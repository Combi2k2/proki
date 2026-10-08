"""The shutdown ritual (the legacy shutdown flow's): today's notes → wrap-up in your own
words → tomorrow → "shutdown complete".

When it's offered (core/shutdown.py, core/offtime.py):
- focus low × close to the shutdown time (checked every tick);
- a session ends near the usual off time;
- the wrap-up alarm, if the user set one: offered when wrap-ups were often missed.

The steps run one after another whenever no popup or task window is open, so
cancelling a task form just moves on to the next step.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Callable

from proki.core.rules import Rule
from proki.core.ui import Alarm, Ui
from proki.legacy.core.offtime import OffTimeParams, near, off_time, often_missed
from proki.legacy.core.shutdown import ShutdownParams, workday
from proki.legacy.core.store import Store
from proki.legacy.flows.base import FlowContext
from proki.legacy.metrics.day import day_bounds
from proki.legacy.rules.base import Cadence
from proki.programs.base import Ritual, rules, variable

RULES = ("shutdown_window", "shutdown_time", "shutdown_not_focused", "shutdown_low_focus")  # the config's


class Shutdown(Ritual):
    def __init__(self, store: Store, params: ShutdownParams, day_starts: time, wrap_up: Callable[[datetime], str],
                 new_task: Callable[..., None] = lambda **kwargs: None,
                 weekly_review: Callable[[datetime], str | None] = lambda now: None,
                 save_review: Callable[[datetime, str | None], None] = lambda now, answer: None,
                 tools_check: Callable[[datetime], None] = lambda now: None,
                 off_params: OffTimeParams = OffTimeParams()):
        super().__init__("shutdown")
        self.new_task = new_task  # the task form (the UI's): new_task(title=..., on_added=...)
        self.weekly_review = weekly_review  # the week's facts when a weekly review is due, else None
        self.save_review = save_review
        self.tools_check = tools_check  # the craftsman question, once per weekly review
        self.store = store
        self.alarm = Alarm("shutdown")  # its own, for the wrap-up alarm
        self.cadence = Cadence(params.check_every)
        self.off_params = off_params
        self._stats: tuple[datetime, time | None, list[bool]] | None = None  # (computed at, off time, done by day)
        self.params = params
        self.day_starts = day_starts
        self.wrap_up = wrap_up  # today's deep work and tomorrow's start, for the last step
        self.snoozed_until: datetime | None = None
        self.stage: str | None = None  # 'notes', 'mind', 'week', 'week_question', 'tomorrow' while the ritual runs
        self.notes: list[tuple[int, str, str | None]] = []
        self.mind_asked = False

    def _key(self, now: datetime) -> str:
        return f"shutdown:{day_bounds(now, self.day_starts)[0].isoformat()}"

    def done_today(self, now: datetime) -> bool:
        """The workday is shut down (or the ritual is under way): no more work questions today."""
        return self.store.get_state(self._key(now)) is not None

    def _busy(self) -> bool:
        return Ui.busy()  # a question waiting, or a window of the app's (the task form)

    def advance(self, now: datetime, in_session: bool) -> None:
        """Every poll (a few seconds): move the running ritual on (paused during a session)."""
        if self.stage is not None and not in_session and not self._busy():
            self._next(now)

    def check(self, now: datetime, active: bool, in_session: bool, intensity: float | None) -> None:
        """Every tick: offer the shutdown when the workday seems to be ending."""
        day = day_bounds(now, self.day_starts)[0]
        if (self._busy() or self.stage is not None or not active or in_session or not workday(day, self.params)
                or self.done_today(now)):
            return
        if self._alarm_due(now, day):
            self.store.set_state(f"shutdown_alarm_rang:{day.isoformat()}", now.isoformat())
            self.alarm.start()
            self.offer(now, "Your wrap-up alarm: time to shut down the workday.")
            return
        if self.snoozed_until and now < self.snoozed_until:
            return
        offer = rules(*RULES)
        if all(rule.chance() > 0 for rule in offer) and self.cadence.due(now) and Rule.vote(offer):
            self.offer(now)
            return
        self._maybe_offer_alarm(now)

    def session_ended(self, now: datetime) -> None:
        """A session just ended: near the usual off time, remind the user to wrap up."""
        day = day_bounds(now, self.day_starts)[0]
        if (workday(day, self.params) and not self.done_today(now) and self.stage is None
                and near(now, self._off_time(now), self.off_params)):
            self.offer(now, "Session done, and it's about when you usually stop. Wrap up the day before you go?")

    def offer(self, now: datetime, message: str | None = None) -> None:
        Ui.ask(
            message or "Your workday seems to be winding down. Time to shut it down: today's notes, a wrap-up, tomorrow.",
            lambda a: self._offer_answer(a, now),
            [("Start shutdown", "start"), ("Ask later", "later")],
        )

    def _offer_answer(self, answer: str, now: datetime) -> None:
        self.alarm.stop()
        if answer == "start":
            self._start(datetime.now(now.tzinfo))
        else:
            self.snoozed_until = datetime.now(now.tzinfo) + self.params.snooze

    # --- the usual off time and the wrap-up alarm ----------------------------------------------

    def _statistics(self, now: datetime) -> tuple[time | None, list[bool]]:
        """The off time and recent wrap-ups (done?, newest first); recomputed hourly."""
        if self._stats is None or now - self._stats[0] >= timedelta(hours=1):
            stops = [start for start, end, _, _ in self.store.absences() if end - start >= self.off_params.min_absence]
            today = day_bounds(now, self.day_starts)[0]
            done = []
            for back in range(1, 15):
                day = today - timedelta(days=back)
                if workday(day, self.params) and self._proki_ran(day, now):
                    done.append(self.store.get_state(f"shutdown:{day.isoformat()}") == "done")
            self._stats = (now, off_time(stops, self.day_starts, self.off_params), done)
        return self._stats[1], self._stats[2]

    def _proki_ran(self, day: date, now: datetime) -> bool:
        start = datetime.combine(day, self.day_starts, now.astimezone().tzinfo)
        return bool(self.store.minutes(start, start + timedelta(days=1)))

    def _off_time(self, now: datetime) -> time | None:
        return self._statistics(now)[0]

    def _alarm_due(self, now: datetime, day: date) -> bool:
        saved = self.store.get_state("shutdown_alarm")
        if not saved or self.store.get_state(f"shutdown_alarm_rang:{day.isoformat()}"):
            return False
        local = now.astimezone()
        return local >= datetime.combine(day, time.fromisoformat(saved), local.tzinfo)

    def _maybe_offer_alarm(self, now: datetime) -> None:
        if self.store.get_state("shutdown_alarm"):
            return
        off, done = self._statistics(now)
        if off is None or not often_missed(done, self.off_params):
            return
        offered = self.store.get_state("shutdown_alarm_offered")
        if offered and now - datetime.fromisoformat(offered) < self.off_params.offer_every:
            return
        local = now.astimezone()
        off_at = datetime.combine(local.date(), off, local.tzinfo)
        if not off_at - timedelta(minutes=20) <= local <= off_at:
            return
        self.store.set_state("shutdown_alarm_offered", now.isoformat())
        options = []
        for minutes_before in (15, 30):
            t = (off_at - timedelta(minutes=minutes_before)).time().replace(second=0, microsecond=0)
            options.append((f"At {t:%H:%M}", t.strftime("%H:%M")))
        Ui.ask(
            f"You usually stop around {off:%H:%M}, and the wrap-up was missed on "
            f"{sum(1 for d in done[:self.off_params.missed_days] if not d)} of the last {min(len(done), self.off_params.missed_days)} workdays. "
            "Set a daily alarm for your wrap-up?",
            lambda a: self.store.set_state("shutdown_alarm", a) if a != "no" else None,
            options + [("No thanks", "no")],
        )

    def _start(self, now: datetime) -> None:
        self.store.set_state(self._key(now), "started")
        self.notes = self.store.notes_to_review(now)
        self.stage, self.mind_asked = "notes", False
        self._next(now)

    def _next(self, now: datetime) -> None:
        if self.stage == "notes":
            if self.notes:
                note_id, text, source = self.notes.pop(0)
                Ui.ask(
                    f"Today's note: “{text}”" + (f"\n(from {source})" if source else ""),
                    lambda a: self._note_answer(a, note_id, text),
                    [("Make it a task", "task"), ("Keep as note", "keep")],
                )
                return
            self.stage = "mind"
        if self.stage == "mind":
            message = ("Anything else?" if self.mind_asked else
                       "Wrap up your day in your own words: anything still open? Write it down as a task so you can let it go.")
            self.mind_asked = True
            Ui.ask_text(message, self._mind_answer, placeholder="something to do…", skip_label="That's all")
            return
        if self.stage == "week":
            facts = self.weekly_review(now)
            if facts is None:
                self.stage = "tomorrow"
            else:
                self.stage = "week_question"
                Ui.ask("Weekly review\n\n" + facts, lambda _: None, [("Next", "next")])
                return
        if self.stage == "week_question":
            Ui.ask_text("Looking at this week: what will you change next week?", self._week_answer,
                                placeholder="e.g. start the block before checking email", skip_label="Nothing")
            return
        if self.stage == "tools":
            self.stage = "tomorrow"
            self.tools_check(now)  # may show a question; the ritual waits for it
            if self._busy():
                return
        if self.stage == "tomorrow":
            self.stage = None
            Ui.ask(self.wrap_up(now), lambda _: self._complete(now), [("Shutdown complete", "done")])

    def _note_answer(self, answer: str, note_id: int, text: str) -> None:
        self.store.mark_note_reviewed(note_id)
        if answer == "task":
            self.new_task(title=text, on_added=lambda task_id: self.store.link_note(note_id, task_id))

    def _mind_answer(self, text: str | None) -> None:
        if text is None:
            self.stage = "week"
        else:
            self.new_task(title=text)  # after the form: "anything else?"

    def _week_answer(self, text: str | None) -> None:
        self.save_review(datetime.now().astimezone(), text)
        self.stage = "tools"

    def _complete(self, now: datetime) -> None:
        self.store.set_state(self._key(now), "done")


    def tick(self, ctx: FlowContext) -> None:
        self.check(ctx.now, ctx.active, ctx.in_session, intensity=ctx.values["focus_5m"] if ctx.values else None)
        variable("shutdown_done", False).set(self.done_today(ctx.now))

    def watch(self, ctx: FlowContext) -> None:
        self.advance(ctx.now, ctx.in_session)

