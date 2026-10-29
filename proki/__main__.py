"""proki: the engine, headless. What it needs (the message bus, ActivityWatch) and the app are
started by the launcher, or by you.

    proki            run it: your programs, served on the bus and as tools
    proki mcp        its tools, for an AI agent that starts them as a command (proki started if it isn't)

What it does, once:
1. serves on the bus: jev and the LLM, and what the app asks for
2. builds your programs, takes in the defaults proki ships, and serves them as tools, for
   the app and for an AI agent

Then, every cycle: the inputs and signals move on, the programs whose wait is over wake up,
and the tray's line shows the focus. Every hour, the media deleted a week ago is gone for good.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from datetime import datetime, timezone

from proki import channels, platforms, settings, storage
from proki.channels import Channels, Popup
from proki.core.actions import Lock, Open, Poke
from proki.core.primitives import Recording
from proki.core.signals import Stream
from proki.engine import Engine
from proki.metrics import Metrics
from proki.migrate import migrate
from proki.model import Defaults
from proki.programs.code.base import Live, popup_open
from proki.programs.code.classify import AppDB, Apps, Track
from proki.programs.code.work import Work
from proki.programs.shipped import Shipped
from proki.serve import READS, current, serve
from proki.services import activitywatch as aw, nats
from proki.services.media import Library
from proki.tools.server import Tools
from proki.utils import wait_until

PURGE = 3600  # seconds between purges of the media deleted a week ago
LATE  = 0.1   # seconds past a cycle's time it runs, so it's due
BUS   = 10    # seconds it waits for the message bus's server, if it's starting too


def main() -> int:
    """Run, until the app or a signal says to stop; or, with `mcp`, the tools for an agent."""
    if sys.argv[1:2] == ["mcp"]:
        from proki.tools import stdio
        return stdio.main()
    config = settings.load()
    if nats.NatsBus.is_up(settings.HOST, settings.TOOLS_PORT):
        print(f"port {settings.TOOLS_PORT} is in use: proki may be running already. Quit it first; nothing was started.", flush=True)
        return 1
    asyncio.run(running(config))
    return 0


async def running(config: settings.Settings) -> None:
    """The bus served, your programs built and served as tools, then a cycle at a time until proki's told to stop."""
    new = not settings.DB_PATH.exists()
    db  = storage.connect(settings.DB_PATH)
    migrate(db, new)
    work, apps, stopping = Work(db), Apps(AppDB(db)), asyncio.Event()

    up = lambda: nats.NatsBus.is_up(settings.HOST, settings.NATS_PORT)
    wait_until(up, BUS)  # its server, if it's starting too
    try:
        bus = await nats.NatsBus.connect(settings.HOST, settings.NATS_PORT) if up() else nats.LocalBus()
    except Exception:
        bus = nats.LocalBus()
    if isinstance(bus, nats.LocalBus):  # one in this process: the app can't reach it
        print("no message bus: the app can't connect (start nats-server, then proki again)", flush=True)
    Channels.bus = bus
    await channels.jev.serve(bus, config.jev)  # as they're set in the app, from then on
    await channels.llm.serve(bus, config.llm)

    Poke.handler, Open.handler = Popup.poke, Popup.open
    library = Popup.lib = Library(db, settings.ASSETS_DIR, settings.MEDIA_DIR, pools=[Popup.POOL])
    library.purge()
    Lock.handler = platforms.current().lock_screen  # the engine locks the screen itself
    Recording.client = aw.ActivityWatchClient(settings.HOST, settings.AW_PORT)
    history = Stream.storage = storage.HistoryDB(db)
    kept    = storage.SpecDB(db)
    if (specs := kept.load()) is None:  # the first time: your programs' folder if you had one (read once, then left as it is), else proki's
        specs = Defaults(settings.PROGRAMS_DIR if (settings.PROGRAMS_DIR / Defaults.MAIN).exists() else settings.SHIPPED_DIR).specs()
        kept.save(specs)
    engine  = Engine(specs, variables=storage.VariableDB(db), switches=storage.SwitchDB(db),
                     keep=kept.save, reads=READS, programs=[
                         Track(apps).make,
                         work.make,
                         lambda: Live("asking", popup_open, "whether a question waits for you", "boolean"),
                     ])
    await serve(bus, work, quit=stopping.set, metrics=Metrics(db, history), signals=lambda: engine.compiled.signals,
                apps=apps, reload=engine.reload, model=engine.model)
    shipped = Shipped(settings.SHIPPED_DIR, storage.StateDB(db))
    shipped.update(engine.model)
    tools   = Tools(engine, shipped, library, stores=[work], config=config).http(settings.TOOLS_PORT, Tools.token(settings.TOOLS_TOKEN))
    serving = asyncio.create_task(tools.serve())

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:  # Windows: a plain handler, handed to the loop
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stopping.set))
    print("proki is running", flush=True)
    purged = loop.time()
    while not stopping.is_set():
        try:  # a cycle, and the tray's line: the focus of the last 5 minutes, and the running session's minutes
            await engine.cycle(datetime.now(timezone.utc))
        except (OSError, RuntimeError) as e:  # ActivityWatch not running, or not ready yet
            Popup.send({"type": "status", "text": f"waiting for ActivityWatch ({e.__class__.__name__})"})
        else:
            focus, minutes = current("focus_5m"), current("session.minutes") if current("session.active") else None
            Popup.send({"type": "status", "text": "focus –" if focus is None else f"focus {focus:.2f} (5 min)",
                        "session": None if minutes is None else int(minutes)})
        if loop.time() - purged >= PURGE:
            purged = loop.time()
            library.purge()
        every = Stream.cycle.total_seconds()  # until the next cycle: the programs run with the signals, never on ones a cycle old
        try:
            await asyncio.wait_for(stopping.wait(), every - datetime.now(timezone.utc).timestamp() % every + LATE)
        except TimeoutError:
            pass

    engine.close()
    Popup.send({"type": "quit"})  # the app closes, and its connection to the tools with it
    tools.should_exit = True
    await serving
    await bus.close()


if __name__ == "__main__":
    raise SystemExit(main())
