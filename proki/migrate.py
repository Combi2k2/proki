"""Your database brought up to what this proki reads, a step at a time.

    migrate(db)         the steps it hasn't had, run, in order
    migrate(db, True)   a new one: at the latest version, as it's made

A step takes the database one version on, all of it or none. It's added at the end, and never
changed once it's out. There are none yet: every database is as this proki reads it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

STEPS: list[Callable[[sqlite3.Connection], None]] = []  # each takes the database one version on


def migrate(db: sqlite3.Connection, new: bool = False) -> None:
    """The steps `db` hasn't had, run (`new`: none, it's made as the latest reads it)."""
    if new:
        db.execute(f"PRAGMA user_version = {len(STEPS)}")
        return
    (version,) = db.execute("PRAGMA user_version").fetchone()
    for to, step in enumerate(STEPS[version:], start=version + 1):
        with db:
            db.execute("BEGIN")
            step(db)
            db.execute(f"PRAGMA user_version = {to}")
