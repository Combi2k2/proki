"""The standard ActivityWatch distribution and its separately bundled input watcher."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("launch", Path(__file__).resolve().parents[1] / "launch.py")
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)


def setup_launcher(monkeypatch, tmp_path, *, input_present=True, external_input=False):
    monkeypatch.setattr(launch.settings, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(launch.platforms, "current", lambda: SimpleNamespace(
        EXE=".exe", NATS_DIRS=[], AW_DIRS=[tmp_path]))
    def commands(names, directories, suffix):
        if names == launch.INPUT and not input_present:
            return None
        return {name: [str(tmp_path / f"{name}{suffix}")] for name in names}
    monkeypatch.setattr(launch, "find_commands", commands)
    monkeypatch.setattr(launch.ActivityWatchClient, "is_up", lambda self: True)
    monkeypatch.setattr(launch.ActivityWatchClient, "buckets", lambda self:
        {"input": {"type": "os.hid.input"}} if external_input else {})
    from datetime import UTC, datetime
    monkeypatch.setattr(launch.ActivityWatchClient, "events", lambda *a, **kw:
        [{"timestamp": datetime.now(UTC).isoformat(), "duration": 5}])


def test_standard_aw_and_input_are_managed_separately(monkeypatch, tmp_path):
    setup_launcher(monkeypatch, tmp_path)
    services = launch.services(app=True)
    assert set(services["ActivityWatch"].commands) == {"aw-server", "aw-watcher-window", "aw-watcher-afk"}
    watcher = services["ActivityWatch Input"]
    assert set(watcher.commands) == {"aw-watcher-input"}
    assert watcher.start_when_healthy  # an existing AW server must not skip the watcher


def test_missing_input_does_not_hide_an_installed_aw(monkeypatch, tmp_path):
    setup_launcher(monkeypatch, tmp_path, input_present=False)
    services = launch.services(app=True)
    assert "ActivityWatch" in services and "ActivityWatch Input" not in services


def test_existing_input_is_left_alone_but_our_crashed_one_is_recovered(monkeypatch, tmp_path):
    setup_launcher(monkeypatch, tmp_path, external_input=True)
    assert "ActivityWatch Input" not in launch.services(app=True)
    pids = tmp_path / "logs" / "activitywatch-input" / "pids"
    pids.parent.mkdir(parents=True)
    pids.write_text("123")
    assert "ActivityWatch Input" in launch.services(app=True)
