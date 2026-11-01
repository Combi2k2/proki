# F-006 Tasks and plans

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Your work | `ui/src/views/tasks.tsx`, `proki/programs/code/work.py`, `proki/serve.py` (`proki.app.tasks`) |

Your work as a board: groups of tasks under tags, with the next task picked for you and an AI
to break a todo into steps.

## How it works
- A card per group, in the row of its most relevant tag; drag a card along a row or into
  another of its tags. A group opens to its tasks as a checklist.
- Everything is edited in place and saved as you leave the field.
- Tasks are weighed by their fields (estimate, deadline, ...) so the next one comes first. Add
  fields of your own in [F-013](F-013-tables.md).
- `task_planner` turns a todo note into a group's tasks, linked back to the note, and suggests
  next steps, shown on the group's card for you to accept or not.
- `task_reminder` mentions tasks that are due soon or stuck, at a quiet moment.
- "Work on it" starts a focus session on a task ([F-004](F-004-focus-sessions.md)).

## Limits
- The planner needs an LLM set up ([F-015](F-015-ai-services.md)).
