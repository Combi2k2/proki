# F-009 Apps and labels

| Status | Area | Code |
| --- | --- | --- |
| ⚪ Not reviewed | Insight | `ui/src/views/apps.tsx`, `proki/programs/code/classify.py`, `classify.json`, `proki/assets/labels.json` |

How each app or website counts: deep work, shallow work, a break, or a distraction.

## How it works
- `classify` labels each window in focus from a similar title, Proki's list, Jev, the LLM, or you.
- A label's category sets the window's `depth`, which the focus score reads ([F-012](F-012-signals.md)).
- The Apps page lists every app and site with its label, who gave it, how sure, and whether
  it's tracked. A label you pick is yours and never asked about again.
- Filter by what's left to you, search, and sort by any column.

## Limits
- A new app's depth stays unknown until it has a label; none is invented.
- The page and its wording haven't been reviewed yet.
