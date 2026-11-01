# F-007 Notes

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Your work | `ui/src/views/notes.tsx`, `proki/programs/config/note_sorter.json`, `capture.json`, `proki/serve.py` (`proki.app.notes`) |

Note a thought anywhere; Proki sorts it into a todo, an idea or a thought, and asks when unsure.

## How it works
- Notes come from the tray, Today, or a prompt (`capture` asks now and then, `shutdown` at the
  end of the day).
- `note_sorter` sorts each one with Jev's guess, asking you when it isn't sure.
- Ideas and thoughts stay here: edit, move between them, delete, or add one.
- Unsorted notes have their own tab: sort one now, file it yourself, or leave it for later.
- Todos go on to the task planner, and each says which group it became ([F-006](F-006-tasks.md)).

## Limits
- Without Jev, every note is asked about ([F-015](F-015-ai-services.md)).
