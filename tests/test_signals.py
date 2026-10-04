from datetime import datetime, timedelta, timezone

from proki.legacy.rules.suggest_session import suggest_session
from proki.services.activitywatch import Event, Record
from proki.core.signals import Depth, Primitive, Stream
from proki.compiler import CONFIG, compile_config, editable_copy
from proki.core.rules import Rule

T0 = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def test_default_signals_feed_the_suggest_session_pipeline():
    # on YouTube until minute 6, then 4 minutes coding, typing steadily: focus is building up
    depth = {"Google Chrome": 0.0, "Code": 1.0}
    recorded = {
        "currentwindow": [Event(at(0), at(6), {"app": "Google Chrome", "title": "Video - YouTube"}),
                          Event(at(6), at(10), {"app": "Code", "title": "client.py"})],
        "os.hid.input": [Event(at(6 + i / 12), at(6 + (i + 1) / 12), {"presses": 8}) for i in range(48)],
    }
    state = {"in_session": False, "shutdown_done": False, "popup_open": False, "minutes_since_suggested": 999}
    Depth.depth_of = lambda app, title: depth.get(app)
    signals = compile_config().streams
    Stream.now = at(0)  # cycles from minute 0
    Primitive.run(at(10), Record.of(at(0), at(10), recorded))
    values = {**state, **{signal.name: signal.current() for signal in signals}}  # as the app does
    assert values["focus"] == 1 and values["on_deep"] is True and values["focus_rise"] > 0.15
    assert suggest_session().decide(values)


def test_every_shipped_signal_compiles_and_runs():
    import json

    signals = {s.name: s for s in compile_config().streams}
    Stream.now = at(0)
    Primitive.run(at(1), Record.of(at(0), at(1), {}))  # every expression compiles on its first cycle
    shipped = json.loads(CONFIG.read_text())
    named = {name for name in Stream.registry if "." not in name}  # not the rules' sides
    assert {e["name"] for e in shipped["inputs"] + shipped["variables"] + shipped["signals"]} == set(signals) == named
    assert {e["name"] for e in shipped["rules"]} == set(Rule.registry)
    assert signals["focus_history"].persist and signals["focus_history"].window == timedelta(days=7)


def test_configs_are_checked(tmp_path):
    import pytest

    bad = tmp_path / "config.json"
    for text, problem in [('{"signals": [{"name": "x", "expr": "keys", "windw": 5}]}', "unknown windw"),
                          ('{"signals": [{"name": "x", "window": 5}]}', "needs an expr"),
                          ('{"signals": [{"expr": "keys"}]}', "needs a name"),
                          ('{"signals": [{"name": "x", "expr": "1"}, {"name": "x", "expr": "2"}]}', "twice"),
                          ('{"signals": [{"name": "x", "expr": "kes + 1"}]}', "unknown name 'kes'"),
                          ('{"inputs": [{"name": "keys"}], "signals": [{"name": "keys", "expr": "1"}]}', "twice"),
                          ('{"inputs": [{"name": "keyz"}]}', "no input is called 'keyz'"),
                          ('{"inputs": [{"name": "keys", "backfill": true}]}', "in minutes"),
                          ('{"flows": []}', "unknown section flows")]:
        bad.write_text(text)
        with pytest.raises(ValueError, match=problem):
            Stream.registry.clear()
            compile_config(bad)


def test_an_editable_copy_is_made_once(tmp_path):
    mine = editable_copy(tmp_path / "config.json")
    assert mine.read_text() == CONFIG.read_text()
    mine.write_text(mine.read_text().replace('"cycle": 10', '"cycle": 30'))
    assert '"cycle": 30' in editable_copy(mine).read_text()  # yours is kept


def test_inputs_keep_the_backfill_they_ask_for(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"inputs": [{"name": "keys", "backfill": 60}, {"name": "app"}]}')
    keys, app = compile_config(config).inputs
    assert (keys.backfill, keys.window) == (True, timedelta(hours=1))
    assert (app.backfill, app.window) == (False, None)
    Primitive.run(at(120), Record.of(at(0), at(120), {}))  # the first run goes back as far as the longest table
    assert len(keys.history(at(0))) == 360


def test_the_cycle_comes_from_the_config(tmp_path):
    """Windows are time, not a count of cycles: a slower cycle gives the same means, fewer rows."""
    typing = {"os.hid.input": [Event(at(m / 12), at((m + 1) / 12), {"presses": 2 * (m // 12)}) for m in range(10 * 12)]}  # per minute
    results = {}
    for cycle in (10, 30):
        Stream.registry.clear()
        config = tmp_path / f"config{cycle}.json"
        config.write_text('{"cycle": %d, "inputs": [{"name": "keys", "backfill": 60}], '
                          '"signals": [{"name": "keys_5m", "expr": "ts_mean(keys, 5)"}]}' % cycle)
        compile_config(config)
        assert Stream.cycle == timedelta(seconds=cycle)
        Stream.now = at(0)
        Primitive.run(at(10), Record.of(at(0), at(10), typing))
        results[cycle] = Stream.registry["keys_5m"].current(), len(Stream.registry["keys"].history(at(0)))
    assert results[10][0] == results[30][0]
    assert (results[10][1], results[30][1]) == (60, 20)


def test_the_cycle_is_checked(tmp_path):
    import pytest

    config = tmp_path / "config.json"
    for cycle in ("0", "-5", '"10"', "true"):
        config.write_text('{"cycle": %s}' % cycle)
        with pytest.raises(ValueError, match="cycle is in seconds"):
            compile_config(config)


def test_your_copy_gets_what_the_shipped_config_adds(tmp_path):
    import json

    mine = tmp_path / "config.json"
    shipped = json.loads(CONFIG.read_text())
    edited = {"inputs": [{"name": "keys", "backfill": 5}],  # yours: changed
              "signals": [{"name": "mine", "expr": "keys * 2"}],  # yours: added
              "rules": []}
    mine.write_text(json.dumps(edited))
    editable_copy(mine)
    synced = json.loads(mine.read_text())
    inputs = {e["name"]: e for e in synced["inputs"]}
    assert inputs["keys"] == {"name": "keys", "backfill": 5}  # your version stays
    assert set(inputs) == {e["name"] for e in shipped["inputs"]}  # the rest are added
    assert synced["signals"][0]["name"] == "mine"  # yours first, kept
    assert {e["name"] for e in synced["rules"]} == {e["name"] for e in shipped["rules"]}
    assert synced["cycle"] == shipped["cycle"] and synced["variables"] == shipped["variables"]

    before = mine.stat().st_mtime_ns, mine.read_text()
    editable_copy(mine)  # nothing new: left alone
    assert (mine.stat().st_mtime_ns, mine.read_text()) == before
