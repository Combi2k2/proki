"""Your programs kept in proki.db (storage.SpecDB), and the defaults proki ships coming
into them (programs/shipped.py)."""

import json
import sqlite3

import pytest

from proki import settings, storage
from proki.core.programs import Program
from proki.engine import Engine
from proki.model import Defaults
from proki.programs.shipped import Shipped


@pytest.fixture
def db():
    db = sqlite3.connect(":memory:")
    db.executescript(storage.SCHEMA)
    return db


def day(model):
    return Defaults.dump(model.specs, "day")


def test_your_programs_are_kept_as_they_change(db):
    kept = storage.SpecDB(db)
    assert kept.load() is None  # nothing kept yet
    e = Engine(settings.SHIPPED_DIR, keep=kept.save)
    e.model.update("state", {"program": "day", "name": "idle"}, {"desc": "mine"})
    assert kept.load() == e.model.specs
    assert db.execute("SELECT desc FROM spec_states WHERE program = 'day' AND name = 'idle'").fetchone() == ("mine",)


def test_a_program_you_never_changed_follows_its_default(db):
    shipped, e = Shipped(settings.SHIPPED_DIR, storage.StateDB(db)), Engine(settings.SHIPPED_DIR)
    shipped.update(e.model)  # the first time: each default, as taken
    older = {**day(e.model), "desc": "as it was shipped before"}
    e.model.swap("day", Defaults.parse({}, {"day": older}))
    taken = shipped.taken()
    storage.StateDB(db).set(Shipped.KEY_SHIPPED, {**taken, "day.json": older})  # taken when it said so
    shipped.update(e.model)
    assert day(e.model) == Defaults.dump(shipped.default("day"), "day")  # the default now
    assert Program.registry["day"].desc == shipped.default("day").programs[0].desc


def test_a_program_you_changed_stays_yours(db):
    shipped, e = Shipped(settings.SHIPPED_DIR, storage.StateDB(db)), Engine(settings.SHIPPED_DIR)
    shipped.update(e.model)
    e.model.update("program", {"name": "day"}, {"desc": "mine"})
    taken = shipped.taken()
    storage.StateDB(db).set(Shipped.KEY_SHIPPED, {**taken, "day.json": {**taken["day.json"], "desc": "older"}})
    shipped.update(e.model)  # a new default came, and yours isn't as it was taken
    assert Program.registry["day"].desc == "mine"


def test_a_new_default_comes_in_and_a_removed_one_stays_away(db, tmp_path):
    from conftest import programs_folder

    shipped = Shipped(settings.SHIPPED_DIR, storage.StateDB(db))
    e = Engine(programs_folder(tmp_path, json.loads((settings.SHIPPED_DIR / "main.json").read_text())))  # no programs yet
    shipped.update(e.model)
    assert {"day", "suggest", "bedtime"} <= set(Program.registry)  # new: in
    e.model.remove("program", {"name": "evening"})
    shipped.update(e.model)
    assert "evening" not in Program.registry  # you removed it: it stays so


def test_a_file_goes_back_to_its_default(db):
    shipped, e = Shipped(settings.SHIPPED_DIR, storage.StateDB(db)), Engine(settings.SHIPPED_DIR)
    e.model.update("program", {"name": "day"}, {"desc": "mine"})
    shipped.revert(e.model, "day")
    assert day(e.model) == Defaults.dump(shipped.default("day"), "day")
    with pytest.raises(ValueError, match="no default"):
        shipped.revert(e.model, "mine")


def test_a_default_you_set_is_the_one_it_goes_back_to(db):
    shipped, e = Shipped(settings.SHIPPED_DIR, storage.StateDB(db)), Engine(settings.SHIPPED_DIR)
    shipped.update(e.model)
    e.model.update("program", {"name": "day"}, {"desc": "mine"})
    shipped.pin(e.model, "day")
    e.model.update("program", {"name": "day"}, {"desc": "mine, then more"})
    shipped.revert(e.model, "day")
    assert Program.registry["day"].desc == "mine"  # yours, not proki's

    taken = shipped.taken()
    storage.StateDB(db).set(Shipped.KEY_SHIPPED, {**taken, "day.json": {**taken["day.json"], "desc": "older"}})
    shipped.update(e.model)  # a new default came: yours stays
    assert Program.registry["day"].desc == "mine"

    shipped.unpin("day")
    shipped.revert(e.model, "day")
    assert day(e.model) == Defaults.dump(shipped.shipped("day"), "day")  # proki's again


def test_a_program_of_your_own_can_have_a_default(db):
    shipped, e = Shipped(settings.SHIPPED_DIR, storage.StateDB(db)), Engine(settings.SHIPPED_DIR)
    e.model.add("program", {"name": "late", "desc": "mine"})
    with pytest.raises(ValueError, match="no default"):
        shipped.revert(e.model, "late")
    shipped.pin(e.model, "late")
    e.model.update("program", {"name": "late"}, {"desc": "changed"})
    shipped.revert(e.model, "late")
    assert Program.registry["late"].desc == "mine"
    with pytest.raises(KeyError):
        shipped.pin(e.model, "nobody")
