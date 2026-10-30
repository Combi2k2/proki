"""proki and what it needs, started together and kept running.

    uv run launch.py                the launcher, from here
    proki-engine [--from-app]       the same, as the app ships it (--from-app: the app started it)
    proki-engine engine             the engine alone, as the launcher starts it there
    proki-engine mcp                the tools, for an AI agent that starts them as a command

    NATS            the message bus the engine and the app talk over
    ActivityWatch   what records the windows you're in
    engine          proki itself: your programs, and their tools
    UI              the app: the tray, the popups, the windows

Each is started once the one before it answers, and started again if it stops. Quit in the
app, or Ctrl-C here, stops them all. One already running is left as it is. ActivityWatch, if
it's nowhere, is installed for you (in proki's data folder) and started once it's there.
"""

from __future__ import annotations

import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import requests

from proki import platforms, settings
from proki.services.activitywatch import ActivityWatchClient
from proki.services.nats import NatsBus
from proki.services.supervisor import Supervisor
from proki.utils import find_commands

CYCLE  = 60                                     # seconds between checks of the services
FROZEN = getattr(sys, "frozen", False)          # shipped in the app, as one program: the engine is it too
STARTS = {"engine": 300}                        # seconds a service may take to answer (else 30): the engine waits on you if the keychain asks

# the programs started for each service, the server first
NATS = ["nats-server"]      # its address is added as it's started
AW   = [                    # the modules included in ActivityWatch's standard download
    "aw-server",
    "aw-watcher-window",    # aw.WINDOW
    "aw-watcher-afk",       # aw.AFK
]                           # aw.WEBTAB comes from the browser extension
INPUT = ["aw-watcher-input"]  # discovered separately: a missing input watcher must not hide an installed AW

AW_HOME = settings.DATA_DIR / "activitywatch"   # where it's installed for you, if it was nowhere
AW_URL  = "https://github.com/ActivityWatch/activitywatch/releases/download/v0.14.1/activitywatch-v0.14.1-{}.zip"
AW_ZIPS = {                                     # its release for this machine, by OS and processor
    ("darwin", "arm64"):  "macos-arm64",
    ("darwin", "x86_64"): "macos-x86_64",
    ("win32",  "AMD64"):  "windows-x86_64",
}


def services(app: bool) -> dict[str, Supervisor]:
    """Each service there is, by name, in the order it's started; the ones not there, said why.
    `app`: the app started this, so it isn't started again."""
    here    = platforms.current()
    release = settings.FRONTEND_DIR / "app" / "target" / "release"
    inside  = Path(sys.executable).parents[2]   # shipped: the app's resources (macOS), or its folder (Windows)
    built   = next((path for path in ([
        inside.parent / "MacOS" / "proki",
        inside / f"proki{here.EXE}"] if FROZEN else [
        release / "bundle" / "macos" / "proki.app" / "Contents" / "MacOS" / "proki-ui",
        release / "bundle" / "macos" / "proki.app" / "Contents" / "MacOS" / "proki",
        release / f"proki-ui{here.EXE}"
    ]) if path.exists()), None)
    nats      = find_commands(NATS,  [Path(sys.executable).parent, *here.NATS_DIRS] if FROZEN else here.NATS_DIRS, here.EXE)  # shipped, its own first
    aw_client = ActivityWatchClient(settings.HOST, settings.PORTS.activitywatch)
    aw_flags  = ["--host", settings.HOST, "--port", str(settings.PORTS.activitywatch)]
    if aw_commands := find_commands(AW, [*here.AW_DIRS, AW_HOME], here.EXE):
        aw_commands = {name: [*command, *aw_flags] for name, command in aw_commands.items()}
    at     = ["-a", settings.HOST, "-p", str(settings.PORTS.nats)]
    flags  = [f"--nats={settings.HOST}:{settings.PORTS.nats}", f"--tools={settings.HOST}:{settings.PORTS.tools}", f"--tools-token={settings.TOOLS_TOKEN}"]
    engine = [sys.executable, *(["engine"] if FROZEN else ["-m", "proki"])]   # shipped, it's this program again
    made   = {}
    for name, commands, up, missing in [  # its programs (none: it isn't there, `missing` says what to do), whether it answers
        ("ActivityWatch", aw_commands,                                           aw_client.is_up,           "ActivityWatch not found: installing it for you"),
        ("NATS",          nats and {"nats-server": [*nats["nats-server"], *at]}, lambda: NatsBus.is_up(settings.HOST, settings.PORTS.nats),             "nats-server not found (brew install nats-server): the app can't connect"),
        ("engine",        {"engine": engine},                                    lambda: NatsBus.is_up(settings.HOST, settings.PORTS.tools),            ""),
        ("UI",            built and {"ui": [str(built), *flags]},                lambda: (ui := made["UI"].processes.get("ui")) and ui.poll() is None, f"the UI isn't built: run `npm install` then `npm run app` in {settings.FRONTEND_DIR}"),
    ]:
        if name == "UI" and app:
            continue
        if commands:
            made[name] = Supervisor(name, commands, up, settings.LOG_DIR / name.lower(), timeout=STARTS.get(name, 30))
        else:
            print(missing, flush=True)
    if (input_commands := find_commands(INPUT, [Path(sys.executable).parent, settings.ROOT_DIR / "build" / "engine" / "proki-engine", *here.AW_DIRS, AW_HOME], here.EXE)) and ("ActivityWatch" in made or aw_client.is_up()):
        input_commands = {name: [*command, *aw_flags] for name, command in input_commands.items()}
        # An external server must not prevent our watcher starting; leave a recently
        # reporting external watcher alone, but recover one left behind by Proki.
        from datetime import UTC, datetime, timedelta
        try:
            recent = any(datetime.fromisoformat(e["timestamp"]) + timedelta(seconds=e["duration"]) > datetime.now(UTC) - timedelta(minutes=1)
                         for key, bucket in aw_client.buckets().items() if bucket.get("type") == "os.hid.input"
                         for e in aw_client.events(key, limit=1))
        except (requests.RequestException, KeyError, TypeError, ValueError):
            recent = False
        if not recent or (settings.LOG_DIR / "activitywatch-input" / "pids").exists():
            made["ActivityWatch Input"] = Supervisor("ActivityWatch Input", input_commands, aw_client.is_up,
                settings.LOG_DIR / "activitywatch-input", timeout=30, start_when_healthy=True)
    elif not input_commands:
        print("Input watcher not found: rebuild the installer with packaging/build.sh", flush=True)
    return made


def install_aw() -> None:
    """ActivityWatch installed where proki looks for it, from its release for this machine (none:
    nothing done): said how it went."""
    build = AW_ZIPS.get((sys.platform, platform.machine()))
    if not build:
        print("ActivityWatch has no release for this machine: install it yourself", flush=True)
        return
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zipped = Path(tmp) / "activitywatch.zip"
            with requests.get(AW_URL.format(build), stream=True, timeout=60) as got, zipped.open("wb") as kept:
                got.raise_for_status()
                for chunk in got.iter_content(1 << 20):
                    kept.write(chunk)
            if sys.platform == "darwin":  # its programs kept runnable
                subprocess.run(["ditto", "-x", "-k", str(zipped), tmp], check=True)
            else:
                zipfile.ZipFile(zipped).extractall(tmp)
            AW_HOME.parent.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(AW_HOME, ignore_errors=True)
            shutil.move(Path(tmp) / "activitywatch", AW_HOME)
    except (OSError, requests.RequestException, subprocess.CalledProcessError, zipfile.BadZipFile) as e:
        print(f"ActivityWatch couldn't be installed ({e}): install it yourself", flush=True)
        return
    print(f"ActivityWatch installed in {AW_HOME}", flush=True)


def main() -> int:
    """Start each service, keep them running, and stop them all as the engine quits, or as
    you stop this."""
    settings.configure_ports()
    app        = "--from-app" in sys.argv
    started    = services(app)
    engine     = started["engine"]
    installing = None if "ActivityWatch" in started else threading.Thread(target=install_aw, daemon=True)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # stopped from outside: as Ctrl-C
    try:
        for service in started.values():
            print(service.start(), flush=True)
        if installing:
            installing.start()
        checked = time.monotonic()
        while True:
            time.sleep(1)
            if installing and not installing.is_alive():  # ActivityWatch is there now, or never will be
                installing = None
                for name, service in services(app).items():
                    if name.startswith("ActivityWatch") and name not in started:
                        started[name] = service
                        print(service.start(), flush=True)
            ended = (process := engine.processes.get("engine")) and process.poll()  # None: it runs, or isn't ours
            if ended == 0:  # it was asked to quit
                break
            if ended is not None or time.monotonic() - checked >= CYCLE:  # it crashed, or it's time
                checked = time.monotonic()
                for module in (m for service in started.values() for m in service.check()):
                    print(f"restarted {module}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # a second Ctrl-C doesn't cut the stopping short
        for service in reversed(started.values()):
            service.stop()
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] in (["engine"], ["mcp"]):
        from proki.__main__ import main as engine
        raise SystemExit(engine())
    raise SystemExit(main())
