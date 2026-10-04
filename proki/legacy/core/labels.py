"""The label registry: what an app or page is ("ide", "video_streaming", ...), by its app
and window title, kept in a file (`LABELS_PATH`, JSON) rather than in the code.

    labels   slug → name, description, group (for choosing in a popup) and the default
             category (how time on it counts, unless a rule or your answer for one site
             says otherwise)
    titles   "app · title" → the label, who gave it (user, similar, openjev, gemini),
             whether you confirmed it, and when

The first time, the labels come from the taxonomy shipped with proki
(assets/labels.json); `migrate` also brings over the kinds stored before labels existed.
Labels are slugs (`slugify`): "Video streaming" → "video_streaming".
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from proki.legacy.core.events import Category
from proki.utils import slugify

TAXONOMY = Path(__file__).resolve().parents[2] / "assets" / "labels.json"
OTHER_GROUP = "Other"

# how deep each category is: the `depth` primitive (core/signals/primitive.py)
DEPTH = {
    Category.DEEP: 1.0,
    Category.NEUTRAL: 0.5,  # tools: neither helps nor hurts much
    Category.SHALLOW: 0.25,
    Category.DISTRACTION: 0.0,
}


def title_key(app: str, title: str) -> str:
    """What is labeled: the app and its window title (in a browser, the page's title)."""
    return f"{app} · {title}" if title else app


@dataclass(frozen=True)
class Label:
    name: str
    description: str = ""
    group: str = OTHER_GROUP
    category: str | None = None  # a Category value; None: no default, it's asked


@dataclass(frozen=True)
class Entry:
    label: str  # a slug
    source: str  # "user", "similar", "openjev" or "gemini"
    confirmed: bool
    at: str  # ISO time


class LabelRegistry:
    def __init__(self, path: Path):
        self.path = path
        data = json.loads(path.read_text()) if path.exists() else json.loads(TAXONOMY.read_text())
        self.labels = {slug: Label(**label) for slug, label in data.get("labels", {}).items()}
        self.titles = {key: Entry(**entry) for key, entry in data.get("titles", {}).items()}

    # --- labels ------------------------------------------------------------------

    def add_label(self, name: str, description: str = "", group: str = OTHER_GROUP,
                  category: Category | None = None) -> str:
        """The slug of `name`, added if new (an existing label keeps what it had)."""
        slug = slugify(name)
        if not slug:
            raise ValueError("a label needs a name")
        if slug not in self.labels:
            self.labels[slug] = Label(name.strip(), description, group, category.value if category else None)
            self.save()
        return slug

    def set_category(self, slug: str, category: Category | None) -> None:
        label = self.labels[slug]
        self.labels[slug] = Label(label.name, label.description, label.group, category.value if category else None)
        self.save()

    def name(self, slug: str | None) -> str:
        return self.labels[slug].name if slug in self.labels else "unknown"

    def category(self, slug: str | None) -> Category | None:
        label = self.labels.get(slug) if slug else None
        return Category(label.category) if label and label.category else None

    def depth(self, slug: str | None) -> float | None:
        """How deep a label is (`DEPTH` of its category); None without a category."""
        category = self.category(slug)
        return DEPTH[category] if category else None

    def groups(self) -> list[str]:
        return list(dict.fromkeys(label.group for label in self.labels.values()))

    def in_group(self, group: str) -> list[tuple[str, Label]]:
        return [(slug, label) for slug, label in self.labels.items() if label.group == group]

    # --- labeled titles ----------------------------------------------------------

    def get(self, key: str) -> Entry | None:
        return self.titles.get(key)

    def label_of(self, key: str) -> str | None:
        entry = self.titles.get(key)
        return entry.label if entry else None

    def set(self, key: str, slug: str, source: str, confirmed: bool, at: datetime) -> None:
        if slug not in self.labels:
            raise KeyError(f"no label {slug!r}")
        self.titles[key] = Entry(slug, source, confirmed, at.isoformat())
        self.save()

    def confirm(self, key: str, at: datetime) -> None:
        entry = self.titles[key]
        self.titles[key] = Entry(entry.label, entry.source, True, at.isoformat())
        self.save()

    def examples(self) -> dict[str, str]:
        """Titles whose label can be trusted (yours, or confirmed): key → slug."""
        return {key: e.label for key, e in self.titles.items() if e.confirmed or e.source == "user"}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"labels": {slug: asdict(label) for slug, label in self.labels.items()},
                "titles": {key: asdict(entry) for key, entry in self.titles.items()}}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, self.path)  # never half-written


def migrate(registry: LabelRegistry, old_kinds: list[tuple[str, str, str, str]], at: datetime) -> int:
    """Bring over the kinds stored per app or website before labels existed (key, kind,
    source, set_at); yours stay confirmed. Returns how many."""
    count = 0
    for key, kind, source, _ in old_kinds:
        if kind == "other" or kind not in registry.labels or key in registry.titles:
            continue
        mine = source == "user"
        registry.titles[key] = Entry(kind, "user" if mine else source, mine, at.isoformat())
        count += 1
    registry.save()
    return count
