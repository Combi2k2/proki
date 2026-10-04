"""The AI helper for tasks (Google Gemini, via its REST API).

It helps the user with *their own* tasks: suggesting steps when a task needs
breaking down, and a name for a new goal group. It also labels a window when openjev
can't (core/labeling.py: it sees the app and window title). Suggestions are always
shown for the user to edit or confirm; it never acts on its own.

Models are tried in order (the first may be busy); every call has a time limit,
and after all of them fail the AI is skipped for a while, so a service that's
down doesn't make the user wait on every request. On failure it returns None.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import requests

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = (
    "You are the task assistant inside proki, a focus app. You help the user with their own tasks: "
    "breaking a task into steps that each fit one focus session (under 50 minutes). Your steps are "
    "suggestions the user edits: show a concrete, practical way to break the task down (kinds of "
    "steps and good practices, e.g. a timed practice exam, summarising formulas, splitting by "
    "chapter), and illustrative specifics are fine. Stay within the task's goal; be brief; plain "
    "text, no markdown."
)

REASONS = {
    "vague": "too vague to estimate (unclear scope or end point)",
    "too_long": "longer than one 50-minute focus session",
}


@dataclass(frozen=True)
class AISettings:
    model: str = "gemini-3.5-flash"
    fallback_models: tuple[str, ...] = ("gemini-3.5-flash-lite",)  # tried when the first is busy
    timeout: float = 20.0  # seconds per model; then the next one is tried
    retry_after: float = 300.0  # after every model failed, skip the AI for this many seconds


class TaskHelper:
    """Suggestions for breaking down tasks and naming goal groups."""

    def __init__(self, api_key: str, settings: AISettings):
        self.api_key = api_key
        self.settings = settings
        self.skip_until = 0.0  # monotonic time; every model failed recently

    def steps(self, title: str, description: str, estimate: int, reason: str) -> list[str] | None:
        """Possible steps to break a task into, for the user to edit and choose from."""
        detail = f"\nDescription: {description}" if description else ""
        return _json_list(self._ask(
            f"The user's task: “{title}”{detail}\nTheir estimate: {estimate} minutes. It is "
            f"{REASONS.get(reason, reason)}. Suggest 2 to 5 concrete steps, each doable in under 50 "
            "minutes, showing a good way to approach it. Reply with only a JSON array of strings.",
            json_reply=True,
        ))

    def group_name(self, title: str, description: str) -> str | None:
        """A short name for the goal this task belongs to (e.g. "Statistics final")."""
        detail = f"\nDescription: {description}" if description else ""
        name = self._ask(
            f"The user's task: “{title}”{detail}\nName the goal or project this task serves, in 1 to 3 "
            "words: the thing it moves forward (e.g. a product, course, exam or life area named or implied "
            "in the task), not the kind of work (not \"Bug fixes\" or \"Emails\"). Reply with the name only."
        )
        return name.strip().strip('"“”.') if name else None

    def label(self, text: str, labels: dict[str, str]) -> str | None:
        """The label for an app and window title: one of `labels` (slug → "name:
        description"), or a short name for a new one when none fits."""
        listing = "\n".join(f"- {slug}: {about}" for slug, about in labels.items())
        name = self._ask(
            f"A window in focus on the user's computer (app · title): “{text}”\nKnown labels:\n{listing}\n"
            "Reply with the slug of the label that fits best. If none fits, reply with a new label "
            "of 1 to 3 words naming what kind of app or page it is (not this particular page). "
            "Reply with the label only."
        )
        return name.strip().strip('"“”.`') if name else None

    def _ask(self, prompt: str, json_reply: bool = False) -> str | None:
        if time.monotonic() < self.skip_until:
            return None  # failed recently: don't make the user wait for more timeouts
        body = {
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6, **({"responseMimeType": "application/json"} if json_reply else {})},
        }
        for model in (self.settings.model, *self.settings.fallback_models):
            text = self._call(model, body)
            if text:
                return text
        self.skip_until = time.monotonic() + self.settings.retry_after
        return None

    def _call(self, model: str, body: dict) -> str | None:
        try:
            response = requests.post(
                API.format(model=model), headers={"x-goog-api-key": self.api_key}, json=body,
                timeout=self.settings.timeout,
            )
            if response.status_code != 200:
                return None  # e.g. 503 "high demand": try the next model
            parts = response.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip() or None
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return None


def _json_list(text: str | None) -> list[str] | None:
    if not text:
        return None
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return None
    try:
        items = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    items = [str(i).strip() for i in items if str(i).strip()]
    return items or None
