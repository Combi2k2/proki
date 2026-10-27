from datetime import datetime, timedelta, timezone

from conftest import built, replay
from proki.services.activitywatch import Event, Record
from proki.core.primitives import Depth
from proki.core.signals import Stream
from proki.model import Defaults
from proki import settings
from proki.core.rules import Rule

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def test_the_shipped_signals_see_focus_building():
    # on YouTube until minute 6, then 4 minutes coding, typing steadily: focus is building up
    depth = {"Google Chrome": 0.0, "Code": 1.0}
    recorded = {
        "currentwindow": [Event(at(0), at(6), {"app": "Google Chrome", "title": "Video - YouTube"}),
                          Event(at(6), at(10), {"app": "Code", "title": "client.py"})],
        "os.hid.input": [Event(at(6 + i / 12), at(6 + (i + 1) / 12), {"presses": 8}) for i in range(48)],
    }
    Depth.depth_of = lambda app, title: depth.get(app)
    signals = built(settings.SHIPPED_DIR).streams
    Stream.now = at(0)  # cycles from minute 0
    replay(at(10), Record.of(at(0), at(10), recorded))
    values = {signal.name: signal.current() for signal in signals}
    assert values["focus"] == 1 and values["on_deep"] is True and values["focus_rise"] > 0.15


def test_every_shipped_signal_compiles_and_runs():
    signals = {s.name: s for s in built(settings.SHIPPED_DIR).streams}
    Stream.now = at(0)
    replay(at(1), Record.of(at(0), at(1), {}))  # every expression compiles on its first cycle
    shipped = Defaults(settings.SHIPPED_DIR).specs()
    top = lambda name: "." not in name or name.split(".")[0] in ("session", "note")  # a global one, or one in the session's or the notes' namespace
    named = {name for name in Stream.registry if top(name)} - {"task", "track", "asking", "work"}  # not the rules' sides, nor what code made
    global_ = {name for name in signals if top(name)}
    scoped = [*shipped.variables, *shipped.rules]
    assert {s.name for s in [*shipped.inputs, *(s for s in [*shipped.signals, *shipped.variables] if s.scope == "global")]} == global_ == named
    assert {"answer", "asked_done", "on_shallow", "snoozed_until"} <= {name.split(".")[-1] for name in signals if not top(name)}  # the programs' and states' own
    assert {s.full() for s in shipped.rules} == set(Rule.registry) and all(s.scope != "program" or s.program for s in scoped)
    assert signals["focus_history"].persist and signals["focus_history"].window == timedelta(days=7)


def test_configs_are_checked(tmp_path):
    import pytest

    bad = tmp_path / "main.json"
    for text, problem in [('{"signals": [{"name": "x", "expr": "keys_pressed", "windw": 5}]}', "unknown windw"),
                          ('{"signals": [{"name": "x", "backfill": 5}]}', "expr is missing"),
                          ('{"signals": [{"name": "x", "expr": "keys_pressed", "backfill": true}]}', "backfill is a number"),
                          ('{"signals": [{"name": "x", "expr": "keys_pressed", "persist": true}]}', "persist needs a backfill"),
                          ('{"signals": [{"expr": "keys_pressed"}]}', "name is missing"),
                          ('{"signals": [{"name": "x", "expr": "1"}, {"name": "x", "expr": "2"}]}', "twice"),
                          ('{"signals": [{"name": "x", "expr": "kes + 1"}]}', "unknown name 'kes'"),
                          ('{"inputs": [{"name": "keys_pressed"}], "signals": [{"name": "keys_pressed", "expr": "1"}]}', "twice"),
                          ('{"inputs": [{"name": "keyz"}]}', "no input is called 'keyz'"),
                          ('{"inputs": [{"name": "keys_pressed", "backfill": true}]}', "backfill is a number"),
                          ('{"flows": []}', "a section: unknown flows"),
                          *(('{"cycle": %s}' % cycle, "cycle is in seconds") for cycle in ("0", "-5", '"10"', "true"))]:
        bad.write_text(text)
        with pytest.raises(ValueError, match=problem):
            Stream.registry.clear()
            built(bad.parent)


def test_inputs_keep_the_backfill_they_ask_for(tmp_path):
    config = tmp_path / "main.json"
    config.write_text('{"inputs": [{"name": "keys_pressed", "backfill": 60}, {"name": "app_name"}]}')
    keys, app = built(config.parent).inputs
    assert (keys.backfill, keys.window) == (True, timedelta(hours=1))
    assert (app.backfill, app.window) == (False, None)
    replay(at(120), Record.of(at(0), at(120), {}))  # the first run goes back as far as the longest table
    assert len(keys.history(at(0))) == 360


def test_the_cycle_comes_from_the_config(tmp_path):
    """Windows are time, not a count of cycles: a slower cycle gives the same means, fewer rows."""
    typing = {"os.hid.input": [Event(at(m / 12), at((m + 1) / 12), {"presses": 2 * (m // 12)}) for m in range(10 * 12)]}  # per minute
    results = {}
    for cycle in (10, 30):
        Stream.registry.clear()
        config = tmp_path / f"cycle{cycle}" / "main.json"
        config.parent.mkdir()
        config.write_text('{"cycle": %d, "inputs": [{"name": "keys_pressed", "backfill": 60}], '
                          '"signals": [{"name": "keys_5m", "expr": "ts_mean(keys_pressed, 5)"}]}' % cycle)
        built(config.parent)
        assert Stream.cycle == timedelta(seconds=cycle)
        Stream.now = at(0)
        replay(at(10), Record.of(at(0), at(10), typing))
        results[cycle] = Stream.registry["keys_5m"].current(), len(Stream.registry["keys_pressed"].history(at(0)))
    assert results[10][0] == results[30][0]
    assert (results[10][1], results[30][1]) == (60, 20)


def test_what_the_app_reads_of_the_config_is_there_and_checked_as_its_built(tmp_path):
    import pytest
    from conftest import programs_folder
    from proki.engine import Engine
    from proki.errors import ConfigError
    from proki.serve import READS

    Engine(settings.SHIPPED_DIR, reads=READS)  # the shipped config has every one, of its type
    Stream.registry.clear()
    with pytest.raises(ConfigError, match="the app reads focus_5m: there's none"):
        Engine(programs_folder(tmp_path, {"variables": [{"name": "x", "value": 1}]}), reads={"focus_5m": "number"})
    Stream.registry.clear()
    with pytest.raises(ConfigError, match="the app reads x, of type boolean: it's of type number"):
        Engine(programs_folder(tmp_path, {"variables": [{"name": "x", "value": 1}]}), reads={"x": "boolean"})
