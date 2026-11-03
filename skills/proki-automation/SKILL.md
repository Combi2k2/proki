---
name: proki-automation
description: Create, change, explain and troubleshoot Proki automations (programs) through the Proki MCP tools, from what the user says in everyday words. Use whenever the user wants Proki to remind, nudge, ask, notice, track, count, lock, start a session or check in on something ("remind me to stretch every hour", "ask me at 5 what I finished", "stop nagging me during calls", "make the break reminder gentler"); when they ask why an automation did or didn't fire; when they ask how Proki's programs, states, rules, signals or variables work; or when they want one turned off, reset, cleaned up or reworded. Not for writing Proki's Python code.
metadata:
  version: 2.0.0
---

# Proki automations

Proki watches the computer (the app in focus, keys and mouse, the clock) and runs **programs**: small
state machines that decide when to poke, ask, or do something. This skill turns what a person wants, in
their own words, into a program that behaves the way they meant, and answers any question about how
programs work.

The user should never need to know the mechanism. They say *what* and *when*; you work out the states,
rules and expressions, show them the behaviour in plain words, build it, and check it.

**Core principles**

1. **The user's intent wins, not the model's habits.** Build what they asked, in the tone they asked. Don't
   add pressure, streaks or escalation they didn't want, and don't water down a firm request.
2. **Speak behaviour, build mechanism.** Talk to the user in moments and sentences ("after 25 minutes of a
   session, if you're drifting, it asks…"). Keep states, levels and expressions to yourself unless asked.
3. **Look before you write.** The live Proki is the source of truth. Read it with the tools; never guess a
   name, a unit or a parameter.
4. **Quiet by default.** Every interruption costs attention. Guard against bad moments, cap repetition, and
   give the user an easy "Later".
5. **Changes are live.** A write takes effect at once in the running app. Say what will change before the
   first write, change only what was asked, and read it back afterwards.

## Setup (every time)

1. **Load the Proki tools.** They are deferred MCP tools named `mcp__proki__*`. Load the ones the route
   needs in one `ToolSearch` call, e.g. `select:mcp__proki__reference,mcp__proki__get_program,mcp__proki__program_specs,mcp__proki__evaluate,mcp__proki__apply_changes`.
   If no `proki` server is connected, say Proki must be running with its MCP server on, and stop.
2. **Read the live reference once per session**: `reference`. Its answer is large (~160 KB of JSON). When it
   is saved to a file, query it with `jq` rather than reading it whole:
   ```bash
   jq -r '.inputs[]    | "\(.name)\t\(.desc)"'            FILE   # what Proki observes
   jq -r '.signals[]   | "\(.name)\t\(.type)\t\(.desc)"'  FILE   # ready-made measures
   jq -r '.variables[] | select(.scope=="global") | "\(.name)\t\(.desc)"' FILE
   jq -c '.actions[]'                                     FILE   # what a program can do, with params
   jq -r '.functions[] | "\(.call)\t\(.about)"'           FILE   # what expressions can call
   jq -r '.programs[]  | "\(.name)\t\(.on)\t\(.desc)"'    FILE   # what already runs
   ```
   No `jq` (`command -v jq` is empty)? Use Python's standard library instead, e.g.
   `python3 -c 'import json,sys; [print(p["name"], p["on"], p["desc"], sep="\t") for p in json.load(open(sys.argv[1]))["programs"]]' FILE`.
3. **Route** the request with the table below and load its playbook.

## Routing

| The user wants to…                                                         | Route    | Playbook                                         |
| -------------------------------------------------------------------------- | -------- | ------------------------------------------------ |
| make something new: "remind me…", "ask me…", "when I…, do…"                 | create   | [references/create.md](references/create.md)     |
| change one: timing, wording, how often, when it's quiet, what answers do   | edit     | [references/edit.md](references/edit.md)         |
| pause, switch off, reset to default, delete, clean up                      | edit     | [references/edit.md](references/edit.md#lifecycle) |
| know why one fired, didn't fire, or keeps firing                           | diagnose | [references/explain.md](references/explain.md#diagnose) |
| understand how something works: a program, a rule, "what is focus?"        | explain  | [references/explain.md](references/explain.md)   |
| judge something fuzzy: focus, wellbeing, "a good day", patterns over days  | + design | [references/evidence.md](references/evidence.md) |

Supporting references, loaded when a playbook says so:

| Reference                                          | What it holds                                                          |
| -------------------------------------------------- | ---------------------------------------------------------------------- |
| [references/vocabulary.md](references/vocabulary.md) | everyday phrases → Proki conditions, measures and actions             |
| [references/patterns.md](references/patterns.md)     | ready recipes as `apply_changes` batches: check-in, cooldown, snooze… |
| [references/mechanics.md](references/mechanics.md)   | exactly how the engine runs: cycles, states, branches, rules, scopes  |
| [references/tools.md](references/tools.md)           | every Proki MCP tool: when to use it, its arguments, its traps        |
| [references/evidence.md](references/evidence.md)     | turning a fuzzy goal into fair evidence; cold starts                  |

Two routes can apply at once ("why does it nag me, and make it stop during calls" = diagnose, then edit).
Do them in that order.

## The tools at a glance

| Need                                   | Tool                                        | Writes? |
| -------------------------------------- | ------------------------------------------- | ------- |
| what exists, live values, actions      | `reference`                                 | no      |
| one program, its states, live values   | `get_program`                               | no      |
| one program's specs, as edited, with `at` | `program_specs`                          | no      |
| an expression's value now              | `evaluate`                                  | no      |
| try an expression or action on sample data | `playground`                            | no      |
| make or change a program               | `apply_changes` (one batch, all or nothing) | **yes** |
| on / off                               | `switch_program`                            | **yes** |
| set a variable right now               | `set_value`                                 | **yes** |
| back to Proki's shipped version        | `reset_program`                             | **yes** |
| a poke's or question's pictures/sounds | `get_picks`, `set_picks`, `get_media`        | yes     |
| tasks and groups                       | `read_records`, `add_record`, …             | yes     |
| LLM / jev setup, for `ask_llm`/`ask_jev` | `get_settings`, `test_connection`          | no      |

Prefer `apply_changes` over the single `add_*`/`update_*`/`remove_*` tools: one batch builds a whole
program, and if any part is wrong nothing is kept. Details and traps: [references/tools.md](references/tools.md).

## Critical rules

These hold on every route.

**Reading**
- **Never invent a name.** Every input, signal, variable, function and action you use must appear in
  `reference`, or be one you add in the same batch. Proki has no `stddev`, `median`, `hour()`, `today()`
  or `now()`: check `functions`.
- **Units are minutes.** `time` is minutes since 1970, `daytime` minutes since midnight (17:30 → `1050`),
  `today` the start of today (a day ends at 04:00), `weekday` 0 Monday … 6 Sunday. A state's `every` is
  minutes or `"6s"`/`"5min"`/`"1h"`. Only an ask's `timeout` is in **seconds**.
- **Test every expression before it goes in a batch.** `evaluate` works out one *now*; an error, or a type
  you didn't expect, means it isn't what you think. `evaluate` gives `null` for a window (`ts_*`, `delay`):
  try the window's shape in `playground` on its sample signals `a` and `b`, and once it's a signal,
  `evaluate` the signal's name.

**Building**
- **A window lives in a signal.** `ts_mean`, `ts_sum`, `ts_min`, `delay`, `every`… are allowed in signals,
  rules and branch conditions, never in an action's `expr`. Make a signal and use its name.
- **Unknown is not false.** A condition that reads an unknown value doesn't pass; a rule with an unknown side
  doesn't fire. An unanswered question leaves its result unknown: always route that case (`answer is None`).
- **Every ask gets guards**: `not asking` (no question on top of another) and, unless it's about a session,
  `not session.active`. Every repeated nudge gets a cooldown kept in a variable.
- **Keep what must survive in a global variable**, prefixed with the program's name and an underscore
  (`stretch_next_at`) and brought by it (`"program": "stretch"`), so removing the program removes it too.
  Never use the program's name as a dotted prefix (`stretch.next_at` in program `stretch`): the builder
  reads it as reaching into the program, and refuses it. Program and state variables start over.
- **A text `value` is an expression.** A variable starting as text needs inner quotes (`"''"`, `"'calm'"`);
  `"calm"` would read a name called `calm`.
- **Branch order matters**: first match wins. Specific and safety branches first, the bare fallback
  (`"when": []`) last, and only where leaving is safe.
- **A soft rule redraws its chance on every check.** At `every: "6s"`, a 25% chance fires within half a
  minute. Use softness only where a check is rare or a near-miss should sometimes count; use hard rules
  for "only if".

**Writing**
- **Confirm before the first write** with the behaviour card (see [create.md](references/create.md#3-show-the-behaviour-card)).
  A small edit the user spelled out exactly needs no extra confirmation: say what you're changing and do it.
- **Change only what was asked.** Never reset, remove, switch off or rewrite another program, or change
  the global `cycle`, as a side effect. `remove_unused` and `reset_program` touch more than they look like they do.
- **Read it back** with `get_program` after every write, and tell the user what's checked and what only
  time will show.

## How to talk to the user

- Ask at most **two or three questions**, each about behaviour, each with a suggested answer, all at once:
  *"Should it stay quiet during a focus session? (I'd say yes.)"* Never ask about states, levels,
  softness or scopes.
- Decide everything else with the defaults in [create.md](references/create.md#defaults) and say what you
  assumed in one line.
- Explain a program as a story: *"Every weekday from 9, once you've been at the computer 50 minutes
  without a break, it suggests standing up. 'Later' asks again in 15 minutes; it never asks during a call."*
- When something can't be observed (Proki can't see your phone, your mood, or a meeting in another room),
  say so plainly and offer the nearest thing it *can* see, or a question to the user instead.

## Finishing a change

End every create or edit with:

```text
Done: <program title> — <one-line behaviour>.
Checked: built and read back; <conditions true/false right now>; <expressions evaluated>.
Not yet seen: <what only real time will show, e.g. "the 17:00 ask fires tomorrow">.
To undo: <switch it off / the change back, in a sentence>.
```

## Source

Engine code, for questions the references don't settle: `proki/core/programs.py` (states and branches),
`proki/core/rules.py` (rule voting), `proki/core/actions/` (what each action does), `proki/model/specs.py`
(every field of every kind), `proki/tools/programs.py` (the MCP tools), and the shipped programs in
`proki/programs/config/*.json`, which are good working examples. Outside Proki's own repository, read
them at <https://github.com/Combi2k2/proki>.
