# F-011 Automations

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Make it yours | `ui/src/views/programs.tsx`, `program-graph.tsx`, `program-forms.tsx`, `proki/editor.py`, `proki/core/programs.py`, `proki/programs/` |

The routines behind every prompt: read them, switch them off, and change them.

## How it works
- Each automation (a program) is a state machine. A state's actions run as it's entered:
  set a variable, ask you, Jev or the LLM, poke, lock, open a page. Its ways out read signals,
  variables and rules.
- The list is every automation, one card each, found by its tags (the most used on top, each card's tags clickable) or a search; it has no groups of its own.
- Scopes: Global, then a program, then a state. The Resources bubble lists what the scope can
  use (inputs, signals, variables, rules), the same global ones from anywhere.
- Each one opens a dialog, changed where it's read: its type, its value, its fields, what writes
  it (expr, auto, user, proki) and what reads it. A place in an automation opens there, lit,
  from any page.
- A program is drawn as a graph you can arrange; the live view shows the state now and when
  it next wakes.
- Every change is checked before it's kept, and one that breaks something is refused.
- Proki ships 15 programs (`proki/programs/config/`). One you never changed follows Proki's
  updates; one you changed stays yours. Reset brings it back to its default.
- The questions Proki asks on its own (a session suggestion, a reminder, a new app's label…)
  share one quiet gap: `nudge_gap`, 30 minutes by default, in the global settings. One you leave
  unanswered makes the next wait twice as long. Questions you start yourself, a session's own,
  and bedtime don't wait for it.
- Pin a working version as its default, keep editing, and reset back to it; unpin to return
  to Proki's. A pinned program keeps yours through Proki's updates.

## Limits
- Which action of a state is running isn't shown; most finish within one cycle.
- Pin and unpin aren't in the app or the MCP tools yet: only the engine has them.
- A value you set yourself holds only until an automation writes it: the last write wins.
