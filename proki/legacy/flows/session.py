"""Focus sessions in the running app: start / stop, each tick's step (pokes, "done?",
wrap-up, away alarm, auto-end), offline work, and the session variants (sprint,
thinking walk, grand gesture). The rules of a session live in core/session.py;
low focus in rules/focus.py.

The flow owns the session's state; it reaches the rest of the app (tray, popup,
store, tasks, other flows) through `app`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from proki.legacy.core.backlog import minutes_text
from proki.legacy.core.events import Segment
from proki.legacy.core.grand import grand_session
from proki.legacy.core.meditation import is_walk
from proki.legacy.core.offline import OfflineWork
from proki.legacy.core.session import Action, FocusSession
from proki.legacy.core.sprint import Sprint
from proki.core.rules import Rule
from proki.legacy.flows.base import Flow, FlowContext, config_rules
from proki.legacy.metrics.history import deep_minutes
from proki.legacy.ui.sound import Alarm

NO_DATA_AFTER = timedelta(minutes=2)  # no activity recorded for this long = away (asleep, or ActivityWatch off)


class SessionFlow(Flow):
    name = "session"

    def __init__(self, app):
        self.app = app
        config = app.config
        self.alarm = Alarm(config.alarm_sound, config.alarm_volume)
        self.session: FocusSession | None = None
        self.session_id: int | None = None
        self.session_checked: datetime | None = None  # last time the session was stepped
        self.offline = OfflineWork()  # away time on an offline task
        self.grand: str | None = None  # the grand gesture's one thing, while one runs
        self.sprint: Sprint | None = None
        running = app.store.running_session()  # resume a session that was running when proki stopped
        if running:
            self.session_id, started = running
            self.session = FocusSession(started, config.session)

    def tick(self, ctx: FlowContext) -> None:
        self.step_session(ctx.segments, ctx.now)

    def toggle_session(self) -> None:
        if self.session:
            self.stop_session(datetime.now(timezone.utc))
        else:
            self.app.tasks.request_session(self.start_session)  # offers to add a task if the list is empty

    def start_session(self, offer_task: bool = True, params=None) -> None:
        """`params`: session rules other than the usual (a grand gesture)."""
        if self.session:
            return
        now = datetime.now(timezone.utc)
        self.session_id = self.app.store.start_session(now)
        self.session = FocusSession(now, params or self.app.config.session)
        self.session_checked = now
        self.app.tray.set_session(0)
        if offer_task:
            self.app.tasks.start_session()  # pick a goal group, hand over its first task

    def start_grand(self, what: str, hours: int) -> None:
        """A grand gesture: one long session on one thing, relaxed rules (core/grand.py)."""
        self.stop_session(datetime.now(timezone.utc), quiet=True)
        self.start_session(params=grand_session(self.app.config.session, hours))
        self.grand = what

    def start_sprint(self, task, title: str, minutes: int) -> None:
        """A sprint: a session on one task with a tight deadline, counting down (core/sprint.py)."""
        now = datetime.now(timezone.utc)
        self.stop_session(now, quiet=True)
        self.start_session(offer_task=False)
        if task is not None:
            self.app.tasks._set_current(task)
        self.sprint = Sprint(title, task.id if task else None, now + timedelta(minutes=minutes))
        self.app.tray.set_session(0, f"{minutes} min left")

    def step_sprint(self, now: datetime) -> bool:
        """Countdown in the tray; at the deadline, "time's up" (rings). True while it's asking."""
        if self.sprint is None:
            return False
        left = int(self.sprint.left(now).total_seconds() // 60) + (1 if self.sprint.left(now).seconds % 60 else 0)
        self.app.tray.set_session(int(self.session.elapsed(now).total_seconds() // 60),
                              f"{left} min left · {self.sprint.title}")
        if not self.sprint.due(now):
            return self.sprint.asked
        self.sprint.asked = True
        self.alarm.start()
        self.app.sprint_prompts.times_up(self.sprint.title, self.on_sprint_answer)
        return True

    def on_sprint_answer(self, answer: str) -> None:
        self.alarm.stop()
        now = datetime.now(timezone.utc)
        if answer == "more" and self.sprint is not None:
            self.sprint.extend(now, self.app.sprint_prompts.params.extension)
            return
        if answer == "done" and self.sprint is not None and self.sprint.task_id is not None:
            self.app.store.set_task_status(self.sprint.task_id, "done", now)
            self.app.tasks.refresh()
        self.stop_session(now)

    def start_walk(self, walk) -> None:
        """A thinking walk: a session on the walk as an offline task (core/meditation.py)."""
        self.stop_session(datetime.now(timezone.utc), quiet=True)
        self.start_session(offer_task=False)
        self.app.tasks.current_task = walk  # not in the backlog; being away is the work

    def stop_session(self, now: datetime, ended_by: str = "user", quiet: bool = False) -> None:
        """`quiet`: no follow-up prompts (wrap-up reminder, thinking walk)."""
        if not self.session:
            return
        counts = {action.value: n for action, n in self.session.counts.items()}
        started, walking = self.session.started_at, is_walk(self.app.tasks.current_task)
        grand, self.grand = self.grand, None
        self.sprint = None
        self.app.store.end_session(self.session_id, now, counts, ended_by)
        self.session = self.session_id = None
        self.offline.reset()
        self.app.tasks.end_session()
        self.alarm.stop()
        self.app.tray.set_session(None)
        if self.app.popup.isVisible():
            self.app.popup.hide()
        if grand is not None and not quiet:  # the grand gesture is over: what got done?
            self.app.grand_prompts.finished(grand, deep_minutes(self.app.store.minutes(started, now), started, now,
                                                            self.app.config.focus.deep_threshold))
            return
        if ended_by == "user" and not quiet:
            self.app.shutdown.session_ended(now)  # near the usual off time: wrap up the day?
            if not walking:  # after a good session, sometimes: a thinking walk?
                deep = deep_minutes(self.app.store.minutes(started, now), started, now, self.app.config.focus.deep_threshold)
                self.app.meditation.after_session(deep)

    def step_session(self, segments: list[Segment], now: datetime) -> None:
        if not self.session:
            return
        last_check, self.session_checked = self.session_checked, now
        task = self.app.tasks.current_task
        slept = last_check and now - last_check >= self.session.params.away_end_after
        if slept and not (task and task.offline):
            # proki didn't run for a while (the Mac slept): the session ended back then
            self.stop_session(last_check, ended_by="away")
            return
        minutes = int(self.session.elapsed(now).total_seconds() // 60)
        self.app.tray.set_session(minutes)
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
        low = Rule.vote(config_rules(self.name, "session_low_focus", "session_not_recovering"))  # config.json
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
            if self.app.config.sound_on_low_focus:
                self.alarm.start()  # rings until focus is back or the popup is answered
            message = "Your focus is slipping. Come back to what you were working on?"
            options = [("Back on it", "ok"), ("Stop session", "stop")]
        # session messages take priority over any other open question
        self.app.popup.ask(message, self.on_session_answer, options)

    def step_offline_work(self, task, away_since: datetime | None, now: datetime) -> tuple[bool, datetime | None]:
        """Away during an offline task is the work itself (core/offline.py); records it and asks when back."""
        step = self.offline.step(task, away_since, now)
        if step.offline and step.credit is None and self.alarm.ringing:
            self.alarm.stop()
        if step.credit:
            worked = self.app.store.mark_offline_work(*step.credit)
            if step.back:
                self.app.routines.offline_work_done()  # no "what was that?" about it
                if is_walk(task):
                    self.stop_session(step.credit[1], ended_by="walk")  # the walk is over
                    self.app.meditation.back(task, worked)
                elif task:
                    self.app.popup.ask(
                        f"Welcome back: {minutes_text(worked)} of offline work on “{task.title}”. Is it done?",
                        lambda a: self.app.tasks.task_done() if a == "done" else None,
                        [("Done", "done"), ("Not yet", "no")],
                    )
        return step.offline, step.away_since

    def on_session_answer(self, response: str) -> None:
        self.alarm.stop()
        if response == "stop":
            self.stop_session(datetime.now(timezone.utc))
