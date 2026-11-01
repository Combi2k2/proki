# NF-001 Architecture

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Everything | `launch.py`, `proki/__main__.py`, `proki/engine/`, `proki/serve.py`, `ui/app/` |

Four processes on this computer, talking over a local message bus.

## How it works
- **Launcher** (`launch.py`, or the app in a release): starts NATS, ActivityWatch, the engine and
  the app, each once the one before answers, and restarts any that stops.
- **Engine** (Python): every cycle (10 s) the inputs move on, then the programs whose wait is
  over wake up ([F-011](F-011-automations.md), [F-012](F-012-signals.md)).
- **App** (Tauri, React): the tray, popups and main window. It asks the engine over NATS
  (`proki.app.*`, see `serve.py`'s docstring).
- **Tools server**: the MCP tools over HTTP on 127.0.0.1 ([F-016](F-016-mcp.md)).
- Questions to you, Jev and the LLM go over the bus, one worker each.
- Everything you make is kept in `proki.db` (SQLite): programs, records, history, state.

## Limits
- One worker per service: a slow LLM answer holds the next question.
