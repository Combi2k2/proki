import sys

from proki.services.activitywatch import ActivityWatchSupervisor, aw_detect

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


def supervisor(tmp_path, server_up=None):
    """Stand-in programs; by default the server is healthy once it has been launched."""
    commands = {"aw-server": SLEEPER, "aw-watcher-afk": SLEEPER, "aw-watcher-window": SLEEPER}
    s = ActivityWatchSupervisor(commands, lambda: False, tmp_path / "logs", timeout=0.1)
    s.healthy = server_up or (lambda: "aw-server" in s.processes)
    return s


def test_starts_every_module_and_stops_them(tmp_path):
    s = supervisor(tmp_path)
    s.start()
    processes = list(s.processes.values())
    assert list(s.processes) == ["aw-server", "aw-watcher-afk", "aw-watcher-window"]
    assert all(p.poll() is None for p in processes)
    s.stop()
    assert all(p.poll() is not None for p in processes) and s.processes == {}


def test_gives_up_when_the_server_never_comes_up(tmp_path):
    s = supervisor(tmp_path, server_up=lambda: False)
    assert "failed to start" in s.start()
    assert s.processes == {}  # the server it launched is stopped again; no watchers


def test_leaves_an_already_running_activitywatch_alone(tmp_path):
    s = supervisor(tmp_path, server_up=lambda: True)
    assert "already running" in s.start()
    assert s.processes == {} and s.check() == []


def test_restarts_a_module_that_crashed(tmp_path):
    s = supervisor(tmp_path)
    s.start()
    crashed = s.processes["aw-watcher-afk"]
    crashed.kill()
    crashed.wait()
    assert s.check() == ["aw-watcher-afk"]
    assert s.processes["aw-watcher-afk"] is not crashed
    s.stop()


def test_detects_programs_in_the_first_directory_with_all_of_them(tmp_path):
    for name in ("aw-watcher-window", "aw-server"):
        (tmp_path / name).touch()
    commands = aw_detect([tmp_path / "missing", tmp_path], "", ["aw-watcher-window", "aw-server"])
    assert commands == {name: [str(tmp_path / name)] for name in ("aw-watcher-window", "aw-server")}
    assert aw_detect([tmp_path], "", ["aw-server", "aw-watcher-afk"]) is None


def test_takes_over_programs_left_behind_by_a_crashed_run(tmp_path):
    first = supervisor(tmp_path)
    first.start()
    leftovers = list(first.processes.values())  # the first run "crashes": never calls stop()
    second = supervisor(tmp_path)
    second.start()
    for p in leftovers:
        p.wait(timeout=5)  # the old ones were stopped...
    assert all(p.poll() is None for p in second.processes.values())  # ...and fresh ones started
    second.stop()


def test_detects_programs_in_per_program_folders(tmp_path):
    # the Windows / Linux layout: activitywatch/aw-server/aw-server.exe
    for module in ["aw-server", "aw-watcher-afk"]:
        (tmp_path / module).mkdir()
        (tmp_path / module / f"{module}.exe").write_text("")
    commands = aw_detect([tmp_path], ".exe", ["aw-watcher-afk", "aw-server"])
    assert set(commands) == {"aw-server", "aw-watcher-afk"}
    assert commands["aw-server"] == [str(tmp_path / "aw-server" / "aw-server.exe")]


def test_optional_watchers_are_found_elsewhere_or_skipped(tmp_path, monkeypatch):
    import proki.services.activitywatch.utils as aw

    app, tools = tmp_path / "app", tmp_path / "tools"
    app.mkdir(), tools.mkdir()
    for m in ["aw-server", "aw-watcher-afk"]:
        (app / m).write_text("")
    monkeypatch.setattr(aw, "UV_TOOLS", tools)
    monkeypatch.setattr(aw.shutil, "which", lambda name: None)
    assert "aw-watcher-input" not in aw_detect([app], "", ["aw-server", "aw-watcher-afk"], ["aw-watcher-input"])
    (tools / "aw-watcher-input").write_text("")
    found = aw_detect([app], "", ["aw-server", "aw-watcher-afk"], ["aw-watcher-input"])
    assert found["aw-watcher-input"] == [str(tools / "aw-watcher-input")]
