"""Labeling what's in focus, by its app and window title (core/labels.py keeps the labels).

For a title that has no label yet, in order:

1. **similar**: cosine similarity (TF-IDF over character trigrams, local, instant) between
   the app and title (in a browser, the title only) and the labels' names and descriptions,
   and the titles already labeled (yours or confirmed) of the same app (or, for a page,
   other pages). At or above `SIMILAR`, it takes that label, and that's settled: no question
   (and nothing stored: it's worked out again whenever needed).
2. **openjev** (in the background): one of the existing labels, if it's sure enough
   (`min_confidence`).
3. **gemini** (in the background), when openjev can't: an existing label, or a new one.

A label from openjev or Gemini is shown for you to confirm (or choose another, or name a
new one); one nobody could give is asked. Your answer always wins. Only tracked apps get
here, and only their app name and window title are sent.
"""

from __future__ import annotations

import math
from collections import Counter
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from proki.core.labels import LabelRegistry, title_key
from proki.platforms import current as platform
from proki.utils import cosine, grams, vector

BROWSER_APPS = platform().BROWSER_APPS
SIMILAR = 0.5  # cosine similarity that settles a label without asking
ASK_LATER = timedelta(hours=2)
SUGGESTION_WAIT = timedelta(seconds=10)  # after `ask_after`, wait this long for openjev / Gemini

AskJev = Callable[[str, dict[str, str]], "tuple[str, float] | None"]  # (text, labels) → (slug, probability)
AskGemini = Callable[[str, dict[str, str]], "str | None"]  # (text, labels) → a slug or a new label's name


def compared(key: str) -> str:
    """What's compared of an "app · title": in a browser only the page's title (the
    browser's name says nothing about the page)."""
    app, _, title = key.partition(" · ")
    return title if app in BROWSER_APPS and title else key


def scope(key: str) -> str:
    """Which labeled titles a title is compared with: the same desktop app's, or (for a
    page) other pages', so a terminal's title never takes a website's label. Keys from
    before labels (a website's domain) are pages."""
    app, sep, _ = key.partition(" · ")
    if app in BROWSER_APPS or (not sep and "." in app and " " not in app):
        return "pages"
    return app


class Similarity:
    """The labels and labeled titles as TF-IDF vectors (rebuilt when they change)."""

    def __init__(self, registry: LabelRegistry):
        self.registry = registry
        self._built_for: tuple[int, int] | None = None
        self.idf: dict[str, float] = {}
        self.known: list[tuple[dict[str, float], str, str | None]] = []  # (vector, slug, scope; None: any)

    def best(self, text: str) -> tuple[str, float] | None:
        """The closest label and its similarity."""
        self._build()
        v = vector(grams(compared(text)), self.idf)
        where = scope(text)
        scored = [(cosine(v, known), slug) for known, slug, among in self.known if among in (None, where)]
        if not scored:
            return None
        score, slug = max(scored)
        return slug, score

    def _build(self) -> None:
        examples = self.registry.examples()
        version = (len(self.registry.labels), len(examples))
        if version == self._built_for:
            return
        docs: list[tuple[list[str], str, str | None]] = [
            (grams(f"{label.name} {label.description} {slug.replace('_', ' ')}"), slug, None)
            for slug, label in self.registry.labels.items()]
        docs += [(grams(compared(key)), slug, scope(key)) for key, slug in examples.items()]
        df = Counter(w for tokens, _, _ in docs for w in set(tokens))
        self.idf = {w: math.log((1 + len(docs)) / (1 + n)) + 1 for w, n in df.items()}
        self.known = [(vector(tokens, self.idf), slug, among) for tokens, slug, among in docs]
        self._built_for = version


@dataclass(frozen=True)
class Guess:
    label: str  # a slug (a new label from Gemini is added first)
    source: str  # "similar", "openjev" or "gemini"
    score: float | None  # similarity or probability


class Labeler:
    """The three steps; `similar` is instant, `suggest` makes the network calls."""

    def __init__(self, registry: LabelRegistry, jev: AskJev | None, gemini: AskGemini | None,
                 min_confidence: float = 0.7, threshold: float = SIMILAR):
        self.registry = registry
        self.jev, self.gemini = jev, gemini
        self.min_confidence, self.threshold = min_confidence, threshold
        self.similarity = Similarity(registry)

    def label_of(self, app: str, title: str) -> str | None:
        """The label of a window: the one it has, else a similar one (nothing is stored)."""
        known = self.registry.label_of(title_key(app, title))
        if known:
            return known
        guess = self.similar(app, title)
        return guess.label if guess else None

    def similar(self, app: str, title: str) -> Guess | None:
        best = self.similarity.best(title_key(app, title))
        return Guess(best[0], "similar", best[1]) if best and best[1] >= self.threshold else None

    def suggest(self, app: str, title: str) -> Guess | None:
        """openjev, then Gemini; None when neither could."""
        text = title_key(app, title)
        labels = {slug: f"{label.name}: {label.description}" if label.description else label.name
                  for slug, label in self.registry.labels.items()}
        if self.jev:
            answer = self.jev(text, labels)
            if answer and answer[0] in labels and answer[1] >= self.min_confidence:
                return Guess(answer[0], "openjev", answer[1])
        if self.gemini:
            name = self.gemini(text, labels)
            if name:
                slug = name if name in labels else self.registry.add_label(name)
                return Guess(slug, "gemini", None)
        return None


@dataclass(frozen=True)
class Question:
    kind: str  # "confirm" (a label from openjev / Gemini) or "ask" (no label)
    key: str  # "app · title"
    app: str
    title: str


class LabelLoop:
    """Called every few seconds with the window in focus; returns a question when one is due."""

    def __init__(self, labeler: Labeler, executor: Executor | None,
                 suggest_after: timedelta = timedelta(seconds=2), ask_after: timedelta = timedelta(seconds=10)):
        self.labeler, self.registry = labeler, labeler.registry
        self.executor = executor
        self.suggest_after, self.ask_after = suggest_after, ask_after
        self.current: str | None = None
        self.since: datetime | None = None
        self.pending: dict[str, Future] = {}
        self.tried: set[str] = set()  # keys openjev / Gemini were asked about
        self.later: dict[str, datetime] = {}

    def observe(self, app: str | None, title: str, now: datetime) -> Question | None:
        self._collect(now)
        if not app:
            self.current = None
            return None
        key = title_key(app, title)
        if key != self.current:
            self.current, self.since = key, now
        dwell = now - (self.since or now)
        entry = self.registry.get(key)
        if entry and (entry.confirmed or entry.source == "user"):
            return None
        if self.later.get(key, now) > now:
            return None
        if entry:  # from openjev / Gemini: yours to confirm
            return Question("confirm", key, app, title) if dwell >= self.suggest_after else None
        if self.labeler.similar(app, title):
            return None  # settled; worked out again whenever needed, so not stored
        if dwell < self.suggest_after:
            return None  # just passing through
        if key not in self.tried and self.executor is not None:
            self.tried.add(key)
            self.pending[key] = self.executor.submit(self.labeler.suggest, app, title)
        if dwell < self.ask_after or (key in self.pending and dwell < self.ask_after + SUGGESTION_WAIT):
            return None
        return Question("ask", key, app, title)

    def answered(self, question: Question, response: str, now: datetime) -> None:
        """Responses: "ok" (confirm), "later", "label:<slug>", or "new:<name>"."""
        key = question.key
        if response == "later":
            self.later[key] = now + ASK_LATER
        elif response == "ok":
            self.registry.confirm(key, now)
        elif response.startswith("label:"):
            self.registry.set(key, response.removeprefix("label:"), "user", True, now)
        elif response.startswith("new:"):
            slug = self.registry.add_label(response.removeprefix("new:"))
            self.registry.set(key, slug, "user", True, now)

    def _collect(self, now: datetime) -> None:
        for key, future in list(self.pending.items()):
            if not future.done():
                continue
            del self.pending[key]
            guess = future.result() if future.exception() is None else None
            entry = self.registry.get(key)
            if guess and not (entry and entry.source == "user"):
                self.registry.set(key, guess.label, guess.source, False, now)
