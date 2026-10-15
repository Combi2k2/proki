"""A media library: pictures and sounds, each a copy in a folder of its own, listed in a
database (`media`, `media_pools`, `media_picks`).

    key          what picks and pools know it by, and it never changes. The dev's: its path
                 under the assets, without its extension ("bugcat/sad", "alarm-clock").
                 Yours: from its content ("yours/3f9a1c2e"), so a file added twice is kept once
    name         what you see, yours to rename: the dev's key, or your file's name ("gong")
    kind         "image" or "sound"
    file         its copy, in proki's data folder
    added_by     "dev" (it ships with proki) or "you"
    deleted_at   when you deleted it (None: it's in the library). A week later it's gone,
                 its copy too

    lib = Library(db, assets, folder, pools)    the first time: the dev's files, pools and picks in.
                                                Never again: one you delete stays deleted

    lib.get(kind, keys, offset, limit)          what's in the library, and how many in all
    lib.add(path)                               a copy of your file in: its key
    lib.rename(key, name)                       one's name
    lib.remove(key, used)                       one deleted (not one in `used`)
    lib.purge()                                 the ones deleted a week ago or more, gone

    lib.pools()                                 every pool: a named list of keys to draw from
    lib.get_pool(name), lib.set_pool(name, keys)
    lib.get_picks(id),  lib.set_picks(id, keys) an action's picks: what a poke or a question
                                                draws from, by its id
    lib.draw(keys, kind)                        one of `keys` at random, of `kind`, as its file
"""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    key         TEXT PRIMARY KEY,   -- "bugcat/sad", "yours/3f9a1c2e"
    name        TEXT NOT NULL,      -- "bugcat/sad", "gong"
    kind        TEXT NOT NULL,      -- image | sound
    file        TEXT NOT NULL,      -- its copy (absolute)
    added_by    TEXT NOT NULL,      -- dev | you
    added_at    TEXT NOT NULL,
    deleted_at  TEXT                -- gone for good a week after
);
CREATE TABLE IF NOT EXISTS media_pools (
    pool        TEXT NOT NULL,
    pos         INTEGER NOT NULL,
    key         TEXT NOT NULL,
    PRIMARY KEY (pool, pos)
);
CREATE TABLE IF NOT EXISTS media_picks (
    id          TEXT NOT NULL,      -- an action's: "3f9a1c2e"
    pos         INTEGER NOT NULL,
    key         TEXT NOT NULL,
    PRIMARY KEY (id, pos)
);
"""

COLUMNS = ("key", "name", "kind", "file", "added_by")  # a row, as `get` gives it


class Library:
    KINDS: ClassVar[dict[str, str]] = {    # a file's kind, by its extension
        **dict.fromkeys((".gif", ".png", ".jpg", ".jpeg", ".webp"), "image"),
        **dict.fromkeys((".mp3", ".wav", ".ogg"), "sound"),
    }
    KEEP : ClassVar[timedelta] = timedelta(weeks=1)    # how long a deleted one waits, before it's gone
    EMOJIS: ClassVar[str]      = "emojis.json"         # under the assets: the dev's pools and picks, {"pools": ..., "picks": ...}

    def __init__(self, db: sqlite3.Connection, assets: Path, folder: Path, pools: Iterable[str] = ()):
        """The library in `db`: the dev's files under `assets` (media/, sounds/), every copy
        in `folder`, and the `pools` whoever uses it draws from (listed even before they're set)."""
        self.db, self.assets, self.folder, self.names = db, assets, folder, set(pools)
        tables = {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        db.executescript(SCHEMA)
        if "media" not in tables:        self.seed()
        if "media_picks" not in tables:  self.seed_emojis()

    def seed(self) -> None:
        """Every file of the dev's copied in, by its path under the assets."""
        for path in sorted(self.assets.rglob("*")):
            kind = self.KINDS.get(path.suffix.lower())
            if kind is not None:
                key = path.relative_to(self.assets).with_suffix("").as_posix()
                key = key.removeprefix("media/")
                key = key.removeprefix("sounds/")
                self.put(key, key, kind, path, "dev")

    def seed_emojis(self) -> None:
        """The dev's pools, and picks for the actions proki ships: the ones of their keys in the library."""
        path = self.assets / self.EMOJIS
        emojis = json.loads(path.read_text()) if path.exists() else {}
        for name, keys in emojis.get("pools", {}).items():  self.set_pool(name, [m["key"] for m in self.get(keys=keys)[0]])
        for id, keys in emojis.get("picks", {}).items():    self.set_picks(id, [m["key"] for m in self.get(keys=keys)[0]])

    # --- the library --------------------------------------------------------------------------

    def get(self, kind: str | None = None, keys: list[str] | None = None,
            offset: int = 0, limit: int | None = None) -> tuple[list[dict], int]:
        """What's in the library, and how many in all: of `kind`, and the ones of `keys` (in
        their order, one not there left out), else yours first, the newest first. A page of
        it: from `offset`, `limit` of them."""
        where, args = ["deleted_at IS NULL"], []
        if kind:              where.append("kind = ?");                                 args.append(kind)
        if keys is not None:  where.append(f"key IN ({','.join('?' * len(keys))})");    args.extend(keys)

        rows = [dict(zip(COLUMNS, row)) for row in self.db.execute(
            f"SELECT {', '.join(COLUMNS)} FROM media WHERE {' AND '.join(where)} "
            "ORDER BY added_by = 'dev', added_at DESC, key", args)]
        if keys is not None:
            rows.sort(key=lambda row: keys.index(row["key"]))
        return rows[offset:None if limit is None else offset + limit], len(rows)

    def add(self, path: Path) -> str:
        """A copy of your file at `path` in, named as the file is (the same file again: the one
        there already, back if it was deleted). Its key. ValueError for one proki can't play."""
        kind = self.KINDS.get(path.suffix.lower())
        if kind is None:        raise ValueError(f"{path.name}: a picture or a sound is one of {', '.join(self.KINDS)}")
        if not path.is_file():  raise ValueError(f"{path}: no such file")
        key = f"yours/{hashlib.sha256(path.read_bytes()).hexdigest()[:8]}"
        self.put(key, path.stem, kind, path, "you")
        return key

    def rename(self, key: str, name: str) -> None:
        """One's name, a line of text: its key stays. ValueError for one that isn't there."""
        name = name.strip()
        if not self.has(key):            raise ValueError(f"no media {key!r}")
        if not name or "\n" in name:     raise ValueError("a name is a line of text")
        with self.db:
            self.db.execute("UPDATE media SET name = ? WHERE key = ?", (name, key))

    def remove(self, key: str, used: set[str]) -> None:
        """One deleted: out of the library, and gone for good a week later (`purge`).
        ValueError for one that isn't there, or one still used (`used`: what the pokes'
        and questions' picks and the pools name)."""
        if not self.has(key):   raise ValueError(f"no media {key!r}")
        if key in used:         raise ValueError(f"{key!r} is still used: take it out of there first")
        with self.db:
            self.db.execute("UPDATE media SET deleted_at = ? WHERE key = ?", (now(), key))

    def purge(self) -> None:
        """The ones deleted a week ago or more, gone: their rows, and their copies."""
        before = (datetime.now(UTC) - self.KEEP).isoformat()
        gone   = self.db.execute("SELECT file FROM media WHERE deleted_at < ?", (before,)).fetchall()
        with self.db:
            self.db.execute("DELETE FROM media WHERE deleted_at < ?", (before,))
        for (file,) in gone:
            if Path(file).is_relative_to(self.folder):
                Path(file).unlink(missing_ok=True)

    # --- pools, picks, and drawing ------------------------------------------------------------

    def pools(self) -> dict[str, list[str]]:
        """Every pool: the ones named, and any other set."""
        names = {name for (name,) in self.db.execute("SELECT DISTINCT pool FROM media_pools")}
        return {name: self.get_pool(name) for name in sorted(names | self.names)}

    def get_pool(self, name: str) -> list[str]:
        return self.listed("media_pools", "pool", name)

    def set_pool(self, name: str, keys: list[str]) -> None:
        self.relist("media_pools", "pool", name, keys)

    def get_picks(self, id: str) -> list[str]:
        return self.listed("media_picks", "id", id)

    def set_picks(self, id: str, keys: list[str]) -> None:
        self.relist("media_picks", "id", id, keys)

    def draw(self, keys: list[str], kind: str | None = None) -> str | None:
        """One of `keys` at random, of `kind`, as its file (None: none of them is there)."""
        files = [row["file"] for row in self.get(kind, keys=list(keys))[0]]
        return random.choice(files) if files else None

    # --- helpers ------------------------------------------------------------------------------

    def has(self, key: str) -> bool:
        """Whether `key` is in the library (not deleted)."""
        return self.get(keys=[key])[1] > 0

    def put(self, key: str, name: str, kind: str, path: Path, added_by: str) -> None:
        """The file at `path` copied in as `key` (one already there: back if it was deleted,
        with the name it had)."""
        copy = self.folder / f"{key}{path.suffix.lower()}"
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, copy)
        with self.db:
            self.db.execute("INSERT INTO media (key, name, kind, file, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?) "
                            "ON CONFLICT (key) DO UPDATE SET deleted_at = NULL",
                            (key, name, kind, str(copy), added_by, now()))

    def listed(self, table: str, column: str, name: str) -> list[str]:
        """A pool's or an action's keys, in their order."""
        return [key for (key,) in self.db.execute(f"SELECT key FROM {table} WHERE {column} = ? ORDER BY pos", (name,))]

    def relist(self, table: str, column: str, name: str, keys: list[str]) -> None:
        """A pool's or an action's keys, as `keys`. ValueError for one not in the library."""
        if missing := set(keys) - {m["key"] for m in self.get(keys=keys)[0]}:
            raise ValueError(f"no media {', '.join(sorted(missing))}")
        with self.db:
            self.db.execute(f"DELETE FROM {table} WHERE {column} = ?", (name,))
            self.db.executemany(f"INSERT INTO {table} ({column}, pos, key) VALUES (?, ?, ?)",
                                [(name, pos, key) for pos, key in enumerate(keys)])


def now() -> str:
    return datetime.now(UTC).isoformat()
