"""jev: a structured-decision API. proki asks it questions it answers with a choice or a
probability, never free text: {"state": text, "questions": {name: {...}}} in,
{"answers": {name: {...}}} out.

Any service that speaks it fits: openjev (api.openjev.sh), a local jev, or a typesafe-AI
backend behind the same shape; the URL and key come from the environment (JEV_URL,
JEV_KEY, e.g. in .env). Optional; only short texts are ever sent (an app name, a
website domain, a tracked window's title, a task's title). The questions themselves are
proki's (core/jev.py).
"""

from __future__ import annotations

import requests


class Jev:
    def __init__(self, url: str, key: str | None = None, model: str | None = None, timeout: float = 5):
        self.url = url
        self.key = key
        self.model = model  # some services want one (openjev: "openjev")
        self.timeout = timeout

    def ask(self, state: str, questions: dict) -> dict:
        """The answers to `questions` about `state`, by question name; raises
        `requests.RequestException` when the call fails."""
        response = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {self.key}"} if self.key else {},
            json={"state": state, "questions": questions, **({"model": self.model} if self.model else {})},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["answers"]
