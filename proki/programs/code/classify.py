"""What's in focus: the apps and websites you use, each tracked or not, and labeled.

    track.labels                    every label, in your order: name, desc, group, depth. Yours
    track.all                       every app seen
    track.now                       the app in focus: key, track, label, source, set_at, conf
    track.now.label == 'Videos'     its label, by name
    track.pin = track.now           the one asked about, whatever's in focus (None: let go)
    track.pin.label = chosen        its label, yours: one set alone is
    track.since                     minutes the one in focus has been
    track.depth                     how deep it is, by its label
    track.reask = time + 120        the one pinned, else in focus, not asked about for two hours

    zip(track.labels.name, track.labels.desc)       a question's options: [name, desc] each

An app is labeled once, by its name ("Code"), and a website by its host ("mail.google.com"),
never a browser itself. Its label is yours, else the one it came with or jev's, else the most
similar one's.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from functools import cache
from urllib.parse import urlsplit

import numpy as np
import tiktoken

from proki import platforms, settings
from proki.core import primitives
from proki.core.records import Field, Linked, Records, clock
from proki.core.signals import Stream
from proki.errors import VariableError
from proki.storage import Table, record_tables
from proki.utils import minutes, slugify

BROWSERS = platforms.current().BROWSER_APPS
IGNORED  = {"proki", "proki.exe", "proki-ui", "proki-ui.exe", *platforms.current().SYSTEM_APPS}  # proki's windows and the system's: never in focus
SIMILAR  = 0.5                                          # cosine similarity that settles a label without asking


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
    id    : int     # what an app keeps of it
    name  : str     # how it's shown, and read: label == "Videos"
    desc  : str     # what it is, for jev and the similarity
    group : str     # what it's chosen under, in a popup
    depth : Depth


def yours(initial: str | None = None) -> list[dict]:
    """A field you set: a new one's `initial` until you do."""
    return [{"from": "user"}, *([{"from": "auto", "initial": initial}] if initial is not None else [])]


LABEL = [   # a label's fields
    Field("name",  "how it's shown, and read: label == 'Videos'", yours(),          "string"),
    Field("desc",  "what it is, for jev and the similarity",      yours(""),        "string"),
    Field("group", "what it's chosen under, in a popup",          yours("Other"),   "string"),
    Field("depth", "how deep time on it is",                      yours("neutral"), {"type": "string", "enum": [d.value for d in Depth]}),
]

SHIPPED = json.loads((settings.ASSETS_DIR / "labels.json").read_text())                 # the labels you start with
KNOWN   = {key: SHIPPED["labels"][i]["name"] for key, i in SHIPPED["apps"].items()}     # and a well-known app's, by name


def key_of(app: str, url: str | None) -> str | None:
    """What's labeled of a window: its app's name, or in a browser its page's host
    ("https://www.facebook.com/x": "facebook.com"). None for a browser on no web page."""
    if app not in BROWSERS:
        return app or None
    parts = urlsplit(url or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:  return None
    return parts.hostname.removeprefix("www.")


def tokens(text: str) -> list[str]:
    """A name's tokens, as an LLM reads its words: "animevietsub.nl" gives anime, viet, sub, nl."""
    words = " ".join(w for w in slugify(text).split("_") if w)
    return [token for i in encoding().encode(words) if (token := encoding().decode([i]).strip())]


@cache
def encoding() -> tiktoken.Encoding:
    """The tokenizer, fetched once and kept."""
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(settings.DATA_DIR / "tiktoken"))
    return tiktoken.get_encoding("o200k_base")


# --- apps and websites ------------------------------------------------------------------------

@dataclass(frozen=True)
class App:
    key    : str                   # an app's name, or a website's host (`key_of`)
    track  : bool | None           # False: you said not to, and it's never asked again (None: never answered)
    label  : int | None            # its label's id (None: not labeled yet, or its label's gone)
    source : str                   # who gave it: "usr" (you, or you said it's right), "dev" (shipped), "jev"
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
    """The apps and websites, and their labels: what the `label` and `depth` inputs read. The
    first time, proki's labels, and the well-known apps with theirs, for you to confirm.

        apps.find("Code")                   its label, else a similar one's
        apps.keep("Code", at, track=False)  its row, changed
        apps.named("Videos")                a label's id
    """

    def __init__(self, db: AppDB):
        self.db, self.rows = db, {app.key: app for app in db.read()}
        self.seen  : tuple[int, dict[int, Label]] | None = None                                # the labels, as of which writes
        self.index : tuple[dict[str, int], np.ndarray, np.ndarray, list[int]] | None = None    # the similarity's: vocab, idf, rows, ids
        self.make()
        if not self.labels.current():  self.labels.set(SHIPPED["labels"])
        for key, name in KNOWN.items():
            if key not in self.rows:   self.keep(key, datetime.now(UTC), track=True, label=self.named(name), source="dev")
        primitives.Label.label_of, primitives.Depth.depth_of = self.label, self.depth

    def make(self) -> None:
        """track.labels, made again: at each build."""
        self.labels = Records("track.labels", self.db.db, "label", LABEL, record_tables(self.db.db, "label"), desc="every label, in your order")

    def known(self) -> dict[int, Label]:
        """Every label, by its id, in your order."""
        if self.seen is None or self.seen[0] != Records.writes:
            labels = {row["id"]: Label(row["id"], row["name"], row["desc"], row["group"], Depth(row["depth"]))
                      for row in self.labels.current() if row["name"]}
            if self.seen is None or self.seen[1] != labels:  self.index = None
            self.seen = Records.writes, labels
        return self.seen[1]

    def named(self, name: str | None) -> int | None:
        """A label's id, by its name (None: none)."""
        return next((label.id for label in self.known().values() if label.name == name), None)

    def get(self, key: str | None) -> App | None:
        return self.rows.get(key) if key else None

    def keep(self, key: str, at: datetime, **changed) -> None:
        """Its row, changed (a new one: never answered for, unlabeled)."""
        app = self.rows.get(key) or App(key, None, None, "usr", at)
        self.rows[key] = replace(app, set_at=at, **changed)
        self.db.create(self.rows[key])
        if {"label", "source"} & changed.keys():  self.index = None

    def label(self, app: str, url: str | None) -> str | None:
        """A window's label, by name (None: none)."""
        return label.name if (label := self.find(key_of(app, url))) else None

    def depth(self, app: str, url: str | None) -> float | None:
        """How deep a window is, by its label (None: no label)."""
        return DEPTH[label.depth] if (label := self.find(key_of(app, url))) else None

    def find(self, key: str | None) -> Label | None:
        """An app's label: its own, else a similar one's (None: neither)."""
        if key is None:
            return None
        known, row = self.known(), self.get(key)
        return known[row.label] if row and row.label in known else self.similar(key)

    def similar(self, key: str) -> Label | None:
        """The label most like `key`'s, by the labels and the apps labeled, if it's like enough (None: none is)."""
        known = self.known()
        if self.index is None:
            docs = [(tokens(f"{label.name} {label.desc}"), id) for id, label in known.items()]
            docs += [(tokens(app.key), app.label) for app in self.rows.values()
                     if app.label in known and app.source != "jev"]  # jev's guesses aren't
            vocab = {t: i for i, t in enumerate(sorted({t for words, _ in docs for t in words}))}
            counts = np.stack([counted(words, vocab) for words, _ in docs]) if docs else np.zeros((0, 0))
            idf = np.log((1 + len(docs)) / (1 + (counts > 0).sum(0))) + 1
            self.index = vocab, idf, normalized(counts * idf), [id for _, id in docs]
        vocab, idf, rows, ids = self.index
        words = tokens(key)
        found = counted(words, vocab) * idf
        rare  = idf.max(initial=1) * np.array([words.count(w) for w in set(words) - set(vocab)])  # in no label: as rare as can be
        norm  = np.sqrt(found @ found + rare @ rare)
        scores = rows @ found / norm if norm else np.zeros(len(ids))
        return known[ids[scores.argmax()]] if len(ids) and scores.max() >= SIMILAR else None


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


# --- what's in focus -------------------------------------------------------------------------

SOURCES = ["usr", "dev", "jev"]                  # who gave a label: you, proki, or jev
APP     = {                                      # an app, as the config reads it
    "type": "object",
    "properties": {
        "key"    : {"type": "string"},
        "track"  : {"type": "boolean"},
        "label"  : {"type": "string"},
        "source" : {"type": "string", "enum": SOURCES},
        "set_at" : {"type": "number", "format": "time"},
        "conf"   : {"type": "number"},
    },
}
WRITES  = ("track", "label", "source", "conf")   # what the config sets of one


class Track(Linked):
    """`track`: the apps seen, the one in focus, and the one asked about. Made once, its
    names again at each build.

        Track(apps).make
    """

    def __init__(self, apps: Apps):
        self.apps   = apps
        self.seen   : str | None        = None    # what's in focus, and since when
        self.since  : datetime | None   = None
        self.looked : datetime | None   = None    # when it was looked at last
        self.pinned : str | None        = None    # the one asked about
        self.reask  : dict[str, float]  = {}      # each one's: not asked about before then

    def make(self) -> None:
        """track and its fields, made again: at each build."""
        def _pin(app: dict | None) -> None:
            self.pinned = app and app["key"]
            if app:  self.keep(app)

        def _set(app: dict | None) -> None:
            if app is None or app.get("key") != self.focus:
                raise VariableError(f"track.now is the app in focus ({self.focus!r}), not {app and app.get('key')!r}")
            self.keep(app)

        def _snooze(until: float | None) -> None:
            if (key := self.pinned or self.focus) is not None:
                self.reask[key] = until or 0

        self.apps.make()
        fields = {
            "labels" : self.apps.labels,
            "all"    : Linked("track.all", self.all, None, "every app seen, tracked or not", {"type": "array", "items": APP}),
            "now"    : Linked("track.now", lambda: self.app(self.focus), _set, "the app in focus (None: none, you're away, or it's proki's or the system's)", APP),
            "pin"    : Linked("track.pin", lambda: self.app(self.pinned), _pin, "the app asked about, whatever's in focus: set it to pin one (None: none)", APP),
            "since"  : Linked("track.since", self.dwell, None, "minutes the one in focus has been", "number"),
            "depth"  : Linked("track.depth", self.depth, None, "how deep the one in focus is, by its label (or a similar one's)", "number"),
            "reask"  : Linked("track.reask", lambda: self.reask.get(self.pinned or self.focus, 0), _snooze, "when the one pinned, else in focus, can be asked about again (minutes since 1970)", "time"),
        }
        myread = lambda: {n: f.current() for n, f in fields.items()}
        mytype = {"type": "object", "properties": {n: f.type for n, f in fields.items()}}

        super().__init__("track", myread, None, "the apps seen, the one in focus, and the one asked about", mytype)

    @property
    def inputs(self) -> list[Stream]:
        # Refresh activity before observing focus, even though track is registered first.
        return [Stream.registry[name] for name in ("app_name", "tab_url", "active") if name in Stream.registry]

    def advance(self, t: datetime) -> None:
        super().advance(t)
        self.look(t)

    def look(self, now: datetime) -> None:
        """What's in focus at `now`: one seen the first time is kept."""
        if self.looked == now:
            return
        self.looked = now
        app = watch()
        key = key_of(*app) if app else None  # None too for a browser on no web page
        if key != self.seen:
            self.seen, self.since = key, now
        if key and self.apps.get(key) is None:
            self.apps.keep(key, now)

    def keep(self, app: dict) -> None:
        """What the config changed of an app, kept: a label set alone is yours."""
        before  = self.app(app["key"]) or {}
        changed = {k: app.get(k) for k in WRITES if app.get(k) != before.get(k)}
        if not changed:
            return
        if "source" in changed and changed["source"] is None:  raise VariableError(f"{app['key']}'s source is one of {', '.join(SOURCES)}")
        if "label" in changed:                                 changed["label"]  = self.label_id(changed["label"])
        if "label" in changed and "source" not in changed:     changed["source"] = "usr"
        if changed.get("source") == "usr":                     changed["conf"]   = None
        self.apps.keep(app["key"], clock(), **changed)

    @property
    def focus(self) -> str | None:
        """What's in focus now."""
        self.look(Stream.now or clock())
        return self.seen

    def all(self) -> list[dict]:
        """Every app seen, as the config reads it."""
        return [self.app(key) for key in self.apps.rows]

    def app(self, key: str | None) -> dict | None:
        """An app as the config reads it (None: none)."""
        if (row := self.apps.get(key)) is None:
            return None
        return {
            "key"    : row.key,
            "track"  : row.track,
            "label"  : label.name if (label := self.apps.known().get(row.label)) else None,
            "source" : row.source,
            "set_at" : minutes(row.set_at),
            "conf"   : row.conf,
        }

    def dwell(self) -> float | None:
        """The minutes what's in focus has been (None: nothing is)."""
        return ((Stream.now or clock()) - self.since).total_seconds() / 60 if self.focus else None

    def depth(self) -> float | None:
        """How deep what's in focus is: by its label, else a similar one's (None: neither)."""
        return DEPTH[label.depth] if (label := self.apps.find(self.focus)) else None

    def label_id(self, name: str | None) -> int | None:
        """A label's id, by its name (None: none). VariableError for a name no label has."""
        if name is None:
            return None
        if (id := self.apps.named(name)) is None:
            raise VariableError(f"no label is called {name!r}: {', '.join(label.name for label in self.apps.known().values())}")
        return id


def watch() -> tuple[str, str | None] | None:
    """The app in focus, and its page (None: none, you're away, or it's proki's or the system's)."""
    get = lambda name: Stream.registry[name].current() if name in Stream.registry else None
    app = get("app_name")

    if not app or app in IGNORED:  return None
    if not get("active"):          return None

    return app, get("tab_url")
