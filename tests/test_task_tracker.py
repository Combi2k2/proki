"""A session's task: counted by the config's task_tracker, and checked on at a break; asked by
@task_picker when there's none."""
import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from conftest import built, programs_folder, tick, with_notes
from proki import settings
from proki.channels import Channels, jev
from proki.core.programs import Program
from proki.core.signals import Stream
from proki.programs.code.base import find_variable, make_variable
from proki.programs.code.work import Work
from proki.tools import records
from proki.serve import setters
from proki.storage import SCHEMA

NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)
at  = lambda minutes: NOW + timedelta(minutes=minutes)


class PickingJev:
    """A stand-in jev: for a choice, the probabilities by a word in its question, each option's by
    its place."""

    def __init__(self, choice):
        self.choice = choice

    def ask(self, state, questions):
        picked = lambda q: next((ps for w, ps in self.choice.items() if w in q["instructions"]), {})
        return {key: {"probabilities": {list(q["criteria"])[i]: p for i, p in ps.items()}, "confidence": max(ps.values())}
                for key, q in questions.items() if q["type"] == "choice" and (ps := picked(q))}


@pytest.fixture
def board(tmp_path):
    db = sqlite3.connect(tmp_path / "proki.db")
    db.executescript(SCHEMA)
    board = Work(db)
    thesis = records.add("work.groups", NOW, name="Thesis", desc="The thesis, chapter by chapter")
    records.add("work.tasks", NOW, group=thesis, name="Write the intro", estimate=40)
    records.add("work.tasks", NOW, group=thesis, name="Fix the figures", estimate=30)
    errands = records.add("work.groups", NOW, name="Errands")
    records.add("work.tasks", NOW, group=errands, name="Buy milk", estimate=10)
    return board


@pytest.fixture
def session():
    """`session.active` and `session.requested`, as the session program keeps them."""
    return make_variable("session.active", False), make_variable("session.requested", False)


@pytest.fixture
def tracker(board, tmp_path):
    """The shipped task_tracker on its own, `session.active`, `session.requested`, `active` and
    `time` its variables."""
    make_variable("task_asked", False), make_variable("task_done", False)
    built(programs_folder(tmp_path / "programs", {"variables": [{"name": name, "value": value} for name, value in
                                                              [("session.active", False), ("session.requested", False), ("active", True), ("time", 0)]]},
                          {"task_tracker": json.loads((settings.SHIPPED_DIR / "task_tracker.json").read_text())}))
    yield
    Program.stop()


async def minute(m):
    """Minute `m`'s first cycles, 10 s apart (a state's next is tried 6 s on): the streams,
    then the programs."""
    for t in (at(m), at(m) + timedelta(seconds=10)):
        find_variable("time").set(at(m).timestamp() / 60)
        Stream.tick(t)
        await tick(t)


def task(board, name):
    return next(t["id"] for t in board.tasks.current() if t["name"] == name)


def hold(board, id):
    """The task at hand: as Start session, or Work on this, picks it."""
    find_variable("work.task").set(board.tasks.get_row(id))


def held():
    return Stream.registry["work.task"].value


def value_of(board, key, id):
    return board.tasks.get_row(id)[key]


def test_the_task_at_hand_is_one_of_the_tasks_you_can_work_on(board):
    from proki.core.signals import Expr
    from proki.errors import VariableError
    make_variable("time", NOW.timestamp() / 60)
    records.change("work.tasks", task(board, "Fix the figures"), NOW, status="done")
    value = lambda expr: Expr(expr).value()
    assert value("work.tasks.name") == ["Write the intro", "Fix the figures", "Buy milk"] and value("work.task") is None  # every one
    assert value("where(work.tasks, work.tasks.ready).name") == ["Write the intro", "Buy milk"] and value("work.tasks.start")[1] is None
    assert value("work.groups.name") == ["Thesis", "Errands"] and value("where(work.tasks, work.tasks.group, work.groups[0].id).name") == [
        "Write the intro", "Fix the figures"] and value("work.groups.startable") == [True, True]
    assert value("work.tasks[0].score") is not None and Expr("work.tasks[0].estimate").type == "number"  # yours too, typed
    find_variable("work.task").set(value("work.tasks[argmin(work.tasks.estimate)]"))
    assert value("work.task.name") == value("work.task")["name"] == "Buy milk" and held() == task(board, "Buy milk")
    with pytest.raises(VariableError):
        find_variable("work.task").set(task(board, "Buy milk"))  # an id: the task is one of work.tasks
    find_variable("work.task").set(None)
    assert value("work.task") is None and value("work.task.name") is None


async def test_a_tasks_field_is_set_where_its_kept_through_any_copy(board):
    from proki.core.actions import Set
    from proki.errors import VariableError
    make_variable("time", NOW.timestamp() / 60)
    make_variable("at", 0), make_variable("item", None)
    status = lambda name: next(t["status"] for t in board.tasks.current() if t["name"] == name)
    find_variable("item").set(find_variable("work.tasks").current()[0])
    await Set(name="item.name", expr="'Renamed'").apply()  # on the board, and item's copy
    assert find_variable("item").current()["name"] == "Renamed" and status("Renamed") == "open"
    await Set(name="item.name", expr="'Write the intro'").apply()
    plain = make_variable("plain", {"id": 1, "name": "x"})  # no record's: a value of its own
    await Set(name="plain.name", expr="'y'").apply()
    assert plain.current() == {"id": 1, "name": "y"} and status("Write the intro") == "open"
    await Set(name="work.tasks[index(work.tasks.id, item.id)].status", expr="'done'").apply()
    await Set(name="work.tasks[at + 9].status", expr="'done'").apply()  # no task there: nothing
    assert status("Write the intro") == "done" and held() is None  # not the one at hand
    await Set(name="work.tasks[-1].estimate", expr="15", when="at == 0").apply()
    assert next(t["estimate"] for t in board.tasks.current() if t["name"] == "Buy milk") == 15
    find_variable("work.task").set(find_variable("work.tasks").current()[0])
    for name, problem in [("work.tasks[0].group_name", "worked out"), ("work.tasks[0].nope", "no field nope"), ("work.task.nope", "no field nope")]:
        with pytest.raises(VariableError, match=problem):
            await Set(name=name, expr="1").apply()
    await Set(name="work.groups[0].name", expr="'Thesis, v2'").apply()   # a record's field: any is set
    assert board.groups.current()[0]["name"] == "Thesis, v2"


async def asked(ui, n, seconds=2.0):
    """Wait until the UI has `n` questions (jev answers on a thread)."""
    for _ in range(int(seconds / 0.01)):
        if len(ui.questions()) >= n:  return ui.questions()[n - 1]
        await asyncio.sleep(0.01)
    raise AssertionError(f"{len(ui.questions())} questions, not {n}: {[q['context'] for q in ui.questions()]}")


# --- the config's task_tracker ------------------------------------------------------------

async def test_a_task_picked_counts_while_youre_at_the_computer_in_the_session(ui, board, tracker):
    intro = task(board, "Write the intro")
    hold(board, intro)
    find_variable("session.requested").set(True)
    await minute(0)  # counted from the pick: the session's only asked for
    find_variable("session.requested").set(False), find_variable("session.active").set(True)
    for m in range(1, 11):
        await minute(m)
    assert value_of(board, "spent", intro) == 10 and value_of(board, "last_worked", intro) == at(10).timestamp() / 60
    find_variable("active").set(False)  # away
    await minute(11), await minute(12)
    assert value_of(board, "spent", intro) == 10 and ui.questions() == []

    find_variable("session.active").set(False)
    await minute(13), await minute(14)
    assert held() is None  # the session's end lets go of it


async def test_past_its_estimate_its_checked_on_and_done_is_done(ui, board, tracker):
    intro = task(board, "Write the intro")
    hold(board, intro), find_variable("session.active").set(True)
    for m in range(42):
        await minute(m)
    check = await asked(ui, 1)
    assert check["context"] == "Still on “Write the intro”? That's 40 min so far, past its estimate."
    await ui.click("Done")
    await minute(42)
    assert [t["status"] for t in board.tasks.current() if t["id"] == intro] == ["done"]
    assert held() is None and find_variable("task_done").value is True  # @task_picker: what's next?


async def test_no_answer_stops_the_count_at_the_break(ui, board, tracker):
    intro = task(board, "Write the intro")
    hold(board, intro), find_variable("session.active").set(True)
    for m in range(42):
        await minute(m)
    await asked(ui, 1)
    await ui.click(None)
    await minute(50)
    assert value_of(board, "spent", intro) == 40 and held() is None
    assert find_variable("task_asked").value is True  # not asked what you're on, this session


async def test_back_from_a_break_its_checked_on(ui, board, tracker):
    figures = task(board, "Fix the figures")
    hold(board, figures), find_variable("session.active").set(True)
    await minute(0)
    find_variable("active").set(False)
    await minute(1), await minute(2)
    find_variable("active").set(True)  # back
    await minute(3)
    assert (await asked(ui, 1))["context"] == "Still on “Fix the figures”?"
    await ui.click("Still on it")
    await minute(4)
    assert value_of(board, "spent", figures) == 2 and held() == figures  # the minute before, and the wait


# --- the task picker -----------------------------------------------------------------------

@pytest.fixture
def picker(board, tmp_path):
    """The shipped task picker on its own, on `board`: `session.active` and `session.requested` its variables, and the notes."""
    built(programs_folder(tmp_path / "programs", with_notes({"variables": [{"name": name, "value": value} for name, value in
                                                              [("session.active", False), ("session.requested", False), ("time", 0), ("today", 0)]]}),
                          {"task_picker": json.loads((settings.SHIPPED_DIR / "task_picker.json").read_text())}))
    yield
    Program.stop()


async def picked(ui, n, m):
    """The cycles a minute apart from minute `m`, until the UI has `n` questions (jev answers on a thread): the question, and the next minute."""
    for minute_ in range(m, m + 10):
        if len(ui.questions()) >= n:
            return ui.questions()[n - 1], minute_
        await minute(minute_)
        await asyncio.sleep(0.05)
    raise AssertionError(f"{len(ui.questions())} questions, not {n}: {[q['context'] for q in ui.questions()]}")


async def test_a_session_without_a_task_asks_and_jev_picks_it_for_you_to_confirm(ui, board, picker):
    await jev.serve(Channels.bus, PickingJev({"groups": {0: 0.9}, "these tasks": {1: 0.8}}))
    find_variable("session.active").set(True)
    question, m = await picked(ui, 1, 0)
    assert question["context"] == "What are you working on?"
    await ui.click("the axis labels on chapter 2's plots")

    question, m = await picked(ui, 2, m)  # jev's sure of the group: only the task's asked
    assert question["context"].endswith("Which task in “Thesis” is it?")
    assert [o[0] for o in question["options"]] == ["Write the intro", "Fix the figures", "Another group", "Something new"]
    assert question["show"]["selected"] == 1  # jev's
    await ui.click("Fix the figures")
    await minute(m)
    assert held() == task(board, "Fix the figures")


async def test_something_new_is_a_todo_for_the_planner(ui, board, tmp_path):
    built(programs_folder(tmp_path / "programs", with_notes({"variables": [{"name": name, "value": value} for name, value in
                                                              [("session.active", True), ("session.requested", False), ("time", 0), ("today", 0)]]}),
                          {"task_picker": json.loads((settings.SHIPPED_DIR / "task_picker.json").read_text())}))
    question, m = await picked(ui, 1, 0)
    await ui.click("Slides for Friday's talk")
    question, m = await picked(ui, 2, m)  # no jev: the group's asked
    assert [o[0] for o in question["options"]] == ["Thesis", "Errands", "Something new"]
    await ui.click("Something new")
    await minute(m), await minute(m + 1)
    assert [n["content"] for n in Stream.registry["note"].current() if n["bucket"] == "Todo"] == ["Slides for Friday's talk"]
    assert held() is None
    await minute(m + 2)
    assert len(ui.questions()) == 2  # asked once a session
    Program.stop()


# --- the fields, in the config --------------------------------------------------------------

async def test_the_config_reads_and_sets_the_task_at_hands_fields(ui, board, tmp_path):
    from conftest import built, programs_folder

    path = programs_folder(tmp_path / "programs", {"variables": [{"name": "session.active", "value": True}]}, {"tracker": {
        "program": {"initial": "idle", "states": {
            "idle":     {"every": 0.1, "next": [{"goto": "tracking", "when": ["work.task.id > 0", "session.active"]}]},
            "tracking": {"do": [{"add": {"name": "work.task.spent", "expr": 10}}], "every": 0.1,
                         "next": [{"goto": "checking", "when": "work.task.spent >= work.task.estimate"}, {"goto": "tracking"}]},
            "checking": {"do": [{"poke": {"context": {"format": "Still on {name}?", "values": {"name": "work.task.name"}}}},
                                {"set": {"name": "work.task.status", "expr": "\"done\""}}], "every": 0.1, "next": "idle"}}}}})
    built(path)
    intro = task(board, "Write the intro")  # 40 min
    hold(board, intro)
    for minute in range(6):
        await tick(at(minute))
    assert value_of(board, "spent", intro) == 40 and [t["status"] for t in board.tasks.current() if t["id"] == intro] == ["done"]
    assert ui.sent[-1]["text"] == "Still on Write the intro?"
    assert setters(board.tasks, "spent") == ["tracker"]  # its action says so
    Program.stop()


def test_a_reserved_prefix_is_a_programs_own(tmp_path):
    from conftest import built, programs_folder
    from proki.errors import ConfigError

    with pytest.raises(ConfigError, match="'work' is reserved"):
        built(programs_folder(tmp_path, {"variables": [{"name": "work", "value": 0}]}))
