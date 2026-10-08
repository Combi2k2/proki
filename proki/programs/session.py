"""Focus sessions (the legacy session flow's): start / stop, each cycle's step (pokes,
"done?", wrap-up, away alarm, auto-end), offline work, and the variants (sprint, thinking
walk, grand gesture). A session's rules live in legacy/core/session.py; low focus is the
config's (`session_low_focus`, `session_not_recovering`).

States: idle, focusing. The config sees it through variables: `in_session` (kept here),
and asks for a session or its end by setting `session_requested` /
`session_stop_requested` (a suggestion's "Start session", hub's "Stop session").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from proki.core.rules import Rule
from proki.core.ui import Alarm, Ui
from proki.legacy.core.events import Segment
from proki.legacy.core.grand import grand_session
from proki.legacy.core.meditation import is_walk
from proki.legacy.core.offline import OfflineWork
from proki.legacy.core.session import Action, FocusSession, SessionParams
from proki.legacy.core.sprint import Sprint
from proki.legacy.core.store import Store
from proki.legacy.flows.base import FlowContext
from proki.legacy.metrics.history import deep_minutes
from proki.legacy.core.backlog import minutes_text
from proki.programs.base import Ritual, program, rules, variable

NO_DATA_AFTER = timedelta(minutes=2)  # no activity recorded for this long = away (asleep, or ActivityWatch off)


class Session(Ritual):
    def __init__(self, store: Store, params: SessionParams = SessionParams(), deep_threshold: float = 0.5,
                 sound_on_low_focus: bool = False, sprint_extension: int = 5):
        super().__init__("session", ("idle", "focusing"))
        self.store = store
        self.params = params
        self.deep_threshold = deep_threshold
        self.sound_on_low_focus = sound_on_low_focus
        self.sprint_extension = sprint_extension
        self.alarm = Alarm("session")
        self.session: FocusSession | None = None
        self.session_id: int | None = None
        self.session_checked: datetime | None = None  # last time the session was stepped
        self.offline = OfflineWork()  # away time on an offline task
        self.grand: str | None = None  # the grand gesture's one thing, while one runs
        self.sprint: Sprint | None = None
        running = store.running_session()  # resume a session that was running when proki stopped
        if running:
            self.session_id, started = running
            self.session = FocusSession(started, params)
            self.current = "focusing"
        variable("in_session", False).set(self.session is not None)

    @property
    def plan(self):
        return program("plan")

    def tick(self, ctx: FlowContext) -> None:
        for name, wanted in (("session_requested", True), ("session_stop_requested", False)):
            asked = variable(name, False)
            if asked.value:  # the config asks (a suggestion's answer)
                asked.set(False)
                if wanted:
                    self.request()
                elif not wanted:
                    self.stop_session(datetime.now(timezone.utc))
        self.step_session(ctx.segments, ctx.now)

    def request(self) -> None:
        """Start a session, unless one runs (an empty task list: add a task first?)."""
        if not self.session:
            self.plan.request_session(self.start_session)

    def toggle_session(self) -> None:
        if self.session:
            self.stop_session(datetime.now(timezone.utc))
        else:
            self.plan.request_session(self.start_session)  # offers to add a task if the list is empty

    def start_session(self, offer_task: bool = True, params: SessionParams | None = None) -> None:
        """`params`: session rules other than the usual (a grand gesture)."""
        if self.session:
            return
        now = datetime.now(timezone.utc)
        self.session_id = self.store.start_session(now)
        self.session = FocusSession(now, params or self.params)
        self.session_checked = now
        self.current = "focusing"
        variable("in_session").set(True)
        Ui.session(0)
        if offer_task:
            self.plan.start_session()  # pick a goal group, hand over its first task

    def start_grand(self, what: str, hours: int) -> None:
        """A grand gesture: one long session on one thing, relaxed rules (core/grand.py)."""
        self.stop_session(datetime.now(timezone.utc), quiet=True)
        self.start_session(params=grand_session(self.params, hours))
        self.grand = what

    def start_sprint(self, task, title: str, minutes: int) -> None:
        """A sprint: a session on one task with a tight deadline, counting down (core/sprint.py)."""
        now = datetime.now(timezone.utc)
        self.stop_session(now, quiet=True)
        self.start_session(offer_task=False)
        if task is not None:
            self.plan.use(task)
        self.sprint = Sprint(title, task.id if task else None, now + timedelta(minutes=minutes))
        Ui.session(0, f"{minutes} min left")

    def step_sprint(self, now: datetime) -> bool:
        """Countdown in the tray; at the deadline, "time's up" (rings). True while it's asking."""
        if self.sprint is None:
            return False
        left = int(self.sprint.left(now).total_seconds() // 60) + (1 if self.sprint.left(now).seconds % 60 else 0)
        Ui.session(int(self.session.elapsed(now).total_seconds() // 60), f"{left} min left · {self.sprint.title}")
        if not self.sprint.due(now):
            return self.sprint.asked
        self.sprint.asked = True
        self.alarm.start()
        program("sprint").times_up(self.sprint.title, self.on_sprint_answer)
        return True

    def on_sprint_answer(self, answer: str) -> None:
        self.alarm.stop()
        now = datetime.now(timezone.utc)
        if answer == "more" and self.sprint is not None:
            self.sprint.extend(now, self.sprint_extension)
            return
        if answer == "done" and self.sprint is not None and self.sprint.task_id is not None:
            self.store.set_task_status(self.sprint.task_id, "done", now)
            self.plan.refresh()
        self.stop_session(now)

    def start_walk(self, walk) -> None:
        """A thinking walk: a session on the walk as an offline task (core/meditation.py)."""
        self.stop_session(datetime.now(timezone.utc), quiet=True)
        self.start_session(offer_task=False)
        self.plan.use(walk)  # not in the backlog; being away is the work

    def stop_session(self, now: datetime, ended_by: str = "user", quiet: bool = False) -> None:
        """`quiet`: no follow-up prompts (wrap-up reminder, thinking walk)."""
        if not self.session:
            return
        counts = {action.value: n for action, n in self.session.counts.items()}
        started, walking = self.session.started_at, is_walk(self.plan.current_task)
        grand, self.grand = self.grand, None
        self.sprint = None
        self.store.end_session(self.session_id, now, counts, ended_by)
        self.session = self.session_id = None
        self.current = "idle"
        variable("in_session").set(False)
        self.offline.reset()
        self.plan.end_session()
        self.alarm.stop()
        Ui.session(None)
        Ui.hide()
        deep = lambda: deep_minutes(self.store.minutes(started, now), started, now, self.deep_threshold)
        if grand is not None and not quiet:  # the grand gesture is over: what got done?
            program("grand").finished(grand, deep())
            return
        if ended_by == "user" and not quiet:
            program("shutdown").session_ended(now)  # near the usual off time: wrap up the day?
            if not walking:  # after a good session, sometimes: a thinking walk?
                program("meditation").after_session(deep())

    def step_session(self, segments: list[Segment], now: datetime) -> None:
        if not self.session:
            return
        last_check, self.session_checked = self.session_checked, now
        task = self.plan.current_task
        slept = last_check and now - last_check >= self.session.params.away_end_after
        if slept and not (task and task.offline):
            # proki didn't run for a while (the Mac slept): the session ended back then
            self.stop_session(last_check, ended_by="away")
            return
        minutes = int(self.session.elapsed(now).total_seconds() // 60)
        Ui.session(minutes)
        if self.step_sprint(now):
            return  # time's up is showing: no other session prompts meanwhile
        latest = max(segments, key=lambda s: s.end) if segments else None
        if latest is None or now - latest.end > NO_DATA_AFTER:
            # no recent data: the Mac slept or ActivityWatch stopped; count it as away
            away_since = max(latest.end if latest else self.session.started_at, self.session.started_at)
        else:
            away_since = latest.start if latest.away else None
        if slept and away_since is None:
            away_since = last_check  # the Mac slept during offline work and just woke up: the user is back now
        offline, away_since = self.step_offline_work(task, away_since, now)
        if offline:
            return  # working offline, or just back from it: no focus checks this time
        low = Rule.vote(rules("session_low_focus", "session_not_recovering"))  # the config's
        if away_since is None and not low and self.alarm.ringing:
            self.alarm.stop()  # the user is back, and focused
        action = self.session.step(now, low, away_since)
        if action is Action.NONE:
            return
        if action is Action.END:
            self.stop_session(away_since, ended_by="away")  # the session ended when the user left
            return
        if action is Action.ALARM:
            self.alarm.start()  # loops until the user is back or answers
            away = int((now - away_since).total_seconds() // 60)
            message = f"You've been away for {away} min, and your focus session is still running."
            options = [("I'm back", "ok"), ("Stop session", "stop")]
        elif action is Action.WRAP_UP:
            message = f"{minutes} minutes of focus. Time to wrap up and take a real break."
            options = [("Stop session", "stop"), ("Almost done", "ok")]
        elif action is Action.ASK_DONE:
            message = "Your focus has dropped. Is this session done?"
            options = [("Yes, stop", "stop"), ("No, keep going", "ok")]
        else:
            if self.sound_on_low_focus:
                self.alarm.start()  # rings until focus is back or the popup is answered
            message = "Your focus is slipping. Come back to what you were working on?"
            options = [("Back on it", "ok"), ("Stop session", "stop")]
        Ui.ask(message, self.on_session_answer, options, urgent=True)  # before any other question

    def step_offline_work(self, task, away_since: datetime | None, now: datetime) -> tuple[bool, datetime | None]:
        """Away during an offline task is the work itself (core/offline.py); records it and asks when back."""
        step = self.offline.step(task, away_since, now)
        if step.offline and step.credit is None and self.alarm.ringing:
            self.alarm.stop()
        if step.credit:
            worked = self.store.mark_offline_work(*step.credit)
            if step.back:
                program("routines").offline_work_done()  # no "what was that?" about it
                if is_walk(task):
                    self.stop_session(step.credit[1], ended_by="walk")  # the walk is over
                    program("meditation").back(task, worked)
                elif task:
                    Ui.ask(f"Welcome back: {minutes_text(worked)} of offline work on “{task.title}”. Is it done?",
                           lambda a: self.plan.task_done() if a == "done" else None,
                           [("Done", "done"), ("Not yet", "no")])
        return step.offline, step.away_since

    def on_session_answer(self, response: str) -> None:
        self.alarm.stop()
        if response == "stop":
            self.stop_session(datetime.now(timezone.utc))
