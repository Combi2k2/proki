"""proki and what it needs, started together and kept running.

    uv run launch.py

    NATS            the message bus the engine and the app talk over
    ActivityWatch   what records the windows you're in
    engine          proki itself: your programs, and their tools
    UI              the app: the tray, the popups, the windows

Each is started once the one before it answers, and started again if it stops. Quit in the
app, or Ctrl-C here, stops them all. One already running is left as it is.
"""

from __future__ import annotations

import signal
import sys
import time

from proki import platforms, settings
from proki.services.activitywatch import ActivityWatchClient
from proki.services.nats import NatsBus
from proki.services.supervisor import Supervisor
from proki.utils import find_commands

CYCLE = 60  # seconds between checks of the services

# the programs started for each service, the server first
NATS = ["nats-server"]      # its address is added as it's started
AW   = [
    "aw-server",
    "aw-watcher-window",    # aw.WINDOW
    "aw-watcher-afk",       # aw.AFK
    "aw-watcher-input",     # aw.INPUT: counts of key presses and clicks (never which keys)
]                           # aw.WEBTAB comes from the browser extension


def services() -> dict[str, Supervisor]:
    """Each service there is, by name, in the order it's started; the ones not there, said why."""
    here    = platforms.current()
    release = settings.FRONTEND_DIR / "app" / "target" / "release"
    built   = next((path for path in (release / "bundle" / "macos" / "proki.app" / "Contents" / "MacOS" / "proki-ui",
                                      release / f"proki-ui{here.EXE}") if path.exists()), None)
    nats    = find_commands(NATS, here.NATS_DIRS, here.EXE)
    at      = ["-a", settings.HOST, "-p", str(settings.NATS_PORT)]
    flags   = [f"--nats={settings.HOST}:{settings.NATS_PORT}", f"--tools={settings.HOST}:{settings.TOOLS_PORT}", f"--tools-token={settings.TOOLS_TOKEN}"]
    made    = {}
    for name, commands, up, missing in [  # its programs (none: it isn't there, `missing` says what to do), whether it answers
        ("NATS",          nats and {"nats-server": [*nats["nats-server"], *at]}, lambda: NatsBus.is_up(settings.HOST, settings.NATS_PORT),             "nats-server not found (brew install nats-server): the app can't connect"),
        ("ActivityWatch", find_commands(AW, here.AW_DIRS, here.EXE),             ActivityWatchClient(settings.HOST, settings.AW_PORT).is_up,           "ActivityWatch not found: install it, or start it yourself"),
        ("engine",        {"engine": [sys.executable, "-m", "proki"]},           lambda: NatsBus.is_up(settings.HOST, settings.TOOLS_PORT),            ""),
        ("UI",            built and {"ui": [str(built), *flags]},                lambda: (ui := made["UI"].processes.get("ui")) and ui.poll() is None, f"the UI isn't built: run `npm install` then `npm run app` in {settings.FRONTEND_DIR}"),
    ]:
        if commands:
            made[name] = Supervisor(name, commands, up, settings.LOG_DIR / name.lower(), timeout=30)
        else:
            print(missing, flush=True)
    return made


def main() -> int:
    """Start each service, keep them running, and stop them all as the engine quits, or as
    you stop this."""
    started = services()
    engine  = started["engine"]
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # stopped from outside: as Ctrl-C
    try:
        for service in started.values():
            print(service.start(), flush=True)
        checked = time.monotonic()
        while True:
            time.sleep(1)
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
    raise SystemExit(main())
