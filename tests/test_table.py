"""A kind of record's table: read as it is now, written by id, fields worked out from `self`."""

from __future__ import annotations

import copy

import pytest

from proki.core.actions import Set
from proki.core.records.field import Field
from proki.core.records import Record, Records
from proki.core.signals import Expr, Variable
from proki.errors import ExprError, VariableError
from proki.storage import VariableDB, connect, record_tables

FIELDS = [Field("title", srcs=[{"from": "user"}], type="string"),
          Field("status", srcs=[{"from": "auto", "initial": "todo"}], type="string"),
          Field("estimate", srcs=[{"from": "user"}], type="number"),
          Field("double", srcs=[{"from": "expr", "expr": "me.estimate * 2"}], type="number")]


@pytest.fixture
def db(tmp_path):
    return connect(tmp_path / "proki.db")


@pytest.fixture
def tasks(db):
    return Records("work.tasks", db, "task", FIELDS, record_tables(db, "task"))


def test_a_record_written_is_read_back_with_its_fields_worked_out(tasks):
    tasks.set([{"title": "a", "estimate": 3}, {"title": "b"}])
    a, b = tasks.current()
    assert (a["title"], a["status"], a["double"], b["double"]) == ("a", "todo", 6, None)
    assert Expr("work.tasks[0].double").value() == 6
    assert Expr("work.tasks[1].status").value() == "todo"


def test_the_table_is_kept_as_its_list_says(tasks):
    tasks.set([{"title": "a"}, {"title": "b"}])
    a, b = tasks.current()
    tasks.set([b, {"title": "c"}])
    assert [(r["id"], r["title"]) for r in tasks.current()] == [(b["id"], "b"), (b["id"] + 1, "c")]


async def test_a_field_of_one_set_as_a_program_says(tasks):
    tasks.set([{"title": "a"}, {"title": "b"}])
    await Set("work.tasks[1].status", "'done'").apply()
    await Set("work.tasks[0].estimate", "1").apply()
    assert [(r["title"], r["status"], r["double"]) for r in tasks.current()] == [("a", "todo", 2), ("b", "done", None)]


def test_a_copy_set_changes_nothing_until_it_is_kept(tasks):
    tasks.set([{"title": "a"}])
    copied = copy.deepcopy(tasks.current()[0])
    copied["estimate"] = 5
    assert copied["double"] == 10 and tasks.current()[0]["double"] is None
    tasks.add_row(copied)
    assert tasks.current()[0]["double"] == 10


def test_updated_at_moves_only_as_a_field_changes(tasks):
    tasks.set([{"title": "a"}])
    a = tasks.current()[0]
    tasks.db.execute("UPDATE records_task SET updated_at = 0")
    Records.writes += 1  # written behind its back: read again
    tasks.add_row(tasks.current()[0])
    assert tasks.current()[0]["updated_at"] == 0
    tasks.add_row(tasks.current()[0] | {"title": "b"})
    assert tasks.current()[0]["updated_at"] > 0 and tasks.current()[0]["created_at"] == a["created_at"]


def test_a_field_not_of_its_type_is_not_kept(tasks):
    with pytest.raises(VariableError):
        tasks.set([{"title": 3}])
    assert tasks.current() == []


async def test_a_record_is_its_row_by_id_and_set_writes_it(tasks, db):
    Variable.store = VariableDB(db)
    task = Record("work.task", tasks)
    assert task.current() is None
    tasks.set([{"title": "a"}, {"title": "b"}])
    await Set("work.task", "work.tasks[1]").apply()
    await Set("work.task.estimate", "4").apply()
    assert (task.current()["title"], tasks.current()[1]["double"], tasks.current()[0]["double"]) == ("b", 8, None)
    assert Record("work.task", tasks).current()["title"] == "b"   # there again after a restart
    tasks.set([tasks.current()[0]])
    assert task.current() is None


def test_a_field_of_yours_defined_renamed_and_removed(tasks):
    tasks.set([{"title": "a", "estimate": 2}])
    tasks.define(Field("effort", srcs=[{"from": "user"}], type="number"))
    tasks.define(Field("total", srcs=[{"from": "expr", "expr": "me.effort + me.double"}], type="number"))
    tasks.add_row(tasks.current()[0] | {"effort": 1})
    assert tasks.current()[0]["total"] == 5
    tasks.rename("effort", "work")
    assert (tasks.current()[0]["work"], tasks.current()[0]["total"]) == (1, 5)
    with pytest.raises(ExprError):
        tasks.define(Field("bad", srcs=[{"from": "expr", "expr": "nothing + 1"}]))
    assert "bad" not in tasks.fields
    tasks.remove("total")
    assert "total" not in tasks.current()[0] and tasks.current()[0].get("total") is None


def test_a_field_redefined_and_removed_is_back_as_it_came(tasks):
    tasks.set([{"title": "a", "estimate": 2}])
    tasks.define(Field("double", srcs=[{"from": "expr", "expr": "me.estimate * 3"}], type="number"))
    assert tasks.current()[0]["double"] == 6
    tasks.remove("double")
    assert Records("work.tasks", tasks.db, "task", FIELDS, record_tables(tasks.db, "task")).current()[0]["double"] == 4


def test_a_formula_reads_other_records(tasks):
    tasks.define(Field("same", srcs=[{"from": "expr", "expr": "len(where(work.tasks, work.tasks.title, me.title))"}], type="number"))
    tasks.set([{"title": "a"}, {"title": "a"}, {"title": "b"}])
    assert [r["same"] for r in tasks.current()] == [2, 2, 1]


def test_a_field_that_reads_itself_is_none(tasks):
    tasks.define(Field("loop", srcs=[{"from": "expr", "expr": "me.loop + 1"}], type="number"))
    tasks.set([{"title": "a"}])
    assert tasks.current()[0]["loop"] is None


async def test_a_field_worked_out_is_not_set(tasks):
    tasks.set([{"title": "a", "estimate": 1}])
    with pytest.raises(VariableError):
        await Set("work.tasks[0].double", "3").apply()
    assert tasks.current()[0]["double"] == 2


def test_a_fields_jev_ask_is_checked_as_ask_jev_checks_it():
    Field("size", srcs=[{"from": "jev", "type": "score", "question": "How big?", "criteria": {"1": "tiny", "10": "huge"}}])
    with pytest.raises(ValueError):
        Field("size", srcs=[{"from": "jev", "type": "nope", "question": "How big?"}])
