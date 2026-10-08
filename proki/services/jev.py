"""jev: a structured-decision API. proki asks it questions it answers with a choice or a
probability, never free text:

- input  :  {"state": text, "questions": {name: {...}}},
- output :  {"answers": {name: {...}}} out.

Any service that speaks it fits: openjev (api.openjev.sh), a local jev, or a typesafe-AI
backend behind the same shape. The URL and key come from the environment (JEV_URL,
JEV_KEY, e.g. in .env). Optional. Only short texts are ever sent (an app name, a
website domain, a tracked window's title, a task's title). The questions themselves are
proki's (core/jev.py).
"""

from __future__ import annotations

import requests


class Jev:
    def __init__(self, api_url: str, api_key: str | None = None, model: str | None = None, timeout: float = 5):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model  # some services want one (openjev: "openjev")
        self.timeout = timeout

    def ask(self, state: str, questions: dict) -> dict:
        """The answers to `questions` about `state`, by question name. Raises
        `requests.RequestException` when the call fails."""
        response = requests.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            json={"state": state, "questions": questions, **({"model": self.model} if self.model else {})},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["answers"]
