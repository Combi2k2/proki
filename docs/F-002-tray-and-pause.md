# F-002 Tray panel and pause

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Getting started | `ui/src/pages/tray.tsx`, `ui/app/src/tray.rs`, `proki/serve.py` (`proki.app.tracking`) |

Proki lives in the menu bar (macOS) or the system tray (Windows). Its panel shows your focus now
and puts the everyday actions one click away.

## How it works
- Focus of the last minutes as a dial, coloured by your focus lines (see [F-003](F-003-today.md)).
- Open Proki, New session or End session (with its time), New note, Settings, Quit.
- Pause stops Proki's cycles: nothing is seen or asked meanwhile, a running session ends, and no
  new one starts. On resume, the paused time isn't replayed.
- Launch at login turns the OS's start-up entry on or off.
- The tray's menu (installed app only) has Install command-line tool, for [F-016](F-016-mcp.md).

## Limits
- Pause is Proki's only: ActivityWatch keeps recording.
- After a restart while paused, the day's windows start empty when you resume: the time before
  the pause isn't replayed either. Saved signals ([F-010](F-010-metrics.md)) keep their past.
