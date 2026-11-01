# F-004 Focus sessions

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Your day | `proki/programs/config/pomodoro.json`, `task_picker.json`, `task_tracker.json`, `suggest.json` |

A timed stretch on one task, with gentle prompts when your focus slips or a break is due.

## How it works
- Start one from the tray, from a task ("work on it"), or by accepting a suggestion when Proki
  notices you're in the flow (`suggest`).
- `task_picker` asks what the session is for; `task_tracker` counts the time on that task and
  checks you're still on it.
- `pomodoro` times the session, nudges you when focus stays low, and suggests a break.
- Each day's session minutes are kept for a year (`session.daily`, see [F-010](F-010-metrics.md)).
- All of it is automations: read and change them in [F-011](F-011-automations.md).

## Limits
- No session starts while Proki is paused ([F-002](F-002-tray-and-pause.md)).
