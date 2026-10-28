"""The day clock: each minute at the computer counted by how focused, and each new day and week
starting its counts afresh (programs/config/day.json)."""

import shutil
from datetime import datetime, timedelta

from proki import settings
from proki.core.programs import Program
from proki.core.signals import Stream
from proki.engine import Engine
from test_rituals import config, runner

STAND_INS = {"active": True, "focus": 0.8, "focused_above": 0.5, "distracted_below": 0.35, "focus_goal": 2}


def clock(tmp_path):
    """The program, with stand-ins for what it reads: set `focus` and `active` to change them."""
    path = config(tmp_path, {"inputs": [{"name": n} for n in ("daytime", "time", "weekday", "dd", "mm")],
                             "variables": [{"name": n, "value": v} for n, v in STAND_INS.items()]})
    shutil.copyfile(settings.SHIPPED_DIR / "day.json", path / "day.json")
    run = runner(Engine(path))
    return Program.registry["day"], run


def value(name):
    return Stream.registry[name].current()


def at(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute).astimezone()


async def test_each_minute_counts_by_how_focused_you_were(tmp_path):
    _, run = clock(tmp_path)
    await run(at(2026, 10, 21, 10, 0))
    await run(at(2026, 10, 21, 10, 5))
    await run(at(2026, 10, 21, 10, 8), focus=0.4)
    await run(at(2026, 10, 21, 10, 10), focus=0.1)
    await run(at(2026, 10, 21, 10, 13), active=False)
    counts = {n: value(f"{n}_today") for n in ("focused", "shallow", "active")}
    assert 4 <= counts["focused"] <= 6 and 2 <= counts["shallow"] <= 4
    assert 1 <= counts["active"] - counts["focused"] - counts["shallow"] <= 3  # distracted; away: none of them
    assert value("focused_week") == counts["focused"]


async def test_a_monday_starts_the_week_afresh_and_the_streak_goes_on(tmp_path):
    day, run = clock(tmp_path)
    await run(at(2026, 10, 25, 23, 50))  # a Sunday
    await run(at(2026, 10, 25, 23, 55))
    assert value("focused_week") >= 2
    await run(at(2026, 10, 26, 0, 1), step=timedelta(minutes=1))
    await run(at(2026, 10, 26, 0, 2))
    assert value("goal_streak") == 1 and value("focused_week") <= 1
    assert day.current == "idle" and value("deadline_eod") > value("time")

