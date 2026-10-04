"""Local SQLite storage: nudges, small tasks, categories, tracking choices, focus ratings, focus minutes."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from proki.core.events import Category, Finding

SCHEMA = """
CREATE TABLE IF NOT EXISTS nudges (
    id INTEGER PRIMARY KEY,
    shown_at TEXT NOT NULL,
    rule TEXT NOT NULL,
    message TEXT NOT NULL,
    response TEXT            -- e.g. 'ok', 'snooze', 'dismissed'
);
CREATE TABLE IF NOT EXISTS tasks (  -- the old small-task inbox, replaced by the backlog
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,
    done_at TEXT
);
CREATE TABLE IF NOT EXISTS categories (
    key TEXT PRIMARY KEY,    -- app name, or website domain
    category TEXT NOT NULL,
    source TEXT NOT NULL,    -- 'user' or 'openjev'
    set_at TEXT NOT NULL,
    confidence REAL,         -- openjev's probability; NULL for user answers
    confirmed_at TEXT        -- when the user accepted openjev's answer; NULL if not (yet)
);
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL,          -- the website domain or app quit for 30 days
    started TEXT NOT NULL,      -- day 1 (local date)
    status TEXT NOT NULL,       -- 'running', 'quit' (for good), 'ended' (went back)
    slips INTEGER DEFAULT 0,
    better_with_it INTEGER,     -- day-30 answers (1 yes, 0 no)
    anyone_cared INTEGER,
    ended_at TEXT
);
CREATE TABLE IF NOT EXISTS tool_verdicts (
    key TEXT PRIMARY KEY,       -- website domain or app
    verdict TEXT NOT NULL,      -- 'serves' (a goal), 'little', 'no'
    group_id INTEGER,           -- the goal it serves ('serves')
    minutes_then REAL,          -- its time in the week it was judged
    answered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY,
    asked_at TEXT NOT NULL,
    answered_at TEXT NOT NULL,
    rating INTEGER,             -- 1 (scattered) .. 5 (deeply focused); NULL = skipped
    source TEXT NOT NULL,       -- 'sampled' (random popup) or 'manual' (from the tray menu)
    snapshot TEXT               -- JSON: proki's focus score and components at that moment
);
CREATE TABLE IF NOT EXISTS focus_minutes (
    minute TEXT PRIMARY KEY,    -- start of the minute, UTC
    intensity REAL,             -- main-window focus intensity at its end; NULL = mostly away
    activity TEXT               -- what was mostly done: deep, shallow, ..., away; NULL = no data
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,              -- NULL while the session is running
    pokes INTEGER DEFAULT 0,
    asked_done INTEGER DEFAULT 0,
    wrap_ups INTEGER DEFAULT 0,
    alarms INTEGER DEFAULT 0,
    ended_by TEXT,              -- 'user', or 'away' (ended itself after 10 min away)
    group_id INTEGER            -- the goal group worked on (the last one started in the session)
);
CREATE TABLE IF NOT EXISTS weekly_reviews (
    week TEXT PRIMARY KEY,      -- the Monday of the reviewed week
    done_at TEXT NOT NULL,
    answer TEXT                 -- "what will you change next week?"; NULL = nothing
);
CREATE TABLE IF NOT EXISTS plans (
    day TEXT PRIMARY KEY,       -- the day being planned (YYYY-MM-DD, proki's day)
    block_start TEXT NOT NULL,  -- HH:MM: this day's block starts at a different time
    made_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS block_log (
    day TEXT NOT NULL,
    action TEXT NOT NULL,       -- 'skipped'
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS todos (  -- the earlier day-plan list; read once to migrate into the backlog
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,          -- the day it was planned for; open ones carry over
    text TEXT NOT NULL,
    kind TEXT,                  -- 'deep' or 'shallow' (openjev's estimate)
    minutes INTEGER,            -- estimated size (openjev); NULL = unknown
    position INTEGER NOT NULL,  -- order within the day
    status TEXT NOT NULL DEFAULT 'open',  -- 'open', 'done' or 'dropped'
    created_at TEXT NOT NULL,
    done_at TEXT
);
CREATE TABLE IF NOT EXISTS goal_groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    priority TEXT NOT NULL DEFAULT 'normal',  -- 'high', 'normal' or 'low'
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backlog (
    id INTEGER PRIMARY KEY,
    group_id INTEGER REFERENCES goal_groups(id),
    parent_id INTEGER REFERENCES backlog(id),  -- set for the steps of a broken-down task
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    deadline TEXT,                  -- YYYY-MM-DD
    estimate INTEGER NOT NULL,      -- minutes, the user's own estimate
    kind TEXT,                      -- openjev: 'deep' or 'shallow'
    jev_minutes INTEGER,            -- openjev's size estimate (NULL = unclear)
    jev_specific REAL,              -- openjev: how specific (0..1)
    jev_offline REAL,               -- openjev: how likely it can be done away from a computer (0..1)
    offline INTEGER,                -- the user's answer: 1 offline, 0 at the computer, NULL not asked
    status TEXT NOT NULL DEFAULT 'open',  -- 'open', 'done' or 'dropped'
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    done_at TEXT
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,             -- what the user noted while on something shallow or distracting
    category TEXT,                  -- the source's category: 'shallow' or 'distraction'
    source_app TEXT,
    source_title TEXT,
    source_url TEXT,
    task_id INTEGER,                -- the task it became, if any
    reviewed INTEGER DEFAULT 0      -- 1 once gone through in the shutdown ritual
);
CREATE TABLE IF NOT EXISTS absences (
    id INTEGER PRIMARY KEY,
    start TEXT NOT NULL,            -- last activity before it (UTC)
    end TEXT NOT NULL,              -- first activity after it (UTC)
    activity TEXT,                  -- e.g. 'meal', 'shower' (core/routines.py TAXONOMY); NULL = unknown
    source TEXT NOT NULL,           -- 'present' (the user: I was here), 'still_there' (openjev: they stayed
                                    -- at the computer, not asked),
                                    -- 'user' (picked), 'jev' (typed, openjev sure), 'jev_unsure' (openjev's guess,
                                    -- not confirmed), 'typed' (no openjev), 'auto' (overnight → sleep), 'unasked', 'skipped'
    note TEXT,                      -- what the user typed
    confidence REAL                 -- openjev's probability for `activity`
);
CREATE TABLE IF NOT EXISTS variables (
    name TEXT PRIMARY KEY,          -- a variable of the config (core/signals/variable.py)
    value TEXT NOT NULL,            -- its latest value, as JSON
    updated_at TEXT NOT NULL        -- when it last changed (UTC)
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,           -- small values proki remembers, e.g. the base quota
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tracking (
    app_hash TEXT PRIMARY KEY,  -- sha256 of the app name
    app TEXT,                   -- the name, kept only for apps the user chose to track
    decision TEXT NOT NULL,     -- 'track' or 'never'
    set_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signal_history (  -- persisted signals (signals/base.py)
    name TEXT NOT NULL,
    t TEXT NOT NULL,            -- UTC, ISO
    value TEXT,                 -- JSON
    PRIMARY KEY (name, t)
);
"""


@dataclass(frozen=True)
class Classification:
    category: Category
    source: str  # 'user' or 'openjev'
    confidence: float | None
    confirmed: bool = False  # the user accepted openjev's answer


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(categories)")}
        for column, kind in [("confidence", "REAL"), ("confirmed_at", "TEXT")]:
            if column not in columns:  # databases created by older versions
                self._db.execute(f"ALTER TABLE categories ADD COLUMN {column} {kind}")
        if "reviewed" not in {row[1] for row in self._db.execute("PRAGMA table_info(notes)")}:
            self._db.execute("ALTER TABLE notes ADD COLUMN reviewed INTEGER DEFAULT 0")
        absence_columns = {row[1] for row in self._db.execute("PRAGMA table_info(absences)")}
        for column, kind in [("note", "TEXT"), ("confidence", "REAL")]:
            if column not in absence_columns:
                self._db.execute(f"ALTER TABLE absences ADD COLUMN {column} {kind}")
        backlog_columns = {row[1] for row in self._db.execute("PRAGMA table_info(backlog)")}
        for column, kind in [("jev_offline", "REAL"), ("offline", "INTEGER"),
                             ("source_app", "TEXT"), ("source_title", "TEXT"), ("source_url", "TEXT")]:
            if column not in backlog_columns:  # databases created by older versions
                self._db.execute(f"ALTER TABLE backlog ADD COLUMN {column} {kind}")
        if "group_id" not in {row[1] for row in self._db.execute("PRAGMA table_info(sessions)")}:
            self._db.execute("ALTER TABLE sessions ADD COLUMN group_id INTEGER")
        if "ended_by" not in {row[1] for row in self._db.execute("PRAGMA table_info(sessions)")}:
            self._db.execute("ALTER TABLE sessions ADD COLUMN ended_by TEXT")
        self._migrate_todos()
        self._normalize_minutes()

    def log_nudge(self, finding: Finding, shown_at: datetime) -> int:
        cur = self._db.execute(
            "INSERT INTO nudges (shown_at, rule, message) VALUES (?, ?, ?)",
            (shown_at.isoformat(), finding.rule, finding.message),
        )
        self._db.commit()
        return cur.lastrowid

    def set_response(self, nudge_id: int, response: str) -> None:
        self._db.execute("UPDATE nudges SET response = ? WHERE id = ?", (response, nudge_id))
        self._db.commit()

    def get_category(self, key: str) -> Category | None:
        row = self._db.execute("SELECT category FROM categories WHERE key = ?", (key,)).fetchone()
        return Category(row[0]) if row else None

    def get_classification(self, key: str) -> Classification | None:
        row = self._db.execute(
            "SELECT category, source, confidence, confirmed_at FROM categories WHERE key = ?", (key,)
        ).fetchone()
        return Classification(Category(row[0]), row[1], row[2], row[3] is not None) if row else None

    def confirm_category(self, key: str, confirmed_at: datetime) -> None:
        self._db.execute(
            "UPDATE categories SET confirmed_at = ? WHERE key = ?", (confirmed_at.isoformat(), key)
        )
        self._db.commit()

    def set_category(
        self,
        key: str,
        category: Category,
        source: str,
        set_at: datetime,
        confidence: float | None = None,
    ) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO categories (key, category, source, set_at, confidence)"
            " VALUES (?, ?, ?, ?, ?)",
            (key, category.value, source, set_at.isoformat(), confidence),
        )
        self._db.commit()

    def start_experiment(self, key: str, started: date) -> int:
        cur = self._db.execute("INSERT INTO experiments (key, started, status) VALUES (?, ?, 'running')",
                               (key, started.isoformat()))
        self._db.commit()
        return cur.lastrowid

    def experiments(self, statuses: tuple[str, ...] = ("running", "quit")) -> list:
        from proki.legacy.core.experiment import Experiment

        marks = ", ".join("?" * len(statuses))
        rows = self._db.execute(f"SELECT id, key, started, status, slips FROM experiments WHERE status IN ({marks})",
                                statuses).fetchall()
        return [Experiment(i, k, date.fromisoformat(s), st, n) for i, k, s, st, n in rows]

    def add_slip(self, experiment_id: int) -> None:
        self._db.execute("UPDATE experiments SET slips = slips + 1 WHERE id = ?", (experiment_id,))
        self._db.commit()

    def end_experiment(self, experiment_id: int, status: str, better_with_it: bool | None,
                       anyone_cared: bool | None, now: datetime) -> None:
        self._db.execute(
            "UPDATE experiments SET status = ?, better_with_it = ?, anyone_cared = ?, ended_at = ? WHERE id = ?",
            (status, better_with_it, anyone_cared, now.isoformat(), experiment_id))
        self._db.commit()

    def set_verdict(self, key: str, verdict: str, group_id: int | None, minutes_then: float, now: datetime) -> None:
        self._db.execute("INSERT OR REPLACE INTO tool_verdicts VALUES (?, ?, ?, ?, ?)",
                         (key, verdict, group_id, minutes_then, now.isoformat()))
        self._db.commit()

    def verdicts(self) -> dict[str, tuple[str, int | None, float]]:
        """key → (verdict, goal group, minutes in the week it was judged)."""
        return {k: (v, g, m) for k, v, g, m in self._db.execute(
            "SELECT key, verdict, group_id, minutes_then FROM tool_verdicts")}

    def note_sources(self, since: datetime) -> list[tuple[str | None, str | None, bool]]:
        """(source url, source app, became a task?) of notes since `since`."""
        return [(u, a, t is not None) for u, a, t in self._db.execute(
            "SELECT source_url, source_app, task_id FROM notes WHERE created_at >= ?",
            (since.astimezone(timezone.utc).isoformat(),))]

    def take_old_kinds(self) -> list[tuple[str, str, str, str]]:
        """The kinds stored per app or website before the label registry (core/labels.py):
        (key, kind, source, set_at). The table is dropped: they live in the registry now."""
        exists = self._db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'site_kinds'").fetchone()
        if not exists:
            return []
        rows = [(r[0], r[1], r[2], r[3]) for r in self._db.execute("SELECT key, kind, source, set_at FROM site_kinds")]
        self._db.execute("DROP TABLE site_kinds")
        self._db.commit()
        return rows

    def all_categories(self) -> list[tuple[str, Category, str]]:
        rows = self._db.execute("SELECT key, category, source FROM categories ORDER BY key").fetchall()
        return [(key, Category(category), source) for key, category, source in rows]

    def set_tracking(self, app: str, track: bool, set_at: datetime) -> None:
        """Remember the user's choice. For 'never', only a hash of the name is kept."""
        self._db.execute(
            "INSERT OR REPLACE INTO tracking (app_hash, app, decision, set_at) VALUES (?, ?, ?, ?)",
            (_hash(app), app if track else None, "track" if track else "never", set_at.isoformat()),
        )
        self._db.commit()

    def get_tracking(self, app: str) -> str | None:
        row = self._db.execute("SELECT decision FROM tracking WHERE app_hash = ?", (_hash(app),)).fetchone()
        return row[0] if row else None

    def tracked_apps(self) -> list[str]:
        rows = self._db.execute("SELECT app FROM tracking WHERE decision = 'track' ORDER BY app").fetchall()
        return [app for (app,) in rows]

    def add_rating(
        self, asked_at: datetime, answered_at: datetime, rating: int | None, source: str, snapshot: dict
    ) -> None:
        self._db.execute(
            "INSERT INTO ratings (asked_at, answered_at, rating, source, snapshot) VALUES (?, ?, ?, ?, ?)",
            (asked_at.isoformat(), answered_at.isoformat(), rating, source, json.dumps(snapshot)),
        )
        self._db.commit()

    def ratings(self) -> list[Rating]:
        rows = self._db.execute(
            "SELECT asked_at, answered_at, rating, source, snapshot FROM ratings ORDER BY answered_at"
        ).fetchall()
        return [
            Rating(datetime.fromisoformat(a), datetime.fromisoformat(b), r, src, json.loads(snap or "{}"))
            for a, b, r, src, snap in rows
        ]

    def save_minutes(self, entries: list) -> None:
        self._db.executemany(
            "INSERT OR REPLACE INTO focus_minutes (minute, intensity, activity) VALUES (?, ?, ?)",
            # always UTC: minutes are compared as text, which is only correct with one offset
            [(e.minute.astimezone(timezone.utc).isoformat(), e.intensity, e.activity) for e in entries],
        )
        self._db.commit()

    def minutes(self, start: datetime, end: datetime) -> list:
        from proki.legacy.metrics.ledger import MinuteEntry

        rows = self._db.execute(
            "SELECT minute, intensity, activity FROM focus_minutes WHERE minute >= ? AND minute < ? ORDER BY minute",
            (start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()),
        ).fetchall()
        return [MinuteEntry(datetime.fromisoformat(m), i, a) for m, i, a in rows]

    def last_minute(self) -> datetime | None:
        row = self._db.execute("SELECT MAX(minute) FROM focus_minutes").fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def start_session(self, started_at: datetime) -> int:
        cur = self._db.execute("INSERT INTO sessions (started_at) VALUES (?)", (started_at.isoformat(),))
        self._db.commit()
        return cur.lastrowid

    def set_running_session_group(self, group_id: int | None) -> None:
        self._db.execute("UPDATE sessions SET group_id = ? WHERE ended_at IS NULL", (group_id,))
        self._db.commit()

    def add_weekly_review(self, week: date, now: datetime, answer: str | None) -> None:
        self._db.execute("INSERT OR REPLACE INTO weekly_reviews (week, done_at, answer) VALUES (?, ?, ?)",
                         (week.isoformat(), now.isoformat(), answer))
        self._db.commit()

    def last_weekly_review(self) -> tuple[date, str | None] | None:
        """(week reviewed, answer) of the latest review."""
        row = self._db.execute("SELECT week, answer FROM weekly_reviews ORDER BY week DESC LIMIT 1").fetchone()
        return (date.fromisoformat(row[0]), row[1]) if row else None

    def running_session(self) -> tuple[int, datetime] | None:
        row = self._db.execute(
            "SELECT id, started_at FROM sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return (row[0], datetime.fromisoformat(row[1])) if row else None

    def end_session(self, session_id: int, ended_at: datetime, counts: dict[str, int], ended_by: str) -> None:
        self._db.execute(
            "UPDATE sessions SET ended_at = ?, pokes = ?, asked_done = ?, wrap_ups = ?, alarms = ?, ended_by = ?"
            " WHERE id = ?",
            (ended_at.isoformat(), counts.get("poke", 0), counts.get("ask_done", 0),
             counts.get("wrap_up", 0), counts.get("alarm", 0), ended_by, session_id),
        )
        self._db.commit()

    def save_plan(self, day: date, block_start: time, made_at: datetime) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO plans (day, block_start, made_at) VALUES (?, ?, ?)",
            (day.isoformat(), block_start.strftime("%H:%M"), made_at.isoformat()),
        )
        self._db.commit()

    def get_plan(self, day: date):
        from proki.legacy.core.schedule import Plan

        row = self._db.execute("SELECT block_start FROM plans WHERE day = ?", (day.isoformat(),)).fetchone()
        return Plan(day, time.fromisoformat(row[0])) if row else None

    def log_block(self, day: date, action: str, at: datetime) -> None:
        self._db.execute("INSERT INTO block_log (day, action, at) VALUES (?, ?, ?)", (day.isoformat(), action, at.isoformat()))
        self._db.commit()

    def block_actions(self, day: date) -> set[str]:
        return {a for (a,) in self._db.execute("SELECT action FROM block_log WHERE day = ?", (day.isoformat(),))}

    def sessions_between(self, start: datetime, end: datetime) -> list[tuple]:
        """(started_at, ended_at or None, pokes, ended_by, group_id) for sessions started in [start, end)."""
        rows = self._db.execute(
            "SELECT started_at, ended_at, pokes, ended_by, group_id FROM sessions WHERE started_at >= ? AND started_at < ?"
            " ORDER BY started_at",
            (start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()),
        ).fetchall()
        return [
            (datetime.fromisoformat(a), datetime.fromisoformat(b) if b else None, pokes or 0, by, group)
            for a, b, pokes, by, group in rows
        ]

    def add_group(self, name: str, priority: str, now: datetime) -> int:
        row = self._db.execute("SELECT id FROM goal_groups WHERE name = ?", (name,)).fetchone()
        if row:
            return row[0]
        cur = self._db.execute(
            "INSERT INTO goal_groups (name, priority, created_at) VALUES (?, ?, ?)", (name, priority, now.isoformat())
        )
        self._db.commit()
        return cur.lastrowid

    def groups(self) -> list:
        from proki.legacy.core.backlog import Group

        return [Group(i, n, p) for i, n, p in self._db.execute("SELECT id, name, priority FROM goal_groups ORDER BY name")]

    def set_group_priority(self, group_id: int, priority: str) -> None:
        self._db.execute("UPDATE goal_groups SET priority = ? WHERE id = ?", (priority, group_id))
        self._db.commit()

    def add_task(
        self, group_id: int | None, title: str, description: str, deadline: date | None, estimate: int,
        now: datetime, parent_id: int | None = None, assessment=None,
    ) -> int:
        (last,) = self._db.execute("SELECT COALESCE(MAX(position), 0) FROM backlog").fetchone()
        cur = self._db.execute(
            "INSERT INTO backlog (group_id, parent_id, title, description, deadline, estimate, kind, jev_minutes,"
            " jev_specific, jev_offline, position, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (group_id, parent_id, title, description, deadline.isoformat() if deadline else None, estimate,
             assessment.kind if assessment else None, assessment.minutes if assessment else None,
             assessment.specific if assessment else None, assessment.offline if assessment else None,
             last + 1, now.isoformat()),
        )
        self._db.commit()
        return cur.lastrowid

    def update_task(self, task_id: int, **fields) -> None:
        allowed = {"group_id", "title", "description", "deadline", "estimate", "kind", "jev_minutes", "jev_specific",
                   "jev_offline", "offline", "source_app", "source_title", "source_url"}
        if not fields or not set(fields) <= allowed:
            raise ValueError(f"can't update {set(fields) - allowed}")
        if isinstance(fields.get("deadline"), date):
            fields["deadline"] = fields["deadline"].isoformat()
        assignments = ", ".join(f"{k} = ?" for k in fields)
        self._db.execute(f"UPDATE backlog SET {assignments} WHERE id = ?", (*fields.values(), task_id))
        self._db.commit()

    def tasks(self, include_closed: bool = False) -> list:
        from proki.legacy.core.backlog import Task

        where = "" if include_closed else "WHERE status = 'open'"
        rows = self._db.execute(
            "SELECT id, group_id, parent_id, title, description, deadline, estimate, kind, status, position,"
            f" offline, jev_offline FROM backlog {where} ORDER BY position"
        ).fetchall()
        return [
            Task(i, g, par, t, d or "", date.fromisoformat(dl) if dl else None, est, k, st, pos,
                 None if off is None else bool(off), jo)
            for i, g, par, t, d, dl, est, k, st, pos, off, jo in rows
        ]

    def set_task_status(self, task_id: int, status: str, at: datetime) -> None:
        self._db.execute(
            "UPDATE backlog SET status = ?, done_at = ? WHERE id = ?",
            (status, at.astimezone(timezone.utc).isoformat() if status != "open" else None, task_id),
        )
        self._db.commit()

    def tasks_done_between(self, start: datetime, end: datetime) -> int:
        (n,) = self._db.execute(
            "SELECT COUNT(*) FROM backlog WHERE status = 'done' AND done_at >= ? AND done_at < ?",
            (start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()),
        ).fetchone()
        return n

    def add_absence(self, start: datetime, end: datetime, activity: str | None, source: str) -> int:
        cur = self._db.execute(
            "INSERT INTO absences (start, end, activity, source) VALUES (?, ?, ?, ?)",
            (start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat(), activity, source),
        )
        self._db.commit()
        return cur.lastrowid

    def set_absence_activity(self, absence_id: int, activity: str | None, source: str,
                             note: str | None = None, confidence: float | None = None) -> None:
        self._db.execute(
            "UPDATE absences SET activity = ?, source = ?, note = COALESCE(?, note), confidence = ? WHERE id = ?",
            (activity, source, note, confidence, absence_id),
        )
        self._db.commit()

    def absence_notes(self) -> list[tuple[str, str | None, str]]:
        """(typed text, activity, source) of the answered absences."""
        return self._db.execute("SELECT note, activity, source FROM absences WHERE note IS NOT NULL ORDER BY start").fetchall()

    def absences(self) -> list[tuple[datetime, datetime, str | None, str]]:
        rows = self._db.execute("SELECT start, end, activity, source FROM absences ORDER BY start").fetchall()
        return [(datetime.fromisoformat(a), datetime.fromisoformat(b), act, src) for a, b, act, src in rows]

    def add_note(self, text: str, source, now: datetime) -> int:
        """`source`: core.capture.Source, or None."""
        cur = self._db.execute(
            "INSERT INTO notes (created_at, text, category, source_app, source_title, source_url) VALUES (?, ?, ?, ?, ?, ?)",
            (now.astimezone(timezone.utc).isoformat(), text,
             source.category.value if source and source.category else None,
             source.app if source else None, source.title if source else None, source.url if source else None),
        )
        self._db.commit()
        return cur.lastrowid

    def link_note(self, note_id: int, task_id: int) -> None:
        self._db.execute("UPDATE notes SET task_id = ? WHERE id = ?", (task_id, note_id))
        self._db.commit()

    def notes(self) -> list[tuple[datetime, str, str | None, int | None]]:
        """(created_at, text, source url or app, task id), oldest first."""
        rows = self._db.execute(
            "SELECT created_at, text, COALESCE(source_url, source_app), task_id FROM notes ORDER BY created_at"
        ).fetchall()
        return [(datetime.fromisoformat(c), t, src, task) for c, t, src, task in rows]

    def notes_to_review(self, until: datetime) -> list[tuple[int, str, str | None]]:
        """(id, text, source url or app) of notes before `until` not yet reviewed nor made a task."""
        return self._db.execute(
            "SELECT id, text, COALESCE(source_url, source_app) FROM notes"
            " WHERE reviewed = 0 AND task_id IS NULL AND created_at < ? ORDER BY created_at",
            (until.astimezone(timezone.utc).isoformat(),),
        ).fetchall()

    def mark_note_reviewed(self, note_id: int) -> None:
        self._db.execute("UPDATE notes SET reviewed = 1 WHERE id = ?", (note_id,))
        self._db.commit()

    def task_sources(self) -> list:
        """(task id, core.capture.Source) for open tasks that came from a tab or window."""
        from proki.legacy.core.capture import Source

        rows = self._db.execute(
            "SELECT id, source_app, COALESCE(source_title, ''), source_url FROM backlog"
            " WHERE status = 'open' AND source_app IS NOT NULL"
        ).fetchall()
        return [(i, Source(app, title, url, "")) for i, app, title, url in rows]

    def mark_present(self, start: datetime, end: datetime, activity: str) -> int:
        """Record [start, end) as time at the computer (the user said they weren't away), not as away."""
        from proki.legacy.metrics.ledger import MINUTE, MinuteEntry, minute_floor

        entries, minute = [], minute_floor(start)
        while minute + MINUTE <= end:
            entries.append(MinuteEntry(minute, None, activity))
            minute += MINUTE
        self.save_minutes(entries)
        return len(entries)

    def mark_offline_work(self, start: datetime, end: datetime) -> int:
        """Record [start, end) as deep work done offline (it shows as away otherwise). Returns minutes."""
        from proki.legacy.metrics.ledger import MINUTE, MinuteEntry, minute_floor

        entries, minute = [], minute_floor(start)
        while minute + MINUTE <= end:
            entries.append(MinuteEntry(minute, 1.0, "offline"))
            minute += MINUTE
        self.save_minutes(entries)
        return len(entries)

    def get_state(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_state(self, key: str, value: str) -> None:
        self._db.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value))
        self._db.commit()

    def _normalize_minutes(self) -> None:
        """Rewrite minutes saved with a local offset in UTC, merging duplicates (once)."""
        if self.get_state("minutes_utc"):
            return
        rows = self._db.execute("SELECT minute, intensity, activity FROM focus_minutes ORDER BY minute").fetchall()
        self._db.execute("DELETE FROM focus_minutes")
        self._db.executemany(
            "INSERT OR REPLACE INTO focus_minutes (minute, intensity, activity) VALUES (?, ?, ?)",
            [(datetime.fromisoformat(m).astimezone(timezone.utc).isoformat(), i, a) for m, i, a in rows],
        )
        self.set_state("minutes_utc", datetime.now(timezone.utc).isoformat())

    def _migrate_todos(self) -> None:
        """Open items from the earlier day-plan to-do list become backlog tasks (once)."""
        if self.get_state("todos_migrated"):
            return
        now = datetime.now(timezone.utc)
        for _, day, text, kind, minutes in self._db.execute(
            "SELECT id, day, text, kind, minutes FROM todos WHERE status = 'open' ORDER BY day, position"
        ).fetchall():
            self._db.execute(
                "INSERT INTO backlog (title, deadline, estimate, kind, position, created_at) VALUES (?, ?, ?, ?, "
                "(SELECT COALESCE(MAX(position), 0) + 1 FROM backlog), ?)",
                (text, day, minutes or 30, kind, now.isoformat()),
            )
        self.set_state("todos_migrated", now.isoformat())

    def forget_tracking(self, app: str) -> None:
        self._db.execute("DELETE FROM tracking WHERE app_hash = ?", (_hash(app),))
        self._db.commit()


@dataclass(frozen=True)
class Rating:
    asked_at: datetime
    answered_at: datetime
    rating: int | None  # None = skipped
    source: str
    snapshot: dict


def _hash(app: str) -> str:
    return hashlib.sha256(app.encode()).hexdigest()


class SignalHistory:
    """Where persisted signals keep their history (the `Storage` of signals/base.py)."""

    def __init__(self, store: Store):
        self._db = store._db

    def load(self, name: str, since: datetime) -> list[tuple[datetime, Any]]:
        rows = self._db.execute(
            "SELECT t, value FROM signal_history WHERE name = ? AND t > ? ORDER BY t",
            (name, since.astimezone(timezone.utc).isoformat()))
        return [(datetime.fromisoformat(t), json.loads(v)) for t, v in rows]

    def save(self, name: str, t: datetime, value: Any) -> None:
        self._db.execute("INSERT OR REPLACE INTO signal_history (name, t, value) VALUES (?, ?, ?)",
                         (name, t.astimezone(timezone.utc).isoformat(), json.dumps(value)))
        self._db.commit()


class VariableValues:
    """Where variables keep their latest value (the `VariableStore` of
    core/signals/variable.py): a row each in the `variables` table, as JSON."""

    def __init__(self, store: Store):
        self._db = store._db

    def load(self, name: str) -> Any:
        row = self._db.execute("SELECT value FROM variables WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        return json.loads(row[0])

    def save(self, name: str, value: Any) -> None:
        self._db.execute("INSERT OR REPLACE INTO variables (name, value, updated_at) VALUES (?, ?, ?)",
                         (name, json.dumps(value), datetime.now(timezone.utc).isoformat()))
        self._db.commit()
