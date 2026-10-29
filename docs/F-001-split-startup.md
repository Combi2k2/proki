# F-001: the engine, the app, and what starts them

## Objective

Today `proki` (`proki/app.py`) is three things at once: the engine, the one that finds and starts
NATS, ActivityWatch and the app, and the one that restarts them when they stop. It knows each
service's folders on each OS, the app's build folders, and the app's flags. Split it in three:

    proki           the engine alone: the bus, your programs, the tools, a cycle at a time
    ui/             the app alone: it finds the engine by itself, started by whoever
    launch.py       what starts the others (NATS, ActivityWatch, the engine, the app), keeps them
                    running, and stops them all when one says to quit

Scale: standard. Complexity: medium. 4 slices.

## What there is

- `proki/app.py`: `main` (the tools' port check, `services()`, `running`); `services` builds a
  `Supervisor` each for NATS, ActivityWatch and the app; `running`'s loop checks them every `CYCLE`,
  and purges the media there too.
- `proki/services/supervisor.py` (frozen): `start`, `check` (the stopped ones started again),
  `stop`, a pid file each, a log each. It does for the engine what it does for the others.
- `proki/utils.find_commands` (frozen), `proki/platforms/*` (`AW_DIRS`, `NATS_DIRS`, `EXE`).
- `ui/app/src/main.rs`: `--nats` (default `127.0.0.1:4222`), `--tools` (default `127.0.0.1:9144`),
  `--tools-token` (the token's path, default none). The app's "Quit proki" asks `proki.app.quit`;
  the engine stops and sends `{"type": "quit"}`, and the app exits. One app at a time.
- `pyproject.toml`: `proki = "proki.app:main"`; `proki/__main__.py` runs it (`python -m proki`).
- `tests/test_bus.py` imports `NATS` from `proki.app`. README's "run it" section.

## Slices

    Slice 1: the launcher, the engine alone        no dependencies
    Slice 2: the app finds the engine by itself     no dependencies       (parallel with 1)
    Slice 3: the engine waits for the bus           depends on 1
    Slice 4: the docs                               depends on 1, 2, 3

## Tasks

Slice 1: the launcher, the engine alone                                              done
  AC: `uv run launch.py` starts NATS, ActivityWatch, the engine and the app; the app killed is
  back within a minute, the engine killed within seconds; "Quit proki" stops all four; Ctrl-C does too.

  [x] 1.1 launch.py (new, at the root): `NATS`, `AW`, `CYCLE` moved from app.py; the services
          a table (name, programs, whether it answers, what to do if it isn't there); the engine
          one of them (`python -m proki`, up when its tools' port answers); checked every
          `CYCLE`, the engine every second: exit code 0 stops them all, anything else restarts it.
          Ctrl-C (twice, as a terminal and uv send it) and SIGTERM stop them all, in reverse.
  [x] 1.2 proki/app.py: the engine alone; the media purged as it starts and every hour (`PURGE`).
  [x] 1.3 tests/test_bus.py finds nats-server itself; `proki` and `python -m proki` stay the engine.

Slice 2: the app finds the engine by itself                                          done
  AC: with the engine running, proki.app opened by itself (Finder, no flags) shows your
  programs and calls their tools.

  [x] 2.1 ui/app/src/main.rs: `--tools-token` defaults to where the engine keeps it (the user's
          config folder, `proki/tools-token`; on Windows `%LOCALAPPDATA%\proki\proki`); the flags
          stay, for another setup. The comment at the top: whoever starts it, not the engine.
  [x] 2.2 the launcher still passes the flags: they say where the engine is, whatever the
          defaults; the app opened from Finder uses the defaults (checked on macOS).

Slice 3: the engine waits for the bus                                                done
  AC: `proki-engine` started before NATS connects to it once it's up (up to a timeout), rather
  than running on a bus of its own that the app can't reach.

  [x] 3.1 proki/app.py `running`: wait for NATS (`wait_until`, its health check) before the
          in-process bus; the in-process bus only when it never comes, said once.

Slice 4: the docs
  AC: README's "run it" says the three commands, and each file's docstring says what it is.

  [ ] 4.1 README.md (run it, the layout), proki/app.py's docstring (the engine only),
          ui/package.json's description ("The engine (Python) starts it" goes).

## Anti-rationalization check

- 1.1 moved code and added a loop in one task: kept together, since the engine can't drop
  `services()` before the launcher has it (two `proki`s for a while is worse). It stays under
  ~150 lines; split if it doesn't.
- No "clean it up later": the services' table is how 1.1 is written, not a second pass.
- Each slice's AC is checked by running it, not just the tests: the tests don't start processes.

## Risks

    RISK: the app's default token path differs from the engine's on Windows (platformdirs puts
          it under %LOCALAPPDATA%\proki\proki, Tauri's config folder is %APPDATA%)
    IMPACT: the app opened alone gets 401 from the tools on Windows
    LIKELIHOOD: high, if it's written with Tauri's folder
    MITIGATION: the Windows path written as platformdirs makes it; the launcher still passes
          --tools-token on Windows until it's tried there

    RISK: the launcher can't tell "asked to quit" from "crashed" for the engine
    IMPACT: Quit restarts the engine, or a crash stops everything
    LIKELIHOOD: medium
    MITIGATION: the engine's exit code (0 on quit, as `main` returns), read before `check()`
          restarts it

    RISK: a `proki` still running the old way (it starts the app itself) alongside the new one
    IMPACT: two apps, two engines on one database
    LIKELIHOOD: low (the tools' port check stops the second engine; the app is single-instance)
    MITIGATION: the port check stays in the engine; the launcher checks the port too, first

    RISK: scripts/windows/proki.bat is already out of date (it imports proki.config, writes .env)
    IMPACT: the Windows install breaks either way
    LIKELIHOOD: high
    MITIGATION: out of this feature; it's its own (its last step becomes `-m proki`, as now)

## Checkpoint gates

- Gate 0: done: the startup code, the supervisor, the app's flags and its quit read.
- Gate 1: slice 1's AC, run for real (start, kill the app, quit from the tray, Ctrl-C).
- Gate 2: slice 2's AC, proki.app opened from Finder.
- Gate 3: slice 3's AC: NATS started 10 s after the engine.
- Gate final: the suite passes, ruff clean, README followed from a fresh terminal.

## Decisions

- The launcher is Python, at the root (launch.py, `uv run launch.py`), not a shell script: the
  supervisor and the commands' search already work on each OS, and are frozen; a shell script
  needs a .bat twin.
- Outside the package, so `proki` stays the engine alone, and no new entry point is needed.
- Then the engine, app.py, folded into proki/__main__.py: "app" is the UI everywhere else, and
  `engine` is taken (proki/engine/); `proki = "proki.__main__:main"`.
- The app finds the token by the same path, rather than asking the engine for it over the bus:
  fewer moving parts; the flag stays for anything else.
- The packaged app, later: it takes the launcher's place (the engine as its sidecar). Nothing
  here stands in the way, since the engine knows nothing of the app.
