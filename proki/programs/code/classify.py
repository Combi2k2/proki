"""@classify: what's in focus, asking you when proki doesn't know.

An app is tracked and labeled once, by its name ("Code"), and a website once, by its host
("mail.google.com"). A browser itself never is. A label says how deep time on it is. The
labels, and a first set of well-known apps and websites with theirs, are in
assets/labels.json. A label is kept by its place in that list, so a new one goes at the end.

A label is found, in order, from: yours, the one an app came with or jev gave (yours to
confirm), or the most similar one (TF-IDF over the tokens of the names) when it's as
similar as `SIMILAR`. Only the app's name or the website's host is sent to jev.

    looking     what's in focus, and what to ask about it (`Look`). jev is asked as soon
                as a tracked app or website without a label shows up, once a run
    tracking    an app or a website you never answered for, a minute in focus: track it?
                (`AskTracking`)
    labeling    a tracked app or website whose label isn't yours: which question to ask,
                by how sure jev is of the label it has, if any (`AskLabel`)
    noidea      no label, nor a similar one: what is it? (`ConfirmNoIdea`)
    unsure      jev's label, jev under 40% sure: is it right? (`ConfirmUnsure`)
    maybe       jev's label, jev 40 to 70% sure (`ConfirmMaybe`)
    sure        jev's label, jev 70% sure or more, or the one it came with (`ConfirmSure`)

A label is chosen from them all, in one list (to confirm one: it's picked already, OK keeps
it). No answer ("Later") asks again in `LATER`. Each question is a step of its own, so it has
its own picture: its picks, by its id ("@classify.sure.confirm_sure"). The `label` and
`depth` inputs read the labels from `Apps.label` and `Apps.depth`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import cache
from urllib.parse import urlsplit

import numpy as np
import tiktoken

from proki import platforms, settings
from proki.channels import Popup, jev
from proki.core.programs import Program, State
from proki.core.signals import Stream
from proki.programs.code.base import Ritual, Step, Table, make_branch, popup_open
from proki.utils import slugify

BROWSER_APPS = platforms.current().BROWSER_APPS
IGNORED      = {"Electron", "proki", *platforms.current().SYSTEM_APPS}   # proki's own windows, and the system's
SIMILAR      = 0.5                   # cosine similarity that settles a label without asking
LATER        = timedelta(hours=2)    # "Ask later"
TIMEOUT      = 24 * 3600             # how long a question waits for you, in seconds


class Depth(Enum):
    """How deep the work is, in Deep Work terms."""

    DEEP     = "deep"          # cognitively demanding, creates value, hard to replicate
    SHALLOW  = "shallow"       # logistics and communication, easy to replicate
    NEUTRAL  = "neutral"       # system tools, between work and not
    DISTRACT = "distraction"   # entertainment unrelated to work


DEPTH = {
    Depth.DEEP     : 1.0,
    Depth.SHALLOW  : 0.5,    # still work, at a lighter load
    Depth.NEUTRAL  : 0.25,   # the line between work and not
    Depth.DISTRACT : 0.0,
}


@dataclass(frozen=True)
class Label:
    name  : str     # how it's shown, and its name in the config: label == "Videos"
    desc  : str     # what it is, for jev and the similarity
    group : str     # what it's chosen under, in a popup
    depth : Depth


SHIPPED = json.loads((settings.ASSETS_DIR / "labels.json").read_text())
LABELS  = [Label(label["name"], label["desc"], label["group"], Depth(label["depth"])) for label in SHIPPED["labels"]]
KNOWN   = SHIPPED["apps"]   # a well-known app's or website's label: {key: its index}


def key_of(app: str, url: str | None) -> str | None:
    """What's labeled of a window: its app's name, or in a browser its page's host, without
    "www." ("https://www.facebook.com/x" gives "facebook.com"). None for a browser on no
    web page."""
    if app not in BROWSER_APPS:  return app or None
    parts = urlsplit(url or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:  return None
    return parts.hostname.removeprefix("www.")


def tokens(text: str) -> list[str]:
    """A name's tokens, as GPT-4o's tokenizer (o200k) cuts its words: "animevietsub.nl"
    gives anime, viet, sub, nl."""
    words = " ".join(w for w in slugify(text).split("_") if w)
    return [token for i in encoding().encode(words) if (token := encoding().decode([i]).strip())]


@cache
def encoding() -> tiktoken.Encoding:
    """o200k, its vocabulary downloaded once into proki's data folder."""
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(settings.DATA_DIR / "tiktoken"))
    return tiktoken.get_encoding("o200k_base")


# --- apps and websites ------------------------------------------------------------------------

@dataclass(frozen=True)
class App:
    key    : str                   # an app's name, or a website's host (`key_of`)
    track  : bool                  # False: you said not to, and it's never asked again
    label  : int | None            # its place in `LABELS` (None: not labeled yet)
    source : str                   # who gave it: "usr" (you, or you said it's right), "dev" (shipped), "openjev"
    set_at : datetime              # when it last changed
    conf   : float | None = None   # how likely jev found its label (None: not jev's)

    @property
    def confirmed(self) -> bool:
        """Whether there's nothing to ask: you gave its label, or said it's right."""
        return self.label is not None and self.source == "usr"


class AppDB(Table[App]):
    NAME = "apps"
    KEY  = "key"


class Apps:
    """The apps table, read once and kept in memory: the `label` and `depth` inputs read it
    every cycle. The well-known apps are added the first time, unconfirmed."""

    def __init__(self, db: AppDB):
        self.db    = db
        self.rows  = {app.key: app for app in db.read()}
        self.index : tuple[dict[str, int], np.ndarray, np.ndarray, list[int]] | None = None   # (vocab, idf, rows, labels)
        for key, label in KNOWN.items():
            if key not in self.rows:  self.keep(key, datetime.now(UTC), label=label, source="dev")

    def get(self, key: str | None) -> App | None:
        return self.rows.get(key) if key else None

    def keep(self, key: str, at: datetime, **changed) -> None:
        """Its row, changed (a new one: tracked, unlabeled)."""
        app = self.rows.get(key) or App(key, True, None, "usr", at)
        self.rows[key] = replace(app, set_at=at, **changed)
        self.db.create(self.rows[key])
        self.index = None

    def label(self, app: str, url: str | None) -> str | None:
        """A window's label, by name (None: none)."""
        index = self.find(app, url)
        return LABELS[index].name if index is not None else None

    def depth(self, app: str, url: str | None) -> float | None:
        """How deep a window is, by its label (None: no label)."""
        index = self.find(app, url)
        return DEPTH[LABELS[index].depth] if index is not None else None

    def find(self, app: str, url: str | None) -> int | None:
        """A window's label: its app's or website's (yours, or one to confirm), else a similar one's."""
        key = key_of(app, url)
        row = self.get(key)
        return row.label if row and row.label is not None else self.similar(key) if key else None

    def similar(self, key: str) -> int | None:
        """The label most like `key`, by the labels themselves and the apps labeled (yours, and
        the shipped ones), if it's like enough (None: none is)."""
        if self.index is None:
            docs = [(tokens(f"{label.name} {label.desc}"), i) for i, label in enumerate(LABELS)]
            docs += [(tokens(app.key), app.label) for app in self.rows.values()
                     if app.label is not None and app.source != "openjev"]  # jev's guesses aren't
            vocab = {t: i for i, t in enumerate(sorted({t for words, _ in docs for t in words}))}
            counts = np.stack([counted(words, vocab) for words, _ in docs])
            idf = np.log((1 + len(docs)) / (1 + (counts > 0).sum(0))) + 1
            self.index = vocab, idf, normalized(counts * idf), [label for _, label in docs]
        vocab, idf, rows, labels = self.index
        words = tokens(key)
        known = counted(words, vocab) * idf
        rare  = idf.max(initial=1) * np.array([words.count(w) for w in set(words) - set(vocab)])  # in no label: as rare as can be
        norm  = np.sqrt(known @ known + rare @ rare)
        scores = rows @ known / norm if norm else np.zeros(len(labels))
        return labels[scores.argmax()] if scores.max() >= SIMILAR else None


def counted(words: list[str], vocab: dict[str, int]) -> np.ndarray:
    """How many times each word of `vocab` is in `words`."""
    counts = np.zeros(len(vocab))
    for word in words:
        if word in vocab:  counts[vocab[word]] += 1
    return counts


def normalized(m: np.ndarray) -> np.ndarray:
    """Each row (or the vector) of length 1 (one of zeros stays so)."""
    norm = np.linalg.norm(m, axis=-1, keepdims=True)
    return np.divide(m, norm, out=np.zeros_like(m), where=norm > 0)


# --- the program ------------------------------------------------------------------------------

class Look(Step):
    """What's in focus now (`watch`), and what to ask about it. jev is asked about a tracked
    app or website with no label as soon as it shows up, once a run."""

    program: Classify

    def __init__(self, program: Classify):
        super().__init__(program)
        self.focus : str | None      = None    # the app or website in focus (`key_of`), and since when
        self.since : datetime | None = None
        self.asked : set[str]        = set()   # what jev was asked about

    @staticmethod
    def watch() -> tuple[str, str | None] | None:
        """The app in focus this cycle, and its page (None: none, you're away, or it's one never
        asked about)."""
        get = lambda name: Stream.registry[name].current() if name in Stream.registry else None
        app = get("app")

        if not app:             return None
        if app in IGNORED:      return None
        if not get("active"):   return None

        return app, get("url")

    async def apply(self) -> None:
        p, now = self.program, Program.now
        window = self.watch()
        key    = key_of(*window) if window else None  # None too for a browser on no web page
        if self.focus != key:
            self.focus = key
            self.since = now

        p.state = p.key = None
        if key is None:  return
        row = p.apps.get(key)

        if row and row.track and row.label is None and key not in self.asked:  # jev's label, for you to confirm
            self.asked.add(key)
            answers = await jev.ask(f"An app or a website someone uses: {key}", {"label": {  # jev gets plain keys: o0, o1, ...
                "type": "choice", "instructions": "What kind of app or website is this?",
                "criteria": {f"o{i}": f"{label.name}: {label.desc}" for i, label in enumerate(LABELS)}}})
            odds = ((answers or {}).get("label") or {}).get("probabilities") or {}
            if chances := {i: c for i in range(len(LABELS)) if (c := odds.get(f"o{i}"))}:
                best = max(chances, key=chances.get)
                p.apps.keep(key, now, label=best, source="openjev", conf=chances[best])
                row = p.apps.get(key)

        if popup_open():                    return  # one question at a time
        if now - self.since < p.ask_after:  return
        if p.later.get(key, now) > now:     return

        if row is None:                                             p.state = "tracking"  # never answered for
        elif not row.track or row.confirmed:                        return
        elif row.label is not None or p.apps.similar(key) is None:  p.state = "labeling"  # else a similar one's, worked out
        p.key = key if p.state else None


class AskTracking(Step):
    """Whether to track an app or a website: OK, Never, or later (no answer)."""

    program: Classify
    SAYS = "You're using “{key}”  jmnk which proki doesn't track yet. Track it?"

    async def apply(self) -> None:
        p, key = self.program, self.program.key
        answer = await Popup.ask(self.SAYS.format(key=key), ["OK", "Never"], TIMEOUT, id=self.id)
        if answer is None:  p.later[key] = Program.now + LATER
        else:               p.apps.keep(key, Program.now, track=answer == 0)


class AskLabel(Step):
    """Which question to ask about a label: by how sure jev is of the one it has, if any."""

    program: Classify

    async def apply(self) -> None:
        p    = self.program
        row  = p.apps.get(p.key)
        conf = row.conf
        if row.label is None:               p.state = "noidea"
        elif conf is None or conf >= 0.7:   p.state = "sure"
        elif conf >= 0.4:                   p.state = "maybe"
        else:                               p.state = "unsure"


class Confirm(Step):
    """A label to confirm: what it `SAYS`, over all the labels, the one it has picked already.
    OK keeps the one picked as yours, Later (no answer) asks again in `LATER`."""

    program: Classify
    SAYS: str

    async def apply(self) -> None:
        p, key = self.program, self.program.key
        has    = p.apps.get(key).label  # its label's place, picked already (None: none)
        says   = self.SAYS.format(key=key, label=LABELS[has].name if has is not None else "")
        answer = await Popup.ask(says, [label.name for label in LABELS], TIMEOUT, id=self.id, selected=has)
        if answer is None:    p.later[key] = Program.now + LATER
        elif answer == has:   p.apps.keep(key, Program.now, source="usr")  # it's right
        else:                 p.apps.keep(key, Program.now, track=True, label=answer, source="usr", conf=None)


class ConfirmNoIdea(Confirm):
    """A label to give: it has none, and nothing like it has one."""

    SAYS = "What is “{key}”?"


class ConfirmUnsure(Confirm):
    """jev's label to confirm, jev under 40% sure."""

    SAYS = "proki thinks “{key}” might be {label}, but isn't sure. Mind telling me what it is?"


class ConfirmMaybe(Confirm):
    """jev's label to confirm, jev 40 to 70% sure."""

    SAYS = "“{key}” looks like {label} to me. Is that right?"


class ConfirmSure(Confirm):
    """A label to confirm: jev's, 70% sure or more, or the one it came with."""

    SAYS = "I'm pretty sure “{key}” is {label}. What do you say?"


class Classify(Ritual):
    TAGS = ("tracking", "labels")

    def __init__(self, apps: Apps, ask_after: timedelta = timedelta(minutes=1)):
        self.apps      = apps
        self.ask_after = ask_after
        self.later : dict[str, datetime] = {}      # "Ask later": not before then
        self.state : str | None          = None    # the question's state, once looked
        self.key   : str | None          = None    # and what it's about: an app, or an app's or a website's key
        go   = lambda state, desc: make_branch(state, desc, **{state: lambda: self.state == state})
        back = [make_branch("looking", "answered, or not")]
        wait = timedelta(0)  # each state's: the next cycle
        super().__init__("@classify", [
            State("looking", do=[Look(self)], every=wait, desc="what's in focus, and whether to ask about it", next=[
                go("tracking", "an app or a website you never answered for, a minute in focus"),
                go("labeling", "a tracked app or website whose label isn't yours, a minute in focus"),
                make_branch("looking", "nothing to ask"),
            ]),
            State("tracking", do=[AskTracking(self)], every=wait, desc="whether to track the app or the website", next=back),
            State("labeling", do=[AskLabel(self)], every=wait, desc="which question to ask about its label", next=[
                go("noidea", "no label, nor a similar one"),
                go("unsure", "jev's label, jev under 40% sure"),
                go("maybe", "jev's label, jev 40 to 70% sure"),
                go("sure", "jev's label, jev 70% sure or more, or the one it came with"),
            ]),
            State("noidea", do=[ConfirmNoIdea(self)], every=wait, desc="what the app or the website is", next=back),
            State("unsure", do=[ConfirmUnsure(self)], every=wait, desc="whether jev's label is right, jev unsure", next=back),
            State("maybe", do=[ConfirmMaybe(self)], every=wait, desc="whether jev's label is right", next=back),
            State("sure", do=[ConfirmSure(self)], every=wait, desc="whether the label it has is right", next=back),
        ])
