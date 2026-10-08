"""LLMs: one client for every family that speaks the OpenAI chat-completions API (Gemini,
NVIDIA, Anthropic, OpenAI, Mistral, ..., a local Ollama). Each family's URL, the
environment variable holding its key (e.g. in .env) and its models are in
assets/llms.json. `available()` asks the service itself which models it has now.

    llm = Llm.of("gemini")                         # its first models, the key from GEMINI_API_KEY
    llm = Llm.of("nvidia/moonshotai/kimi-k3")      # family/model
    llm = Llm("http://localhost:8000/v1", api_key=None, model="my-model")   # any URL, any key

    llm.ask("Which goal does this task serve?", context={"task": ..., "goals": [...]})   → text
    llm.ask(..., schema={"type": "object", "properties": {...}})                         → the JSON, parsed
    for piece in llm.ask(..., stream=True): ...                                          → text as it comes

`context`: what the model should know (text, or anything JSON can hold), sent before the
question. `schema`: a JSON schema the answer must follow (the service's structured
output. A service without it gets the schema in the prompt instead.). Models are tried in
order (the first may be busy). After all of them fail, the LLM is skipped for a while, so
a service that's down doesn't make every question wait. A failure raises `LlmError`
(`complete()`: None instead).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from proki.errors import LlmError

FAMILIES_PATH = Path(__file__).resolve().parents[1] / "assets" / "llms.json"


@dataclass(frozen=True)
class Family:
    name: str
    url: str  # the OpenAI-compatible base URL (…/v1)
    key: str | None  # the environment variable holding the key. None: no key (local)
    models: tuple[str, ...]  # a snapshot. `Llm.available()` asks the service


def families() -> dict[str, Family]:
    data = json.loads(FAMILIES_PATH.read_text())
    return {name: Family(name, f["url"], f.get("key"), tuple(f.get("models", ()))) for name, f in data.items()}


class Llm:
    def __init__(self, api_url: str, api_key: str | None = None, model: str | Sequence[str] = (),
                 timeout: float = 30.0, retry_after: float = 300.0, system: str | None = None):
        self.api_url = api_url.rstrip("/")
        self.models = (model,) if isinstance(model, str) else tuple(model)  # tried in order
        if not self.models:
            raise LlmError("no model to ask")
        self.api_key = api_key
        self.timeout = timeout  # seconds per model. Then the next one is tried
        self.retry_after = retry_after  # after every model failed, skip the LLM this many seconds
        self.system = system  # who the model is, before everything else
        self.skip_until = 0.0  # monotonic time

    @classmethod
    def of(cls, spec: str, fallbacks: int = 1, **kwargs: Any) -> Llm:
        """"family" (its first model, and `fallbacks` more after it) or "family/model". The
        key from the family's environment variable."""
        name, _, model = spec.partition("/")
        family = families().get(name)
        if family is None:
            raise LlmError(f"no LLM family {name!r} ({', '.join(families())})")
        models = (model,) if model else family.models[: 1 + fallbacks]
        if not models:
            raise LlmError(f"{name}: name a model (\"{name}/<model>\"); `available()` lists them")
        key = None
        if family.key:
            key = os.environ.get(family.key)
            if not key:
                raise LlmError(f"{name}: no key ({family.key} isn't set)")
        return cls(family.url, key, models, **kwargs)

    # --- asking ----------------------------------------------------------------------

    def ask(self, prompt: str, context: Any = None, schema: dict | None = None, stream: bool = False,
            temperature: float = 0.2) -> Any:
        """The answer: text, or the parsed JSON with a `schema`, or with `stream` the text
        in pieces as it comes (an iterator)."""
        if time.monotonic() < self.skip_until:
            raise LlmError("skipped: every model failed recently")
        messages = self._messages(prompt, context)
        body: dict[str, Any] = {"messages": messages, "temperature": temperature}
        if schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "answer", "schema": schema, "strict": True}}
        if stream:
            return self._stream(body)
        text = self._first(body, schema)
        return parse_json(text) if schema is not None else text

    def complete(self, prompt: str, context: Any = None) -> str | None:
        """The answer as text, or None when it fails."""
        try:
            return self.ask(prompt, context)
        except LlmError:
            return None

    def _messages(self, prompt: str, context: Any) -> list[dict]:
        messages = [{"role": "system", "content": self.system}] if self.system else []
        if context is not None:
            text = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False, indent=1, default=str)
            messages.append({"role": "system", "content": f"Context:\n{text}"})
        return messages + [{"role": "user", "content": prompt}]

    def _first(self, body: dict, schema: dict | None) -> str:
        """The first model that answers."""
        problems = []
        for model in self.models:
            try:
                response = self._post({**body, "model": model})
                if response.status_code == 400 and schema is not None:  # no structured output here
                    response = self._post(_schema_in_prompt({**body, "model": model}, schema))
                if response.status_code != 200:
                    problems.append(f"{model}: HTTP {response.status_code}")  # e.g. 503 "busy": the next one
                    continue
                text = response.json()["choices"][0]["message"].get("content") or ""
                if text.strip():
                    return text.strip()
                problems.append(f"{model}: an empty answer")
            except (requests.RequestException, KeyError, IndexError, ValueError) as e:
                problems.append(f"{model}: {e.__class__.__name__}")
        self.skip_until = time.monotonic() + self.retry_after
        raise LlmError("; ".join(problems))

    def _stream(self, body: dict) -> Iterator[str]:
        """Server-sent events, from the first model that answers."""
        for model in self.models:
            try:
                response = self._post({**body, "model": model, "stream": True}, stream=True)
            except requests.RequestException:
                continue
            if response.status_code != 200:
                continue
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    piece = json.loads(data)["choices"][0]["delta"].get("content")
                except (ValueError, KeyError, IndexError):
                    continue
                if piece:
                    yield piece
            return
        self.skip_until = time.monotonic() + self.retry_after
        raise LlmError("no model answered")

    def _post(self, body: dict, stream: bool = False) -> requests.Response:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return requests.post(f"{self.api_url}/chat/completions", headers=headers, json=body, timeout=self.timeout,
                             stream=stream)

    def available(self) -> list[str]:
        """The models the service has now."""
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = requests.get(f"{self.api_url}/models", headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return sorted(m["id"].removeprefix("models/") for m in response.json()["data"])
        except (requests.RequestException, KeyError, ValueError) as e:
            raise LlmError(f"can't list models: {e}") from None


def _schema_in_prompt(body: dict, schema: dict) -> dict:
    """For a service without structured output: the schema in the question."""
    messages = [*body["messages"]]
    messages[-1] = {**messages[-1], "content": f"{messages[-1]['content']}\n\nReply with only JSON following this "
                                               f"schema, nothing else:\n{json.dumps(schema)}"}
    return {k: v for k, v in body.items() if k != "response_format"} | {"messages": messages}


def parse_json(text: str) -> Any:
    """The JSON in a reply (fenced or wrapped in words too)."""
    try:
        return json.loads(text)
    except ValueError:
        pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if starts:
        start = min(starts)
        end = text.rfind("}" if text[start] == "{" else "]")
        try:
            return json.loads(text[start:end + 1])
        except ValueError:
            pass
    raise LlmError(f"not JSON: {text[:80]!r}")
