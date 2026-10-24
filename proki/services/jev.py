"""jev: named questions about a short text, each answered with how likely each answer is.

    jev = Jev("https://api.openjev.sh/v1/systemone", api_key="...", model="openjev")
    jev.ask('A task: "write the intro"', {
        "size":  {"type": "choice", "instructions": "How long?", "criteria": {"short": "under 25 min", "long": "over 2 h"}},
        "vague": {"type": "noul",   "instructions": "Too vague to start?"},
        "ready": {"type": "score",  "instructions": "How ready is it?", "criteria": ["not at all", "somewhat", "ready"]},
    })
    →  {"size":  {"choice": "short", "probabilities": {"short": 0.8, "long": 0.2}, "confidence": 0.78},
        "vague": {"noul": 0.1},
        "ready": {"score": 1.4, "probabilities": {"0": 0.1, "1": 0.4, "2": 0.5}, "legend": [...], "confidence": 0.7}}

    noul      yes or no: the probability of yes
    choice    one of its criteria, {key: what it means}: the key picked, and each one's probability
    score     a level of its criteria, what each means, lowest first: where it is (0 at the first),
              and each level's probability, by its place
"""

from __future__ import annotations

import requests


class Jev:
    """A jev service: where it is, its key, and the model to ask (if it has several)."""

    def __init__(self, api_url: str, api_key: str | None = None, model: str | None = None, timeout: float = 5):
        self.api_url = api_url  # the endpoint questions are posted to
        self.api_key = api_key  # sent as a bearer token. None: no key (a local service)
        self.model = model  # some services want one (openjev: "openjev")
        self.timeout = timeout  # seconds per call

    def ask(self, state: str, questions: dict) -> dict:
        """The answers to `questions` about `state`, by name (above). Raises
        `requests.RequestException` when the call fails or times out."""
        response = requests.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            json={"state": state, "questions": questions, **({"model": self.model} if self.model else {})},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["answers"]
