from __future__ import annotations

import sqlite3

import pytest

from proki.core.actions import Append, Set
from proki.core.signals import Stream
from proki.errors import VariableError
from proki.programs.code.base import find_variable, make_variable
from proki.programs.code.work import Work
from proki.tools import records
from proki.storage import SCHEMA


@pytest.fixture
def board():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA)
    board = Work(db)
    records.add("work.groups", None, name="Thesis")
    find_variable("work.group").set(board.groups.get_row(1))
    return board


def ops(board):
    return sorted(board.ops.read(), key=lambda op: op.id)


async def test_the_plan_is_one_object_its_changes_a_table_on_the_card(board):
    plan = {"name": "Thesis", "desc": "the venue first", "tags": ["papers"], "questions": ["Which venue?"],
            "changes": [{"op": "add", "name": "Book the venue", "estimate": 30}]}
    find_variable("work.plan").set(plan)
    [op] = ops(board)
    assert (op.op, op.group, op.fields) == ("add", 1, {"name": "Book the venue", "estimate": 30, "key": "book_the_venue"})  # the group at hand's
    assert find_variable("work.plan").current() == plan | {"changes": [
        {"op": "add", "task": None, "name": "Book the venue", "desc": None, "done_when": None, "checkpoint": None, "estimate": 30, "after": None}]}
    assert find_variable("work.plan.name").current() == "Thesis"
    find_variable("work.plan").set(None)
    assert find_variable("work.plan").current() is None and ops(board) == []


async def test_the_changes_set_are_the_plans_from_now_on_the_group_at_hands(board):
    find_variable("work.plan").set({"changes": [{"op": "add", "name": "Draft"}, {"op": "add", "name": "Send"}]})
    await Set(name="work.plan.changes[0].estimate", expr="20").apply()
    assert [(op.fields["name"], op.fields.get("estimate")) for op in ops(board)] == [("Draft", 20), ("Send", None)]
    await Set(name="work.plan.changes", expr="work.plan.changes[1:]").apply()
    assert [op.fields["name"] for op in ops(board)] == ["Send"]
    await Append(name="work.groups", expr={"name": "'Errands'"}).apply()
    await Set(name="work.group", expr="work.groups[-1]").apply()
    await Set(name="work.plan", expr="work.plan").apply()
    assert [op.group for op in ops(board)] == [2]  # the new group's
    with pytest.raises(VariableError, match="of type"):
        find_variable("work.plan.changes").set([{"op": "nope"}])  # add, change or remove


async def test_a_slice_is_a_part_of_a_list_and_pops_one(board):
    from proki.core.signals.expr import Expr
    queue = make_variable("queue", [1, 2, 3])
    make_variable("word", "abc")
    await Set(name="queue", expr="queue[1:]").apply()  # a pop
    assert queue.current() == [2, 3]
    for expr, value in [("queue[:1]", [2]), ("queue[-1:]", [3]), ("queue[5:]", []), ("word[1:]", None)]:
        assert Expr(expr).value() == value, expr


async def test_a_change_is_planned_only_if_the_group_can_take_it_each_task_by_its_key(board):
    read = records.add("work.tasks", None, group=1, name="Read the papers")
    records.add("work.tasks", None, group=1, name="Take notes", after=[read])
    done = records.add("work.tasks", None, group=1, name="Pick a topic")
    records.change("work.tasks", done, None, status="done")
    find_variable("work.plan").set({"changes": [
        {"op": "change", "task": "Take notes", "estimate": 90, "after": []},
        {"op": "remove", "task": "read_the_papers"},
        {"op": "remove", "task": "pick_a_topic"},           # done: none
        {"op": "change", "task": "nope", "name": "x"},      # no such task: none
        {"op": "add"},                                      # no name: none
        {"op": "add", "name": "Take notes", "after": ["take_notes", "Read the papers", "nope"]},
        {"op": "add", "name": "Write it up", "after": ["take_notes_2", "write_it_up"]}]})

    change, remove, add, write = ops(board)
    assert (change.op, change.task, change.fields, change.after) == ("change", "take_notes", {"estimate": 90}, [])
    assert (remove.op, remove.task) == ("remove", "read_the_papers")
    assert (add.fields["key"], add.after) == ("take_notes_2", ["take_notes", "read_the_papers"])  # a key of its own; known ones
    assert write.after == ["take_notes_2"]  # one planned before it, not itself


async def test_a_group_is_made_and_set_its_tags_known_ones_three_at_most(board):
    from proki.core.signals.expr import Expr
    await Append(name="work.groups", expr={"name": "'Groceries'", "tags": "['shopping', 'food', 'cooking']"}).apply()
    await Set(name="work.group", expr="work.groups[-1]").apply()
    groups = board.groups.current()
    assert [g["name"] for g in groups] == ["Thesis", "Groceries"] and groups[1]["tags"] == ["shopping", "food", "cooking"]
    assert Expr("work.group.name").value() == "Groceries"  # the one at hand
    for tags in (["nope"], ["food", "food"], ["shopping", "food", "cooking", "errands"]):  # not a tag there is; twice; four
        with pytest.raises(VariableError, match="of type"):
            await Set(name="work.group.tags", expr=repr(tags)).apply()
    assert "papers" in Expr("choices(work.group.tags)").value()
    await Set(name="work.groups[0].desc", expr="'my master\\'s thesis'").apply()
    assert board.groups.current()[0]["desc"] == "my master's thesis" and Expr("work.group.outline").value().startswith(
        "It goes with their group of tasks “Groceries”")
