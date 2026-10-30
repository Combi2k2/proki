"""Check the bundled watcher's event compatibility without starting OS input listeners."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def test_keydowns_are_adapted_to_the_historical_input_event_counts(monkeypatch):
    package = ModuleType("aw_watcher_input")
    watcher = ModuleType("aw_watcher_input.main")
    class Keydowns:
        def next_event(self):
            return {"presses": 3}
    watcher.KeyboardListener = Keydowns
    package.main = watcher
    monkeypatch.setitem(sys.modules, "aw_watcher_input", package)
    monkeypatch.setitem(sys.modules, "aw_watcher_input.main", watcher)
    spec = importlib.util.spec_from_file_location("bundled_input", Path(__file__).resolve().parents[1] / "packaging/input-watcher.py")
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    from proki.core.primitives.aw.keys import Keys
    assert Keys().count(watcher.KeyboardListener().next_event()) == 3
