"""Programs written in code (proki/programs/), program files, the UI messages, slow calls."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import replay_cycle
from proki import compiler
from proki.compiler import compile_config, editable_copy
from proki.core.later import Later
from proki.core.programs import Program
from proki.core.signals import Stream
from proki.core.ui import Ui
from proki.engine import Engine
from proki.legacy.core.events import Category, Segment
from proki.legacy.core.store import Store
from proki.legacy.flows.base import FlowContext
from proki.programs import Plan, Ritual, Session
from proki.services.activitywatch import Record


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "proki.db")


def config(tmp_path, data, files=None):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    (tmp_path / "programs").mkdir(exist_ok=True)
    for name, spec in (files or {}).items():
        (tmp_path / "programs" / f"{name}.json").write_text(json.dumps(spec))
    return path


# --- program files -----------------------------------------------------------------------

def test_a_program_brings_its_own_file(tmp_path):
    path = config(tmp_path, {"variables": [{"name": "x", "value": 1}]}, {"bump": {
        "rules": [{"name": "low_x", "lhs": "x", "cmp": "lt", "rhs": 3}],
        "program": {"name": "bump", "initial": "s", "states": {"s": {
            "do": [{"add": {"name": "x", "expr": 1}}], "next": [{"if": ["low_x"], "goto": "s"}]}}}}})
    compiled = compile_config(path)
    assert [p.name for p in compiled.programs] == ["bump"] and "low_x" in {r.name for r in compiled.rules}
    Stream.registry.clear(), Program.registry.clear()
    assert compile_config(path, programs=[]).programs == []  # which files, by name


def test_program_files_are_checked(tmp_path):
    for spec, problem in [({"program": {"name": "other", "initial": "s", "states": {"s": {}}}}, "named after the file"),
                          ({"program": {"name": "p", "initial": "s", "states": {"s": {}}}, "inputs": []}, "unknown inputs")]:
        path = config(tmp_path, {}, {"p": spec})
        with pytest.raises(ValueError, match=problem):
            compile_config(path)


def test_your_copy_gets_the_program_files(tmp_path, monkeypatch):
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    rule = {"name": "r", "lhs": 1, "cmp": "eq", "rhs": 1}
    program = {"name": "p", "initial": "s", "states": {"s": {"next": "s"}}}
    (shipped / "config.json").write_text(json.dumps({"rules": []}))
    config(shipped, {"rules": []}, {"p": {"rules": [rule], "program": program}})
    monkeypatch.setattr(compiler, "CONFIG", shipped / "config.json")
    mine = tmp_path / "mine" / "config.json"
    mine.parent.mkdir()
    mine.write_text(json.dumps({"rules": [rule, {"name": "yours", "lhs": 1, "cmp": "eq", "rhs": 2}],
                                "programs": [program]}))  # p, from before it had a file
    editable_copy(mine)
    assert json.loads((mine.parent / "programs" / "p.json").read_text())["program"] == program
    kept = json.loads(mine.read_text())
    assert [r["name"] for r in kept["rules"]] == ["yours"] and kept["programs"] == []  # moved into the file
    compile_config(mine)  # nothing defined twice


# --- questions, the UI, slow calls ---------------------------------------------------------

def test_text_questions_and_urgent_ones(ui):
    typed = []
    Ui.ask_text("Anything still open?", typed.append, placeholder="…", skip_label="That's all")
    Ui.ask("Focus is slipping", lambda a: None, [("Back on it", "ok")], urgent=True)
    text, urgent = ui.questions()
    assert text["options"] is None and text["show"]["skip"] == "That's all" and urgent["show"]["urgent"] is True
    assert Ui.busy()
    ui.click("buy milk", text)
    ui.click("Back on it", urgent)
    Later.deliver()
    assert typed == ["buy milk"] and not Ui.busy()


def test_an_alarm_question_rings_until_answered(ui):
    Ui.ask("Bedtime", lambda a: None, [("Lock screen", "lock")], alarm="bedtime")
    ui.click("Lock screen")
    Later.deliver()
    alarms = [m["on"] for m in ui.sent if m["type"] == "alarm"]
    assert alarms == [True, False]


def test_slow_calls_come_back_at_the_next_turn():
    got = []
    Later.run(lambda: 6 * 7, got.append)
    Later.run(lambda: 1 / 0, got.append)  # a failure: None
    Later.pool.shutdown(wait=True)
    Later.pool = None
    assert got == []
    Later.deliver()
    assert sorted(got, key=str) == [42, None]


# --- plan and session ------------------------------------------------------------------------

class Stub(Ritual):
    """A program the session reaches by name, keeping what it's told."""

    def __init__(self, name):
        super().__init__(name)
        self.calls = []

    def __getattr__(self, method):
        return lambda *args: self.calls.append((method, *args))


def tasks(store):
    now = datetime.now(timezone.utc)
    thesis = store.add_group("Thesis", "high", now)
    store.add_task(thesis, "Write the intro", "", date.today() + timedelta(days=1), 40, now)
    store.add_task(thesis, "Fix the figures", "", date.today() + timedelta(days=2), 30, now)


SESSION = {
    "variables": [{"name": "in_session", "value": False}, {"name": "session_requested", "value": False},
                  {"name": "session_stop_requested", "value": False},
                  {"name": "focus_2m", "value": 0.8}, {"name": "focus_2m_rise", "value": 0}],
    "rules": [{"name": "session_low_focus", "lhs": "focus_2m", "cmp": "lt", "rhs": 0.35, "level": 2},
              {"name": "session_not_recovering", "lhs": "focus_2m_rise", "cmp": "le", "rhs": 0.05, "level": 1}],
}


def at_work(now):
    """A minute of work up to `now`: the timeline the session sees."""
    return FlowContext(now, segments=[Segment(now - timedelta(minutes=1), now, "Code", category=Category.DEEP)],
                       active=True)


def test_plan_hands_over_a_task_when_a_session_starts(tmp_path, ui, store):
    tasks(store)
    e = Engine(config(tmp_path, SESSION), programs=[lambda: Plan(store)])
    plan = Program.registry["plan"]
    plan.start_session()
    assert plan.current == "offering" and ui.questions()[-1]["context"].endswith("Next: Write the intro  (~40m)")
    ui.click("Done")  # already done: the next one of the same group
    Later.deliver()
    assert ui.questions()[-1]["context"].endswith("Next: Fix the figures  (~30m)")
    ui.click("Start")
    Later.deliver()
    assert plan.current == "working" and Stream.registry["task"].value == "Fix the figures"
    replay_cycle(e, datetime.now(timezone.utc), rec=Record.of(datetime.now(timezone.utc) - timedelta(minutes=1), datetime.now(timezone.utc), {}))
    assert Stream.registry["tasks_open"].value == 1
    plan.end_session()
    assert plan.current == "idle" and Stream.registry["task"].value is None


def test_a_session_from_the_config_pokes_and_stops(tmp_path, ui, store):
    tasks(store)
    stubs = {}
    e = Engine(config(tmp_path, SESSION),
               programs=[lambda: Plan(store), lambda: Session(store),
                         *[lambda n=n: stubs.setdefault(n, Stub(n)) for n in ("shutdown", "meditation", "sprint")]])
    session = Program.registry["session"]

    def cycle(now):
        replay_cycle(e, now, at_work(now), rec=Record.of(now - timedelta(minutes=1), now, {}))

    Stream.registry["session_requested"].set(True)  # a suggestion's "Start session"
    start = datetime.now(timezone.utc)
    cycle(start)
    assert session.current == "focusing" and Stream.registry["in_session"].value is True
    assert Stream.registry["session_requested"].value is False
    assert ui.questions()[-1]["context"].endswith("Next: Write the intro  (~40m)")  # the plan's offer
    assert {"type": "session", "minutes": 0, "extra": None} in ui.sent  # the tray

    Stream.registry["focus_2m"].set(0.1)  # focus drops: low for a minute → a poke, before anything else
    cycle(start + timedelta(seconds=30))
    cycle(start + timedelta(seconds=95))
    poke = ui.questions()[-1]
    assert poke["context"].startswith("Your focus is slipping") and poke["show"]["urgent"] is True

    Stream.registry["session_stop_requested"].set(True)  # hub's "Stop session"
    cycle(start + timedelta(minutes=2))
    assert session.current == "idle" and Stream.registry["in_session"].value is False
    assert stubs["shutdown"].calls[0][0] == "session_ended" and stubs["meditation"].calls[0][0] == "after_session"
    assert store.running_session() is None and {"type": "hide"} in ui.sent


def shipped(tmp_path, *names, variables=()):
    """A config with the shipped program files `names`, the clock, and stand-in variables."""
    import shutil

    path = config(tmp_path, {"inputs": [{"name": "clock"}, {"name": "time"}],
                             "variables": [{"name": n, "value": v} for n, v in variables],
                             "signals": [{"name": "today", "expr": "time - clock - (clock < 240) * 1440"}]})
    for name in names:
        shutil.copyfile(compiler.CONFIG.parent / "programs" / f"{name}.json", tmp_path / "programs" / f"{name}.json")
    return path


def local(day, hour, minute, second=0):
    return datetime(2026, 10, day, hour, minute, second).astimezone()


def runner(e):
    """`run(until)`: the engine's cycles every 10 s up to `until`, as the app runs them
    (`jump`: one cycle straight to `until`, like after a sleep)."""
    at = []

    def run(until, step=timedelta(seconds=10), jump=False, **values):
        for name, value in values.items():
            Stream.registry[name].set(value)
        t = until if jump or not at else at[-1] + step
        while t <= until:
            replay_cycle(e, t, rec=Record.of(t - timedelta(minutes=1), t, {}))
            Later.deliver()
            at.append(t)
            t += step
    return run


def test_bedtime_from_the_config_pokes_then_rings(tmp_path, ui):
    e = Engine(shipped(tmp_path, "bedtime", variables=[("active", True)]))
    bedtime, run = Program.registry["bedtime"], runner(e)
    run(local(5, 21, 0))
    run(local(5, 21, 59))
    assert not ui.questions()  # the day
    run(local(5, 22, 0, 10))
    [poke] = ui.questions()
    assert ui.labels(poke) == ["10 more minutes", "OK, winding down", "Lock screen"]
    assert poke["context"].startswith("It's 22:00. Time to wrap up")
    ui.click("10 more minutes")
    run(local(5, 22, 9))
    assert len(ui.questions()) == 1  # snoozed until 22:10
    run(local(5, 22, 11))
    assert ui.labels(ui.questions()[-1]) == ["OK, winding down", "Lock screen"]  # one snooze a night
    run(local(5, 23, 59, 50), jump=True)  # left unanswered: the default, back to idle
    run(local(6, 0, 0, 10))  # past the hard stop
    assert {"type": "alarm", "id": "bedtime", "on": True} in ui.sent and bedtime.current == "ringing"
    ui.click("Lock screen")
    run(local(6, 0, 11), active=False)  # locked: away
    alarms = [m for m in ui.sent if m["type"] == "alarm"]
    assert {"type": "lock"} in ui.sent and alarms[-1] == {"type": "alarm", "id": "bedtime", "on": False}
    assert bedtime.current == "idle"


def test_the_morning_from_the_config(tmp_path, ui):
    e = Engine(shipped(tmp_path, "morning", variables=[("active", False), ("in_session", False),
                                                       ("session_requested", False), ("todays_work", "\"Thesis first.\"")]))
    morning, run = Program.registry["morning"], runner(e)
    run(local(6, 3, 0))
    run(local(6, 6, 59), jump=True)  # asleep since 03:00
    run(local(6, 7, 0), active=True)  # picked up the laptop
    greeting = ui.questions()[-1]
    assert "Thesis first." in greeting["context"] and "60 min" in ui.labels(greeting)
    ui.click("15 min")  # 15 minutes and a 5-minute buffer: until 07:20
    run(local(6, 7, 1))
    assert morning.current == "routine"
    run(local(6, 7, 5))
    run(local(6, 7, 9), active=False)  # in the shower: away after 3 minutes
    assert morning.current == "away"
    run(local(6, 7, 10), active=True)  # back early
    assert ui.questions()[-1]["context"] == "Finished your morning routine?"
    ui.click("Not yet")  # a minute more: until 07:21
    run(local(6, 7, 20))
    assert not any(m["type"] == "alarm" for m in ui.sent)
    run(local(6, 7, 21, 30))
    assert morning.current == "overdue" and {"type": "alarm", "id": "morning", "on": True} in ui.sent
    ui.click("Start session")
    run(local(6, 7, 22))
    assert Stream.registry["session_requested"].value is True  # the session program starts it
    alarms = [m for m in ui.sent if m["type"] == "alarm"]
    assert morning.current == "done" and alarms[-1] == {"type": "alarm", "id": "morning", "on": False}
    run(local(7, 6, 0), jump=True, active=False)  # a new day
    assert morning.current == "idle"


def test_every_program_takes_its_turns_with_the_shipped_config(tmp_path, ui, store, monkeypatch):
    """The app's programs (as legacy/app.py makes them) and the shipped config's, through a
    working day's cycles and polls, without one failing."""
    from proki.compiler import CONFIG
    from proki.legacy.config import Config
    from proki.legacy.core.rhythm import Rhythm as Days
    from proki.programs import (Capture, Craftsman, Grand, Meditation, Reminders, Rhythm, Routines, Shutdown, Sprint,
                                ThirtyDayTest)

    tasks(store)
    c = Config()
    days = Days(store, c.rhythm, c.day_starts, c.focus.deep_threshold)
    e = Engine(CONFIG, programs=[
        lambda: Plan(store, today=days.today), lambda: Session(store, c.session, c.focus.deep_threshold),
        lambda: Routines(store, c.bedtime.wind_down, c.day_starts), lambda: Reminders(store, c.day_starts),
        lambda: ThirtyDayTest(store, days.today, lambda: []), lambda: Capture(store, None),
        lambda: Shutdown(store, c.shutdown, c.day_starts, lambda now: "Tomorrow."),
        lambda: Rhythm(store, days, c.rhythm, c.day_starts), lambda: Meditation(store), lambda: Grand(store),
        lambda: Sprint(), lambda: Craftsman(store)])
    assert {"plan", "session", "shutdown", "day", "suggest", "budget", "hub", "bedtime", "morning", "evening"} \
        <= set(Program.registry)
    start = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)
    for minute in range(0, 14 * 60, 7):  # 08:00 to 22:00 UTC, answering every question with its first option
        now = start + timedelta(minutes=minute)
        work = Segment(now - timedelta(minutes=7), now, "Code", "proki — app.py", category=Category.DEEP)
        replay_cycle(e, now, FlowContext(now, {"in_session": False, "shutdown_done": False, "popup_open": False},
                                 segments=[work], latest=work, active=True, values={"focus_5m": 0.2}), rec=Record.of(now - timedelta(minutes=7), now, {}))
        e.poll(now, FlowContext(now, latest=work, current=work, active=True, category=Category.DEEP))
        for request in ui.questions():
            if request["id"] in ui.replies:
                ui.click(ui.labels(request)[0] if request["options"] else "a note", request)
    assert ui.questions()  # it spoke up, and every answer went through
