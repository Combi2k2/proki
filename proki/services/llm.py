"""An LLM: any service that speaks the OpenAI chat API (Gemini, Anthropic, OpenAI, Mistral,
a local Ollama, ...).

    llm = Llm("https://generativelanguage.googleapis.com/v1beta/openai", api_key="...", model="gemini-2.5-flash")
    llm.ask("Which goal does this task serve?", context={"task": ..., "goals": [...]})    →  a text
    llm.ask(..., schema={"type": "object", "properties": {...}})                          →  the JSON

    context   what it should know first: a text, or anything JSON holds
    schema    the JSON schema its answer follows

No answer (a failed call, an empty one) raises LlmError.
"""

from __future__ import annotations

import json
from typing import Any

import requests

from proki.errors import LlmError


class Llm:
    """An OpenAI-compatible service, and the model to ask there."""

    def __init__(self, api_url: str, api_key: str | None, model: str, timeout: float = 30):
        self.api_url = api_url.rstrip("/")  # the service's base address (…/v1)
        self.api_key = api_key  # sent as a bearer token. None: no key (a local service)
        self.model = model
        self.timeout = timeout  # seconds

    def ask(self, prompt: str, context: Any = None, schema: dict | None = None, temperature: float = 0.2) -> Any:
        """The answer to `prompt`: a text, or with a `schema` its JSON. LlmError: no answer."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": _messages(prompt, context),
            "temperature": temperature,
        }
        body["messages"].insert(0, {
            "role": "system",
            "content": "Think less. Keep reasoning brief and focus on useful, concrete results. "
                        "Answer directly, without a long analysis. Follow the requested output format.",
        })
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "reasoning_schema", "strict": True, "schema": schema},
            }

        try:
            response = self._post(body)
            if response.status_code == 400 and schema is not None:  # no structured output here
                response = self._post(_schema_in_prompt(body, schema))
            if response.status_code != 200:
                raise LlmError(f"{self.model}: HTTP {response.status_code}")

            text = response.json()["choices"][0]["message"].get("content") or ""
        except (requests.RequestException, KeyError, IndexError, ValueError) as e:
            raise LlmError(f"{self.model}: {e.__class__.__name__}") from None

        if not text.strip():  raise LlmError(f"{self.model}: an empty answer")
        return parse_json(text) if schema is not None else text.strip()

    def _post(self, body: dict) -> requests.Response:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return requests.post(f"{self.api_url}/chat/completions", headers=headers, json=body, timeout=self.timeout)


def _messages(prompt: str, context: Any) -> list[dict]:
    """What's sent: the context (if any), then the question."""
    messages = []
    if context is not None:
        text = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False, indent=1, default=str)
        messages.append({"role": "system", "content": text})
    return messages + [{"role": "user", "content": prompt}]


def _schema_in_prompt(body: dict, schema: dict) -> dict:
    """The request for a service that can't hold to a schema: it's asked for in words."""
    messages = [*body["messages"]]
    messages[-1] = {
        **messages[-1],
        "content": f"{messages[-1]['content']}\n\nReply with only JSON following this schema, nothing else:\n"
                   f"{json.dumps(schema)}",
    }
    return {k: v for k, v in body.items() if k != "response_format"} | {"messages": messages}


def parse_json(text: str) -> Any:
    """The JSON in a reply, words around it or not. LlmError: there's none."""
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
