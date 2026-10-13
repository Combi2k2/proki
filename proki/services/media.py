"""A media library: pictures and sounds, each a copy in a folder of its own, listed in a
database (`media`, `media_pools`).

    key          what it's named by. The dev's: its path under
                 the assets, without its extension ("bugcat/sad", "alarm-clock"). Yours:
                 from its content ("yours/3f9a1c2e"), so a file added twice is kept once
    kind         "image" or "sound"
    file         its copy, in proki's data folder
    added_by     "dev" (it ships with proki) or "you"
    deleted_at   when you deleted it (None: it's in the library). A week later it's gone,
                 its copy too

    lib = Library(db, assets, folder, pools)
                                        a new library (no table yet) starts with the dev's
                                        files, copied in. Never again: one you delete stays
                                        deleted

    lib.get(kind, keys, offset, limit)  what's in the library, and how many in all
    lib.add(path)                       a copy of your file in: its key
    lib.remove(key, used)               one deleted (not one in `used`)
    lib.purge()                         the ones deleted a week ago or more, gone

    lib.pools()                         every pool: a named list of keys to draw from (the
                                        ones named in `pools` even before they're set)
    lib.get_pool(name)
    lib.set_pool(name, keys)
    lib.draw(keys)                      one of them at random, as its file (None: none)
"""

from __future__ import annotations

import hashlib
import random
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    key         TEXT PRIMARY KEY,   -- "bugcat/sad", "yours/3f9a1c2e"
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
"""

COLUMNS = ("key", "kind", "file", "added_by")  # a row, as `get` gives it


class Library:
    KINDS: ClassVar[dict[str, str]] = {  # a file's kind, by its extension
        ".gif": "image", ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
        ".mp3": "sound", ".wav": "sound", ".ogg": "sound",
    }
    KEEP: ClassVar[timedelta] = timedelta(weeks=1)  # how long a deleted one waits, before it's gone

    def __init__(self, db: sqlite3.Connection, assets: Path, folder: Path, pools: Iterable[str] = ()):
        """The library in `db`: the dev's files under `assets` (media/, sounds/), every copy
        in `folder`, and the `pools` whoever uses it draws from."""
        self.db, self.assets, self.folder, self.names = db, assets, folder, set(pools)
        new = not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'media'").fetchone()
        Upgrade.columns(db)
        db.executescript(SCHEMA)
        Upgrade.rows(self)
        if new:
            self.seed()

    def seed(self) -> None:
        """Every file of the dev's copied in, by its path under the assets."""
        for path in sorted(self.assets.rglob("*")):
            kind = self.KINDS.get(path.suffix.lower())
            key  = path.relative_to(self.assets).with_suffix("").as_posix().removeprefix("media/").removeprefix("sounds/")
            if kind:
                self.put(key, kind, path, "dev")

    # --- the library ------------------------------------------------------------------------

    def get(self, kind: str | None = None, keys: list[str] | None = None,
            offset: int = 0, limit: int | None = None) -> tuple[list[dict], int]:
        """What's in the library, and how many in all: of `kind`, and the ones of `keys` (in
        their order, one not there left out), else yours first, the newest first. A page of
        it: from `offset`, `limit` of them."""
        where, args = ["deleted_at IS NULL"], []
        if kind:              where.append("kind = ?");                                 args.append(kind)
        if keys is not None:  where.append(f"key IN ({','.join('?' * len(keys))})");   args.extend(keys)

        rows = [dict(zip(COLUMNS, row)) for row in self.db.execute(
            f"SELECT {', '.join(COLUMNS)} FROM media WHERE {' AND '.join(where)} "
            "ORDER BY added_by = 'dev', added_at DESC, key", args)]
        if keys is not None:
            rows.sort(key=lambda row: keys.index(row["key"]))
        return rows[offset:None if limit is None else offset + limit], len(rows)

    def add(self, path: Path) -> str:
        """A copy of your file at `path` in (the same file again: the one there already, back
        if it was deleted). Its key. ValueError for a file that isn't a picture or a sound proki plays."""
        kind = self.KINDS.get(path.suffix.lower())
        if kind is None:          raise ValueError(f"{path.name}: a picture or a sound is one of {', '.join(self.KINDS)}")
        if not path.is_file():    raise ValueError(f"{path}: no such file")
        key = f"yours/{hashlib.sha256(path.read_bytes()).hexdigest()[:8]}"
        self.put(key, kind, path, "you")
        return key

    def remove(self, key: str, used: set[str]) -> None:
        """One deleted: out of the library, and gone for good a week later (`purge`).
        ValueError for one that isn't there, or one still used (`used`: what pokes,
        questions and pools name)."""
        if not self.get(keys=[key])[1]:  raise ValueError(f"no media {key!r}")
        if key in used:                  raise ValueError(f"{key!r} is still used (a poke, a question or a pool): take it out of there first")
        with self.db:
            self.db.execute("UPDATE media SET deleted_at = ? WHERE key = ?", (now(), key))

    def purge(self) -> None:
        """The ones deleted a week ago or more, gone: their rows, and their copies."""
        before = (datetime.now(timezone.utc) - self.KEEP).isoformat()
        gone   = self.db.execute("SELECT file FROM media WHERE deleted_at < ?", (before,)).fetchall()
        with self.db:
            self.db.execute("DELETE FROM media WHERE deleted_at < ?", (before,))
        for (file,) in gone:
            if Path(file).is_relative_to(self.folder):
                Path(file).unlink(missing_ok=True)

    def put(self, key: str, kind: str, path: Path, added_by: str) -> None:
        """The file at `path` copied in as `key` (one already there: back, if it was deleted)."""
        copy = self.folder / f"{key}{path.suffix.lower()}"
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, copy)
        with self.db:
            self.db.execute("INSERT INTO media (key, kind, file, added_by, added_at) VALUES (?, ?, ?, ?, ?) "
                            "ON CONFLICT (key) DO UPDATE SET deleted_at = NULL", (key, kind, str(copy), added_by, now()))

    # --- pools, and drawing -----------------------------------------------------------------

    def pools(self) -> dict[str, list[str]]:
        """Every pool: the ones named, and any other set."""
        names = {name for (name,) in self.db.execute("SELECT DISTINCT pool FROM media_pools")}
        return {name: self.get_pool(name) for name in sorted(names | self.names)}

    def get_pool(self, name: str) -> list[str]:
        return [key for (key,) in self.db.execute("SELECT key FROM media_pools WHERE pool = ? ORDER BY pos", (name,))]

    def set_pool(self, name: str, keys: list[str]) -> None:
        """Pool `name` as `keys`. ValueError for a key not in the library."""
        if missing := set(keys) - {m["key"] for m in self.get(keys=keys)[0]}:
            raise ValueError(f"no media {', '.join(sorted(missing))}")
        with self.db:
            self.db.execute("DELETE FROM media_pools WHERE pool = ?", (name,))
            self.db.executemany("INSERT INTO media_pools (pool, pos, key) VALUES (?, ?, ?)",
                                [(name, pos, key) for pos, key in enumerate(keys)])

    def draw(self, keys: list[str]) -> str | None:
        files = [row["file"] for row in self.get(keys=list(keys))[0]]
        return random.choice(files) if files else None


class Upgrade:
    """A library kept by an older proki, brought up to this one's, as it's opened:

        2026-10-13   `origin` (shipped | yours) is `added_by` (dev | you), a deleted one
                     waits a week (`deleted_at`) instead of being hidden, and a pool's
                     `position` is its `pos`
        2026-10-13   the dev's files are copied in, as yours are: deleting one deletes it.
                     The ones hidden stay out
    """

    @staticmethod
    def columns(db: sqlite3.Connection) -> None:
        columns = lambda table: {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        with db:
            if "origin" in columns("media"):
                db.execute("ALTER TABLE media RENAME COLUMN origin TO added_by")
                db.execute("ALTER TABLE media ADD COLUMN deleted_at TEXT")
                db.execute("UPDATE media SET added_by = CASE added_by WHEN 'shipped' THEN 'dev' ELSE 'you' END")
            if "position" in columns("media_pools"):
                db.execute("ALTER TABLE media_pools RENAME COLUMN position TO pos")

    @staticmethod
    def rows(library: Library) -> None:
        db  = library.db
        old = db.execute("SELECT key, kind, file FROM media WHERE added_by = 'dev' AND file NOT LIKE ?",
                         (f"{library.folder}%",)).fetchall()
        with db:
            db.execute("DROP TABLE IF EXISTS media_hidden")
        for key, kind, file in old:
            with db:
                db.execute("DELETE FROM media WHERE key = ?", (key,))
            if Path(file).is_file():
                library.put(key, kind, Path(file), "dev")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
