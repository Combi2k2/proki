"""The running daemon: a tray app that polls, analyzes and nudges."""

from __future__ import annotations

import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone

from platformdirs import user_log_path
from PySide6.QtCore import QLockFile, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from proki import platforms
from proki.legacy.config import CONFIG_PATH, DATA_DIR, DB_PATH, LABELS_PATH, JSON_CONFIG_PATH, UNTRACKED, Config
from proki.legacy.core.analyzer import Analyzer
from proki.legacy.core.categories import Categorizer, prepare
from proki.legacy.core.classifier import ClassificationLoop, Question
from proki.legacy.core import labeling
from proki.legacy.core.labels import LabelRegistry, migrate
from proki.legacy.core.collector import Collector
from proki.legacy.core.events import Category, Finding, Level, Segment
from proki.legacy.focus import moment
from proki.legacy.core.sampling import SamplingSchedule
from proki.legacy.metrics.keeper import ScoreKeeper
from proki.legacy.metrics.day import day_bounds, summarize_day
from proki.legacy.core.jev import assess_task, classify_activity, is_todo, still_there, suggest_group, suggest_label
from proki.services.jev import Jev
from proki.legacy.metrics.quota import QuotaKeeper
from proki.legacy.core.policy import NudgePolicy
from proki.legacy.rules.fragmentation import default_rules
from proki.legacy.core.rhythm import Rhythm
from proki.legacy.core.store import SignalHistory, Store, VariableValues
from proki.legacy.flows.experiment import experiment_lines
from proki.legacy.flows.base import FlowContext
from proki.compiler import editable_copy
from proki.core.ui import Ui
from proki.core.ask import Asking
from proki.engine import Engine, serve_jev, serve_llm
from proki.services import nats
from proki.services.supervisor import Supervisor
from proki.utils import find_commands
from proki.legacy.core.sprint import SprintParams
from proki.programs import (Capture, Craftsman, Grand, Meditation, Plan, Reminders, Routines,
                            Session, Shutdown, Sprint, ThirtyDayTest, program, variable)
from proki.programs import Rhythm as RhythmPrompts
from proki.programs.session import NO_DATA_AFTER
from proki.legacy.ui.client import PopupClient
from proki.services.llm import Llm
from proki.core.primitives import Depth, Label, Recording
from proki.core.signals import Stream, Variable
from proki.legacy.core.craftsman import WorthAsking, pick, site_weeks
from proki.legacy.core.association import AssociationParams, contributions, pair_minutes
from proki.legacy.ui.background import Background
from proki.legacy.flows.craftsman import verdict_lines
from proki.legacy.core.backlog import minutes_text
from proki.legacy.core.budget import shallow_share
from proki.legacy.metrics.consistency import ConsistencyParams, consistency
from proki.legacy.core.shutdown import workday
from proki.legacy.core.weekly import WeekFacts, review_due, review_text, week_start
from proki.legacy.flows.tasks import TasksFlow
from proki.services import aw
from proki.legacy.ui.board import budget_lines, consistency_lines, rhythm_lines, scoreboard_lines, sleep_lines, task_lines
from proki.legacy.ui.popup import Popup
from proki.legacy.ui.sound import Alarm
from proki.legacy.ui.tray import Tray

FAST_POLL_MS = 2_000  # how often to look at what's in focus right now (cheap: latest events only)
RATING_OPTIONS = [(c.value.capitalize(), c.value) for c in Category] + [("Ask later", "later")]
FOCUS_OPTIONS = [("1 scattered", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5 deeply focused", "5"), ("Skip", "skip")]
TRACK_OPTIONS = [(c.value.capitalize(), c.value) for c in Category] + [("Don't track", "never"), ("Ask later", "later")]


class Proki:
    def __init__(self, config: Config):
        self.config = config
        # the third-party services: each client made here, once, and given to what uses it
        self.aw = aw.ActivityWatchClient(config.aw_host, config.aw_port)
        Recording.client = self.aw  # the primitives read what it recorded
        self.activitywatch = start_activitywatch(config, self.aw)  # before anything reads from it
        self.nats = start_nats(config.nats_host, config.nats_port)
        Asking.bus = connect_bus(config.nats_host, config.nats_port)  # questions and UI messages go over it
        self.store = Store(DB_PATH)
        config.add_tracked_apps(self.store.tracked_apps())
        self.collector = Collector(config)
        jev = (
            Jev(config.jev_url, config.jev_key, config.jev_model)
            if config.jev_enabled and config.jev_url
            else None
        )
        self.assess = (lambda task: assess_task(jev, task)) if jev else None  # deep/shallow, size, vague?
        self.suggest_group = self.make_group_suggester(jev)
        self.helper = make_helper(config)  # the AI's step suggestions, or None
        # what apps and pages are (core/labels.py); the kinds stored before labels move over once
        self.labels = LabelRegistry(LABELS_PATH)
        migrate(self.labels, self.store.take_old_kinds(), datetime.now(timezone.utc))
        self.labeler = labeling.Labeler(
            self.labels,
            jev=(lambda text, labels: suggest_label(jev, text, labels)) if jev else None,
            gemini=self.helper.label if self.helper else None,
            min_confidence=config.jev_min_confidence,
        )
        self.label_loop = labeling.LabelLoop(
            self.labeler,
            ThreadPoolExecutor(max_workers=2) if jev or self.helper else None,  # never block the UI on the network
            suggest_after=timedelta(seconds=config.suggest_after_seconds),
            ask_after=timedelta(seconds=config.ask_after_seconds),
        )
        self.categorizer = Categorizer(config.categories, self.store, self.labeler)
        self.classifier = ClassificationLoop(config, self.store)  # whether to track an app
        self.analyzer = Analyzer(default_rules())
        self.policy = NudgePolicy(timedelta(minutes=config.min_minutes_between_nudges))
        self.sampling = SamplingSchedule(config.sampling) if config.sampling_enabled else None
        self.recent: list[Segment] = []  # latest analyzed timeline, for rating snapshots
        self.scores = ScoreKeeper(
            self.store,
            load=lambda start, end: prepare(self.collector.between(start, end), config, self.categorizer),
            params=config.focus,
            day_starts=config.day_starts,
        )
        self.quota = QuotaKeeper(self.store, config.quota, config.day_starts, config.focus.deep_threshold)
        self.rhythm = Rhythm(self.store, config.rhythm, config.day_starts, config.focus.deep_threshold)
        self.tray = Tray(  # its items reach the programs (proki/programs/) by name, once the engine made them
            on_session=lambda: program("session").toggle_session(),
            on_tasks=lambda: self.tasks.open_board(),
            on_new_task=lambda: self.tasks.new_task(),
            on_task_done=lambda: program("plan").task_done(),
            on_walk=lambda: program("meditation").start(),
            on_grand=lambda: program("grand").start(),
            on_experiment=lambda: program("experiment").start(),
            on_sprint=lambda: program("sprint").start(),
            on_rate=lambda: self.ask_focus("manual"),
            on_snooze=self.snooze_hour,
            on_settings=lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_PATH))),
            on_autostart=set_autostart,
            autostart_enabled=platforms.current().autostart_installed(),
            on_quit=QApplication.quit,
        )
        self.popup = Popup()
        self.tasks = TasksFlow(  # the task windows (the UI's); handing tasks over is the plan program's
            self.store, self.popup, today=self.rhythm.today, day_starts=config.day_starts,
            deep_minutes_today=lambda now: self.scores.today(now).deep_minutes,
            assess=self.assess, suggest_group=self.suggest_group, helper=self.helper,
        )
        # kinds are remembered by site; without the domain, a browser's window has none yet
        Stream.storage = SignalHistory(self.store)  # where persisted signals keep their history
        Label.label_of = self.labeler.label_of
        Depth.depth_of = lambda app, title: self.labels.depth(self.labeler.label_of(app, title))
        # the engine's UI, in this app for now: questions in the popup, alarms, the session in the tray
        self.ui = PopupClient(self.popup, alarm=lambda: Alarm(config.alarm_sound, config.alarm_volume),
                              set_session=self.tray.set_session, lock_screen=platforms.current().lock_screen,
                              views={"task_form": lambda: self.tasks.new_task(), "task_board": self.tasks.open_board})
        self.ui.serve(Asking.bus)  # it answers your questions ("proki.ask.usr") and shows "proki.ui"
        Ui.elsewhere = lambda: ((self.popup.isVisible() and self.ui.showing is None)  # a legacy question
                                or self.tasks.form.isVisible() or self.tasks.breakdown_dialog.isVisible())
        if jev:
            serve_jev(Asking.bus, jev)
        if config.ai_enabled and config.gemini_api_key:
            serve_llm(Asking.bus, Llm.of("gemini"))
        new_task = self.tasks.new_task
        self.engine = Engine(
            editable_copy(JSON_CONFIG_PATH),  # config.json and programs/ next to the config: yours to edit
            variables=VariableValues(self.store),  # variables keep their latest value
            # programs in code, in the order they take their turn (earlier ones get the popup first);
            # the config's (programs/*.json) come after them
            programs=[
                lambda: Plan(self.store, new_task=new_task, refresh=self.tasks.refresh, today=self.rhythm.today),
                lambda: Session(self.store, config.session, config.focus.deep_threshold, config.sound_on_low_focus,
                                SprintParams().extension),
                lambda: Routines(self.store, config.bedtime.wind_down, config.day_starts,
                                 always_ask=config.routines_always_ask,
                                 classify=(lambda text: classify_activity(jev, text)) if jev else None,
                                 still_there=(lambda context: still_there(jev, context)) if jev else None,
                                 still_there_above=config.routines_skip_if_still_there,
                                 label_name=lambda s: self.labels.name(self.labeler.label_of(s.app, s.title)) if s.app else None),
                lambda: Reminders(self.store, config.day_starts),
                lambda: ThirtyDayTest(self.store, self.rhythm.today, self.distraction_candidates),
                lambda: Capture(self.store, (lambda note: is_todo(jev, note)) if jev else None,
                                new_task=new_task, refresh_tasks=self.tasks.refresh),
                lambda: Shutdown(self.store, config.shutdown, config.day_starts, self.shutdown_wrap_up,
                                 new_task=new_task, weekly_review=self.weekly_review,
                                 save_review=self.save_weekly_review, tools_check=self.tools_check),
                lambda: RhythmPrompts(self.store, self.rhythm, config.rhythm, config.day_starts),
                lambda: Meditation(self.store),
                lambda: Grand(self.store),
                lambda: Sprint(),
                lambda: Craftsman(self.store),
            ],
        )
        self.signals = self.engine.compiled.streams

        self.worth_asking = WorthAsking()
        self._week_sites: tuple[datetime, dict] | None = None
        self._computing = False
        self.background = Background()
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(config.poll_seconds * 1000)
        self.fast_timer = QTimer()
        self.fast_timer.timeout.connect(self.poll)
        self.fast_timer.start(FAST_POLL_MS)
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.ui.pump)  # what came over the bus, onto the screen
        self.ui_timer.start(200)

    def make_group_suggester(self, jev):
        """An existing group that fits (jev), else a name for a new one (the AI)."""
        helper = make_helper(self.config)
        if jev is None and helper is None:
            return None

        def suggest(task: str, groups: list[str]) -> str | None:
            existing = suggest_group(jev, task, groups) if jev else None
            return existing or (helper.group_name(task, "") if helper else None)

        return suggest

    def tick(self) -> None:
        now = datetime.now(timezone.utc)
        if self.activitywatch:
            for module in self.activitywatch.check():
                print(f"restarted {module}", flush=True)
        if self.nats:
            for module in self.nats.check():
                print(f"restarted {module}", flush=True)
        try:
            raw = self.collector.timeline(timedelta(minutes=self.config.lookback_minutes))
        except (OSError, RuntimeError) as e:  # ActivityWatch not running or not ready
            self.tray.set_status(f"waiting for ActivityWatch ({e.__class__.__name__})")
            return
        segments = prepare(raw, self.config, self.categorizer)
        self.recent = segments
        away = bool(segments) and max(segments, key=lambda s: s.end).away
        for finding in self.analyzer.run(segments, now):
            if self.policy.allow(finding, now, away=away):
                self.policy.record(finding, now)
                self.show(finding, self.store.log_nudge(finding, now))
        latest = max(segments, key=lambda s: s.end) if segments else None
        active = latest is not None and not latest.away and now - latest.end <= NO_DATA_AFTER
        self.update_scoreboard(now)
        self.week_sites(now)  # keeps the craftsman data fresh (hourly, in the background)

        def context() -> FlowContext:  # what the programs in code get, once the signals moved on
            state = self.state(now)
            variable("todays_work").set(self.todays_work(now))  # for the morning's greeting (programs/morning.json)
            return FlowContext(now, state, segments=segments, latest=latest, active=active,
                               in_session=state["in_session"],
                               away_since=latest.start if latest is not None and latest.away else None,
                               values={**state, **{signal.name: signal.current() for signal in self.signals}})

        try:
            self.engine.cycle(now, context)  # signals, then programs
        except (OSError, RuntimeError) as e:  # ActivityWatch stopped answering: the cycles wait (none ran)
            self.tray.set_status(f"waiting for ActivityWatch ({e.__class__.__name__})")
            return
        self.ui.show_next()
        self.tray.set_status("away" if away else self.status())  # after the cycles: this tick's focus

    # --- focus sessions --------------------------------------------------------

    def last_night(self, now: datetime) -> tuple[datetime | None, datetime | None]:
        """(last active minute of the previous day, first active minute today), from the
        minute ledger, which is filled from ActivityWatch's history even when proki wasn't running."""
        _, start, end = day_bounds(now, self.config.day_starts)
        active = lambda entries: [e.minute for e in entries if e.activity not in (None, "away")]
        yesterday = active(self.store.minutes(start - timedelta(days=1), start))
        today = active(self.store.minutes(start, end))
        return (yesterday[-1] + timedelta(minutes=1) if yesterday else None, today[0] if today else None)

    def todays_work(self, now: datetime) -> str:
        """One line for the morning: the most urgent goal and its next task, and the deep-work goal."""
        group, task = program("plan").next_task(now)
        quota = self.quota.today(now, self.scores.today(now).deep_minutes)
        goal = f"Today's deep-work goal: {minutes_text(quota)}."
        if task is None:
            return f"{goal} Your task list is empty: add what needs doing."
        where = f"{group.name}: " if group else ""
        return f"{goal} First up: {where}{task.title} (~{minutes_text(task.estimate)})."

    def shutdown_wrap_up(self, now: datetime) -> str:
        """The shutdown's last step: today's deep work, and where tomorrow starts."""
        deep = self.scores.today(now).deep_minutes
        quota = self.quota.today(now, deep)
        lines = [f"Deep work today: {minutes_text(deep)} of {minutes_text(quota)}."]
        tz = now.astimezone().tzinfo
        today = self.rhythm.today(now)
        for ahead in range(1, 8):
            block = self.rhythm.block(today + timedelta(days=ahead), tz)
            if block is not None:
                when = "Tomorrow" if ahead == 1 else f"{block.start.astimezone():%A}"
                lines.append(f"{when}: deep-work block at {block.start.astimezone():%H:%M}.")
                break
        group, task = program("plan").next_task(now)
        if task is not None:
            lines.append(f"First up: {task.title} (~{minutes_text(task.estimate)}).")
        lines.append("Everything is written down. The workday is over.")
        return "\n".join(lines)

    def weekly_review(self, now: datetime) -> str | None:
        """The week's facts, when the weekly review is due (core/weekly.py); else None."""
        today = self.rhythm.today(now)
        last = self.store.last_weekly_review()
        if not review_due(today, last[0] if last else None, self.config.shutdown.days):
            return None
        monday = week_start(today)
        deep_by_day, shallow, active = {}, 0, 0
        for back in range((today - monday).days + 1):
            day = monday + timedelta(days=back)
            _, start, end = day_bounds(datetime.combine(day, time(12)).astimezone(), self.config.day_starts)
            summary = summarize_day(day, self.store.minutes(start, end), self.config.focus.deep_threshold, 0)
            deep_by_day[day] = summary.deep_minutes
            if workday(day, self.config.shutdown):
                share = shallow_share(summary.minutes_by_activity)
                shallow, active = shallow + share.shallow, active + share.active
        _, week_from, _ = day_bounds(datetime.combine(monday, time(12)).astimezone(), self.config.day_starts)
        groups = {g.id: g for g in self.store.groups()}
        minutes: dict[int, int] = {}
        for session in self.rhythm.sessions(week_from, now, now):
            if session.group_id in groups:
                minutes[session.group_id] = minutes.get(session.group_id, 0) + session.deep_minutes
        worked_on = {t.group_id for t in self.store.tasks() if t.group_id is not None}  # groups with open tasks
        by_group = sorted(
            ((g.name, g.priority, minutes.get(g.id, 0)) for g in groups.values() if g.id in minutes or g.id in worked_on),
            key=lambda row: -row[2],
        )
        return review_text(WeekFacts(
            deep_by_day=deep_by_day, daily_goal=self.quota.base(now), by_group=by_group,
            chain=self.rhythm.chain(now), consistency=consistency_lines(self.consistency(now))[0],
            last_answer=last[1] if last else None, workdays=self.config.shutdown.days,
            shallow=(shallow, active), shallow_limit=self.config.shallow.limit,
            top_deep=self.usage(Category.DEEP, week_from, now),  # the vital few
            tools=verdict_lines(self.week_sites(now), self.store.verdicts(), {g.id: g.name for g in self.store.groups()}),
        ))

    def week_sites(self, now: datetime) -> dict:
        """This week's sites/apps with the goals they serve (craftsman check); refreshed hourly in
        the background, since four weeks of history take a few seconds to read. Empty until ready."""
        if (self._week_sites is None or now - self._week_sites[0] >= timedelta(hours=1)) and not self._computing:
            self._computing = True
            self.background.run(lambda: self.compute_week_sites(now), self._week_sites_ready)
        return self._week_sites[1] if self._week_sites else {}

    def _week_sites_ready(self, result) -> None:
        self._computing = False
        if result is not None:
            self._week_sites = result

    def compute_week_sites(self, now: datetime) -> tuple[datetime, dict]:
        """(runs in a worker thread) Pairs (goal, window) over the lookback → what serves which goal;
        then this week's sites (core/association.py, core/craftsman.py)."""
        store = Store(DB_PATH)  # its own connection: SQLite connections stay in their thread
        params = AssociationParams()
        since = now - params.lookback
        categorizer = Categorizer(self.config.categories, store, self.labeler)
        segments = [s for s in prepare(self.collector.between(since, now), self.config, categorizer)
                    if s.app != UNTRACKED]
        sessions = [(a, b or now, g) for a, b, _, _, g in store.sessions_between(since, now)]
        contributes = contributions(pair_minutes(segments, sessions), params)
        for key, (verdict, group, _) in store.verdicts().items():
            if verdict == "serves" and group is not None:  # the user's answer wins
                contributes.setdefault(key, set()).add(group)
        today = self.rhythm.today(now)
        _, week_from, _ = day_bounds(datetime.combine(week_start(today), time(12)).astimezone(), self.config.day_starts)
        notes = [(Segment(now, now, app or "", url=url).key, became_task)
                 for url, app, became_task in store.note_sources(week_from) if url or app]
        week = [s for s in segments if s.end > week_from]
        return now, site_weeks(week, contributes, notes)

    def tools_check(self, now: datetime) -> None:
        """The craftsman question: one site per weekly review, picked by the rule."""
        site = pick(self.week_sites(now), set(self.store.verdicts()), self.worth_asking)
        if site is not None:
            program("craftsman").ask(site, self.store.groups())

    def save_weekly_review(self, now: datetime, answer: str | None) -> None:
        self.store.add_weekly_review(week_start(self.rhythm.today(now)), now, answer)

    def usage(self, category: Category, since: datetime, now: datetime) -> list[tuple[str, int]]:
        """Sites/apps of a category with their minutes since `since`, most first."""
        try:
            segments = prepare(self.collector.between(since, now), self.config, self.categorizer)
        except OSError:
            return []
        minutes: dict[str, float] = {}
        for s in segments:
            if not s.away and s.category is category and s.app != UNTRACKED:
                minutes[s.key] = minutes.get(s.key, 0) + s.duration.total_seconds() / 60
        return sorted(((k, int(m)) for k, m in minutes.items() if m >= 1), key=lambda km: -km[1])

    def distraction_candidates(self) -> list[tuple[str, int]]:
        """Distraction sites/apps with minutes in the last week, most first (for the 30-day test)."""
        now = datetime.now(timezone.utc)
        return self.usage(Category.DISTRACTION, now - timedelta(days=7), now)

    def state(self, now: datetime) -> dict:
        """The app's own values, for the programs in code; each is also the config's variable
        of that name (set here, only when it changes)."""
        state = {
            "in_session": program("session").session is not None,
            "shutdown_done": program("shutdown").done_today(now),
            "popup_open": Ui.busy() or self.popup.isVisible(),  # a question on screen, or waiting for it
        }
        for name, value in state.items():
            if isinstance(variable := Stream.registry.get(name), Variable):
                variable.set(value)
        return state

    def shallow_today(self, now: datetime):
        return shallow_share(self.scores.today(now).minutes_by_activity)

    def update_scoreboard(self, now: datetime) -> None:
        try:
            self.scores.update(now)  # the first run fills in today so far
        except (OSError, RuntimeError):
            return
        deep = self.scores.today(now).deep_minutes
        today = self.scores.today(now, self.quota.today(now, deep))
        _, day_start, day_end = day_bounds(now, self.config.day_starts)
        group, task = program("plan").next_task(now)
        shallow = shallow_share(today.minutes_by_activity)
        lines = (
            scoreboard_lines(today, self.config.focus.deep_threshold)
            + budget_lines(shallow, self.config.shallow.limit)
            + rhythm_lines(program("rhythm").todays_block(now), now, self.rhythm.chain(now), self.rhythm.todays_sessions(now))
            + consistency_lines(self.consistency(now))
            + experiment_lines(self.store.experiments(("running",)), self.rhythm.today(now))
            + task_lines(group, task, self.store.tasks_done_between(day_start, day_end))
            + sleep_lines(*self.last_night(now))
        )
        self.tray.set_scoreboard(lines, today.goal_progress)

    def consistency(self, now: datetime):
        params = ConsistencyParams()
        starts = self.rhythm.first_starts(now, params.history_days)
        return consistency(starts, self.rhythm.today(now), self.config.day_starts, params)

    def poll(self) -> None:
        """Every few seconds: classify what's in focus, asking the user if needed."""
        now = datetime.now(timezone.utc)
        try:
            current = self.collector.current()
        except OSError:
            return  # ActivityWatch not reachable; tick() reports it in the tray
        question = self.classifier.observe(current, now)
        present = current is not None and not current.away
        label_question = None
        if present and question is None and self.config.is_tracked(current.app, current.title, current.url):
            label_question = self.label_loop.observe(current.app, current.title, now)
        state = self.state(now)
        ctx = FlowContext(now, state=state, latest=current, current=current, active=present,
                          in_session=state["in_session"],
                          category=self.categorizer.categorize(current) if present else None,
                          kind=self.categorizer.kind(current) if present else None)
        self.engine.poll(now, ctx)  # answers, and the programs that watch what's in focus
        self.ui.show_next()
        if question and not self.popup.isVisible():
            self.ask(question)
        elif label_question and not self.popup.isVisible():
            self.ask_label(label_question)
        elif self.sampling and not self.popup.isVisible():
            away = current is None or current.away
            if self.sampling.due(now, away):
                self.ask_focus("sampled")

    def ask_focus(self, source: str) -> None:
        """Ask for a 1–5 focus rating: ground truth for calibrating the focus score."""
        asked_at = datetime.now(timezone.utc)
        self.popup.ask(
            "How focused are you right now?",
            lambda r: self.on_focus_rating(asked_at, r, source),
            FOCUS_OPTIONS,
        )

    def on_focus_rating(self, asked_at: datetime, response: str, source: str) -> None:
        now = datetime.now(timezone.utc)
        snapshot = {}
        for horizon in self.config.focus.horizons:
            m = moment(self.recent, now, horizon, self.config.focus)
            snapshot[f"{int(horizon.total_seconds() // 60)}m"] = {
                "intensity": m.intensity, "depth": m.depth, "fit": m.fit,
                "hit_rate": m.hit_rate, "continuity": m.continuity,
            }
        rating = None if response == "skip" else int(response)
        self.store.add_rating(asked_at, now, rating, source, snapshot)

    def status(self) -> str:
        """The tray's line: config.json's `focus_5m`, the focus the rules decide by."""
        focus = Stream.registry.get("focus_5m")
        value = focus.current() if focus is not None else None
        if value is None:
            return "focus now – (unknown, last 5 min)"
        return f"focus now {value:.2f} (last 5 min)"

    def ask(self, question: Question) -> None:
        message = (
            f"You're using “{question.key}”, which proki doesn't track yet. Track it as…\n"
            "(Tracked apps are recorded by name and count toward focus;"
            " untracked ones stay anonymous.)"
        )
        self.popup.ask(message, lambda r: self.classifier.answered(question, r, datetime.now(timezone.utc)),
                       TRACK_OPTIONS)

    # --- labels (core/labeling.py) -----------------------------------------------

    def ask_label(self, question: labeling.Question) -> None:
        what = f"“{question.title}” ({question.app})" if question.title else f"“{question.app}”"
        others = [("Other label…", "_groups"), ("New label…", "_new"), ("Ask later", "later")]
        if question.kind == "confirm":
            entry = self.labels.get(question.key)
            name = self.labels.name(entry.label if entry else None)
            source = {"openjev": "openjev", "gemini": "Gemini"}.get(entry.source, entry.source) if entry else ""
            self.popup.ask(f"{what} looks like {name} (says {source}). Right?",
                           lambda r: self.on_label_answer(question, r), [("Right", "ok"), *others])
        else:
            self.popup.ask(f"What is {what}?", lambda r: self.on_label_answer(question, r),
                           [(group, f"_group:{group}") for group in self.labels.groups()] + others[1:])

    def on_label_answer(self, question: labeling.Question, response: str) -> None:
        """Answers to label popups; some open a follow-up (groups, a new label's name, how it counts)."""
        what = question.title or question.app
        if response == "_groups":
            self.popup.ask(f"What is “{what}”?", lambda r: self.on_label_answer(question, r),
                           [(group, f"_group:{group}") for group in self.labels.groups()] + [("New label…", "_new")])
        elif response.startswith("_group:"):
            group = response.removeprefix("_group:")
            self.popup.ask(f"What is “{what}”? ({group})", lambda r: self.on_label_answer(question, r),
                           [(label.name, f"label:{slug}") for slug, label in self.labels.in_group(group)])
        elif response == "_new":
            self.popup.ask_text(f"What kind of app or page is “{what}”? (a short label)",
                                lambda text: self.on_label_answer(question, f"new:{text}") if text else None,
                                placeholder="e.g. Lecture videos")
        elif response.startswith("_counts:"):
            slug = response.removeprefix("_counts:")
            self.popup.ask(f"How does {self.labels.name(slug)} count?",
                           lambda r: self.labels.set_category(slug, Category(r)) if r != "later" else None,
                           RATING_OPTIONS)
        else:
            self.label_loop.answered(question, response, datetime.now(timezone.utc))
            slug = self.labels.label_of(question.key)
            if response != "later" and slug and self.labels.category(slug) is None:
                self.on_label_answer(question, f"_counts:{slug}")  # a label without a default: how does it count?

    def show(self, finding: Finding, nudge_id: int) -> None:
        if finding.level is Level.QUIET:
            self.tray.set_status(finding.message)
        elif finding.level is Level.NOTIFY:
            self.tray.notify("proki", finding.message)
        else:
            self.popup.ask(finding.message, lambda r: self.on_response(nudge_id, r))

    def on_response(self, nudge_id: int, response: str) -> None:
        self.store.set_response(nudge_id, response)
        if response == "snooze":
            self.policy.snooze(datetime.now(timezone.utc) + timedelta(minutes=30))

    def snooze_hour(self) -> None:
        self.policy.snooze(datetime.now(timezone.utc) + timedelta(hours=1))
        self.tray.set_status("snoozed for 1 hour")


def make_helper(config: Config):
    """The AI's step suggestions (Gemini), if enabled and a key is set; otherwise None."""
    if not (config.ai_enabled and config.gemini_api_key):
        return None
    from proki.legacy.core.ai import TaskHelper

    return TaskHelper(config.gemini_api_key, config.ai)


def set_autostart(enabled: bool) -> None:
    os_support = platforms.current()
    if enabled:
        os_support.install_autostart([sys.executable, "-m", "proki"])
    else:
        os_support.uninstall_autostart()


def start_activitywatch(config: Config, client: aw.ActivityWatchClient) -> Supervisor | None:
    """Start ActivityWatch's programs ourselves, unless disabled, missing, or already running."""
    if not config.aw_manage:
        return None
    os_support = platforms.current()
    commands = find_commands(aw.MODULES, os_support.ACTIVITYWATCH_DIRS, os_support.EXECUTABLE_SUFFIX)
    if commands is None:
        print("ActivityWatch not found; start it yourself or set [activitywatch] manage = false", flush=True)
        return None
    supervisor = Supervisor("ActivityWatch", commands, client.is_up, user_log_path("proki") / "activitywatch")
    print(supervisor.start(), flush=True)
    return supervisor


def start_nats(host: str, port: int) -> Supervisor | None:
    """Start the NATS server ourselves, at `host`:`port`, unless it's missing or already running."""
    os_support = platforms.current()
    commands = find_commands(nats.MODULES, os_support.NATS_DIRS, os_support.EXECUTABLE_SUFFIX)
    if commands is None:
        print("nats-server not found (brew install nats-server): questions stay in this process", flush=True)
        return None
    commands["nats-server"] += ["-a", host, "-p", str(port)]  # on the config's address only
    supervisor = Supervisor("NATS", commands, lambda: nats.NatsBus.is_up(host, port), user_log_path("proki") / "nats")
    print(supervisor.start(), flush=True)
    return supervisor


def connect_bus(host: str, port: int) -> nats.Bus:
    """The message bus: NATS if a server answers at `host`:`port`, else one in this process
    (everything works, in this process only)."""
    if not nats.NatsBus.is_up(host, port):
        return nats.LocalBus()
    try:
        return nats.NatsBus(host, port)
    except Exception as e:  # a server that doesn't speak NATS
        print(f"NATS unreachable ({e.__class__.__name__}): questions stay in this process", flush=True)
        return nats.LocalBus()


def run(config: Config) -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # closing a window must not quit the daemon
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(DATA_DIR / "proki.lock"))  # released automatically if proki crashes
    if not lock.tryLock(0):
        print("proki is already running.", flush=True)
        return 0
    proki = Proki(config)
    if proki.activitywatch:
        app.aboutToQuit.connect(proki.activitywatch.stop)  # stop what we started
    app.aboutToQuit.connect(Asking.bus.close)
    if proki.nats:
        app.aboutToQuit.connect(proki.nats.stop)
    # Quit cleanly (running aboutToQuit) when told to stop, e.g. at logout or by launchd.
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: app.quit())
    wake = QTimer()
    wake.timeout.connect(lambda: None)  # lets Python handle signals while Qt's loop runs
    wake.start(500)
    QTimer.singleShot(0, proki.tick)  # first check right away
    return app.exec()

