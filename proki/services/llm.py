"""An LLM: one client for every service that speaks the OpenAI chat-completions API (Gemini,
NVIDIA, Anthropic, OpenAI, Mistral, a local Ollama, ...).

    llm = Llm("https://generativelanguage.googleapis.com/v1beta/openai", api_key="...", model="gemini-2.5-flash")

    llm.ask("Which goal does this task serve?", context={"task": ..., "goals": [...]})  → text
    llm.ask(..., schema={"type": "object", "properties": {...}})                        → the JSON, parsed

    context   what the model should know, sent before the question: text, or anything JSON
              can hold (who it is, what it's for, the facts it needs)
    schema    a JSON schema the answer must follow: the service's structured output, or,
              for a service that has none, the schema written into the question

When the model doesn't answer (an HTTP error, a failed call, an empty answer), `ask` raises
LlmError. Which service and model to ask is the caller's to say.
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
        """The answer to `prompt`: text, or the parsed JSON with a `schema`. Raises LlmError
        when the model doesn't answer."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": _messages(prompt, context),
            "temperature": temperature,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "schema": schema, "strict": True},
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
    """The context (if any) first, as the system's message, then the question."""
    messages = []
    if context is not None:
        text = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False, indent=1, default=str)
        messages.append({"role": "system", "content": text})
    return messages + [{"role": "user", "content": prompt}]


def _schema_in_prompt(body: dict, schema: dict) -> dict:
    """The request for a service without structured output: the schema written into the
    question instead."""
    messages = [*body["messages"]]
    messages[-1] = {
        **messages[-1],
        "content": f"{messages[-1]['content']}\n\nReply with only JSON following this schema, nothing else:\n"
                   f"{json.dumps(schema)}",
    }
    return {k: v for k, v in body.items() if k != "response_format"} | {"messages": messages}


def parse_json(text: str) -> Any:
    """The JSON in a reply, also when it's fenced (```json) or wrapped in words. Raises
    LlmError when there's none."""
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
