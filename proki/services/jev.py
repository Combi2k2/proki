"""jev: a structured-decision API. You describe a situation in a short text (`state`) and ask
it named questions. It answers each one with a choice or a probability, never free text.

    jev = Jev("https://api.openjev.sh/v1/systemone", api_key="...", model="openjev")
    jev.ask('A person\'s task: "write the intro"', {
        "size": {
            "type": "choice",
            "instructions": "How long will it take one focused person?",
            "criteria": {
                "short": "under 25 minutes",
                "long": "more than 2 hours"
            }
        },
        "vague": {"type": "noul", "instructions": "Is the task too vague to start?"},
    })
    →  {"size":  {"choice": "short", "probabilities": {"short": 0.8, "long": 0.2}},
        "vague": {"noul": 0.1}}

Question types:

    choice   pick one of `criteria` (option → what it means): its key, and each one's probability
    noul     yes or no: the probability of yes
    score    a level on a scale, `criteria` its levels in order (what each means, lowest first):
             the score (2.97: between levels, by how likely each is), each level's probability
             by its place ("0", "1", ...), the levels as `legend`, and the `confidence`

Any service that speaks this shape fits: openjev (api.openjev.sh), a local jev, or another
backend behind the same shape. Which one, and what's sent to it, is the caller's to say.
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
        """The answers to `questions` (name → question) about `state`, by question name (see
        above). Raises `requests.RequestException` when the call fails or times out."""
        response = requests.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            json={"state": state, "questions": questions, **({"model": self.model} if self.model else {})},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["answers"]
