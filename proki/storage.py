"""proki's database (proki.db): its tables, a class each.

    StateDB     values by key, as JSON: proki's own records, not a program's state
    SwitchDB    the programs switched off, by name (a key of the state table)
    VariableDB  each variable's latest value
    HistoryDB   each persisted signal's values over time
    SpecDB      your programs: a table for each kind of spec, a row for each spec
"""

from __future__ import annotations

import json
import sqlite3
import typing
from dataclasses import fields
from datetime import UTC, datetime
from typing import Any

from proki.model import Spec, Specs
from proki.model.model import Model

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    key         TEXT PRIMARY KEY,   -- "programs_off"
    value       TEXT NOT NULL       -- JSON
);
CREATE TABLE IF NOT EXISTS variables (
    name        TEXT PRIMARY KEY,   -- a variable of the config
    value       TEXT NOT NULL,      -- its latest value, as JSON
    updated_at  TEXT NOT NULL       -- when it last changed (UTC)
);
CREATE TABLE IF NOT EXISTS signal_history (
    name        TEXT NOT NULL,      -- a persisted signal
    t           TEXT NOT NULL,      -- UTC, ISO
    value       TEXT,               -- JSON
    PRIMARY KEY (name, t)
);
"""


def connect(path) -> sqlite3.Connection:
    """proki.db, with these tables made if they're missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


class StateDB:
    """Values by key, as JSON."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def get(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value: Any) -> None:
        """Kept at once, or with the transaction it's part of."""
        part = self.db.in_transaction
        self.db.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, json.dumps(value)))
        if not part:
            self.db.commit()


class SwitchDB:
    """The programs switched off, by name."""

    KEY = "programs_off"

    def __init__(self, db: sqlite3.Connection):
        self.kv = StateDB(db)

    def load(self) -> set[str]:
        return set(self.kv.get(self.KEY, []))

    def save(self, off: set[str]) -> None:
        self.kv.set(self.KEY, sorted(off))


class VariableDB:
    """Each variable's latest value, as JSON."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def load(self, name: str) -> Any:
        """Its saved value. KeyError if it was never saved."""
        row = self.db.execute("SELECT value FROM variables WHERE name = ?", (name,)).fetchone()
        if row is None:  raise KeyError(name)
        return json.loads(row[0])

    def save(self, name: str, value: Any) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO variables (name, value, updated_at) VALUES (?, ?, ?)",
                            (name, json.dumps(value), datetime.now(UTC).isoformat()))


class HistoryDB:
    """Each persisted signal's values over time."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def load(self, name: str, since: datetime) -> list[tuple[datetime, Any]]:
        rows = self.db.execute("SELECT t, value FROM signal_history WHERE name = ? AND t > ? ORDER BY t",
                               (name, since.astimezone(UTC).isoformat()))
        return [(datetime.fromisoformat(t), json.loads(v)) for t, v in rows]

    def save(self, name: str, t: datetime, value: Any) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO signal_history (name, t, value) VALUES (?, ?, ?)",
                            (name, t.astimezone(UTC).isoformat(), json.dumps(value)))

    def forget(self, name: str, before: datetime) -> None:
        with self.db:
            self.db.execute("DELETE FROM signal_history WHERE name = ? AND t <= ?", (name, before.astimezone(UTC).isoformat()))


class SpecDB:
    """Your programs, as specs: a table for each kind (spec_programs, spec_states, ...), a
    column for each field, and a row for each spec, in order. A text is kept as it is,
    anything else as JSON. The cycle is a key of the state table.

    `save` writes them all again in one transaction: one that fails leaves the last save.
    `load` is None until the first save."""

    CYCLE = "programs_cycle"

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.kv = StateDB(db)

    def load(self) -> Specs | None:
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'spec_programs'").fetchone():
            return None
        specs = Specs(self.kv.get(self.CYCLE, 10))
        for kind, cls in Spec.kinds.items():
            cursor  = self.db.execute(f"SELECT * FROM {self.table(kind)} ORDER BY position")
            columns = [c[0] for c in cursor.description][1:]  # after the position
            hints   = typing.get_type_hints(cls)
            for row in cursor:
                data = {name: value if self.plain(hints[name]) else json.loads(value) for name, value in zip(columns, row[1:])}
                getattr(specs, Model.LISTS[kind]).append(cls.parse(data))
        return specs

    def save(self, specs: Specs) -> None:
        with self.db:
            self.db.execute("BEGIN")  # the tables are dropped and made in it too
            self.kv.set(self.CYCLE, specs.cycle)
            for kind, cls in Spec.kinds.items():
                table, hints = self.table(kind), typing.get_type_hints(cls)
                names = [f.name for f in fields(cls)]
                self.db.execute(f"DROP TABLE IF EXISTS {table}")
                columns = ", ".join(f'"{n}"' for n in names)  # quoted: "when" is a word of SQL
                self.db.execute(f"CREATE TABLE {table} (position INTEGER PRIMARY KEY, {columns})")
                self.db.executemany(
                    f"INSERT INTO {table} VALUES (?, {', '.join('?' for _ in names)})",
                    [(i, *(v if self.plain(hints[n]) else json.dumps(v) for n in names for v in [getattr(spec, n)]))
                     for i, spec in enumerate(getattr(specs, Model.LISTS[kind]))])

    @staticmethod
    def table(kind: str) -> str:
        return f"spec_{Model.LISTS[kind]}"

    @staticmethod
    def plain(hint: Any) -> bool:
        """Whether a field is kept as it is (a text, a word of a few, or none), not as JSON."""
        if typing.get_origin(hint) is typing.Literal:
            return all(isinstance(a, str) for a in typing.get_args(hint))
        return hint is str or hint == str | None
