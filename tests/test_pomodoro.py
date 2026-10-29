"""The pomodoro: the focus session, a program of the config (programs/config/pomodoro.json)."""

import shutil

from proki import settings
from proki.core.programs import Program
from proki.core.signals import Stream
from proki.engine import Engine
from test_rituals import config, local, runner

STAND_INS = {"typing": True, "focus_2m": 0.8, "focus_2m_rise": 0.0,
             "session.active": False, "session.requested": False, "session.stop_requested": False, "distracted_below": 0.35}


def session(tmp_path, **values):
    """The program, with stand-ins for what it reads. `active` is a signal, as in the app
    (a value every cycle): set `typing` to change it."""
    path = config(tmp_path, {"inputs": [{"name": "daytime"}, {"name": "time"}],
                             "variables": [{"name": n, "value": v} for n, v in {**STAND_INS, **values}.items()],
                             "signals": [{"name": "active", "expr": "typing"}]})
    shutil.copyfile(settings.SHIPPED_DIR / "pomodoro.json", path / "pomodoro.json")
    run = runner(Engine(path))
    return Program.registry["pomodoro"], run


def value(name):
    return Stream.registry[name].current()


async def test_a_requested_session_runs_and_stops_when_asked(tmp_path, ui):
    program, run = session(tmp_path)
    await run(local(5, 10, 0))
    await run(local(5, 10, 1), **{"session.requested": True})
    assert program.current == "focusing" and value("session.active") and not value("session.requested")
    assert ui.sent[-1]["text"].startswith("Focus session started")
    await run(local(5, 10, 21))
    assert 20 <= value("session.minutes") <= 21
    await run(local(5, 10, 22), **{"session.stop_requested": True})
    assert program.current == "idle" and not value("session.active") and not value("session.stop_requested")


async def test_slipping_focus_is_poked_once_a_minute(tmp_path, ui):
    program, run = session(tmp_path)
    await run(local(5, 10, 0), **{"session.requested": True})
    await run(local(5, 10, 5))
    await run(local(5, 10, 7, 30), focus_2m=0.1)
    pokes = [m for m in ui.sent if m["type"] == "poke" and "slipping" in m["text"]]
    assert len(pokes) == 3  # 10:05:10, then each minute it stays low


async def test_past_25_minutes_a_dip_asks_whether_its_done(tmp_path, ui):
    program, run = session(tmp_path)
    await run(local(5, 10, 0), **{"session.requested": True})
    await run(local(5, 10, 30), focus_2m=0.1)
    [asked] = ui.questions()
    assert asked["context"] == "Your focus has dropped. Is this session done?"
    await ui.click("Stop session")
    await run(local(5, 10, 31))
    assert not value("session.active")


async def test_away_pokes_with_a_sound_and_ten_minutes_end_it(tmp_path, ui):
    program, run = session(tmp_path)
    await run(local(5, 10, 0), **{"session.requested": True})
    await run(local(5, 10, 5))
    await run(local(5, 10, 6, 50), typing=False)
    assert program.current == "focusing"  # not yet: `active` turns false 3 minutes after the last input
    await run(local(5, 10, 7, 20))
    away = ui.sent[-1]
    assert program.current == "away" and away["title"] == "You've been away"
    assert away["media"].endswith("bugcat/what.gif") and away["sound"].endswith("alarm-clock.mp3")  # it rings until you close it
    await run(local(5, 10, 8), typing=True)
    assert program.current == "focusing" and ui.sent[-1] == away  # nothing more to say

    await run(local(5, 10, 14, 50), typing=False)
    assert value("session.active")
    await run(local(5, 10, 15, 30))
    assert program.current == "idle" and not value("session.active")
    assert ui.sent[-1]["text"].startswith("Your focus session ended")


async def test_a_session_from_before_a_restart_is_over(tmp_path, ui):
    """session.active is global, so it's kept across a restart. The program starts over, so the
    session it ran is over."""
    program, run = session(tmp_path, **{"session.active": True})
    await run(local(5, 10, 0))
    await run(local(5, 10, 0, 10))
    await run(local(5, 10, 0, 20))
    assert program.current == "idle" and not value("session.active")


async def test_after_50_minutes_its_time_to_wrap_up(tmp_path, ui):
    program, run = session(tmp_path)
    await run(local(5, 10, 0), **{"session.requested": True})
    await run(local(5, 10, 49))
    assert not ui.questions()
    await run(local(5, 10, 51))
    assert ui.questions()[-1]["context"] == "50 minutes of focus. Time to wrap up and take a real break."
