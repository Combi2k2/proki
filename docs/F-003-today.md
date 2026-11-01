# F-003 Today

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Your day | `ui/src/views/today.tsx`, `proki/serve.py` (`proki.app.today`) |

Where you are now and what to do next, on one page.

## How it works
- Your focus today as its spread from scattered to focused, with the minutes in each band and
  your focus now moving along it.
- The focus lines between the bands: drag one to move it, double-click to add or remove one.
  They're the `focus_lines` variable, so automations read the same bands.
- Progress toward your daily focus goal (`focus_goal`, 240 minutes unless you change it).
- Your tasks, the next one first ([F-006](F-006-tasks.md)), and a box to note a thought ([F-007](F-007-notes.md)).
- The automations helping you today, each opening in the editor ([F-011](F-011-automations.md)).
- The page is resizable panels, kept as you leave them.

## Limits
- "Today" starts at 4 am, so late work counts toward the day before.
