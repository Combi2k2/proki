# How Proki runs a program

The exact behaviour of the engine. Use it to build correctly, to diagnose, and to answer "how does it
work?" questions. Each claim here is checked against `proki/core/`. When the live `reference` differs,
the live one wins.

```text
inputs ──► signals ──► rules ─┐
  │            │              ├──► branch of a state ──► next state ──► its actions (poke, ask, set…)
  └──► variables ◄────────────┼──────────────────────────────────────────┘ (actions set variables)
                              └ conditions (plain expressions)
```

## Contents

1. [The cycle](#the-cycle)
2. [Building blocks](#building-blocks)
3. [A state's life](#a-states-life)
4. [Branches: the way out](#branches-the-way-out)
5. [Rules and voting](#rules-and-voting)
6. [Variables: scope and lifetime](#variables-scope-and-lifetime)
7. [Expressions](#expressions)
8. [Actions](#actions)
9. [Programs talking to each other](#programs-talking-to-each-other)

## The cycle

Proki looks at the computer once a **cycle** (a few seconds; read or set it with `cycle`, which affects
everything). Each cycle, inputs are sampled, signals move on, and every program that's **on** and whose
wait is over takes its next step. A program never sees time finer than the cycle: `every: "1s"` with a
5-second cycle checks every 5 seconds.

Inputs (live list in `reference.inputs`) are what Proki can observe: `app_name`, `app_title`, `tab_url`,
`label` (what the app or page *is*: "Chat", "Email", "Videos"…), `depth` (0 shallow … 1 deep),
`keys_pressed`, `mouse_*`, `running` (false while Proki is off or the computer asleep), and the clock:
`time`, `daytime`, `weekday`, `dd`, `mm`, `yy`. It can't see anything off the computer.

## Building blocks

| Kind       | What it is                                                     | User-level meaning                    |
| ---------- | -------------------------------------------------------------- | ------------------------------------- |
| input      | a primitive Proki samples each cycle                           | "what Proki can see"                  |
| signal     | a named expression over inputs, variables, signals             | "a measure", "how focused you are"    |
| variable   | a value that actions set, and that persists or resets by scope | "what it remembers"                   |
| rule       | a comparison giving a chance of firing, voting by level        | "a condition, maybe a soft one"       |
| program    | a state machine; starts in `initial` (default `idle`)          | "an automation"                       |
| state      | a step of a program: actions on entry, then waits for a way out | "what it's doing or waiting for"     |
| branch     | one ordered way out of a state, to another of its states       | "when this happens, go there"         |
| action     | something a state does as it's entered, in order               | "what it does"                        |

A program, its states, branches and actions are one unit. Variables, signals and rules have a **scope**:
`global` (seen everywhere), `program` (only inside the program), or `state` (only inside one state). A
global one can say which program brings it (`"program": "x"`); it's then removed with that program.

## A state's life

```text
enter state ─► run its actions, in order (an ask waits for its answer or its timeout)
            ─► wait `every` (unless every is 0)
            ─► try its branches, in order ── one passes ─► leave: its state variables reset ─► enter the next
                     ▲                    └─ none passes ─► wait `every`, try again
                     └─────────────────────────────────────────┘
```

- **Actions run once, on entry.** Staying in a state does not repeat them. To repeat them, take a branch
  back into the same state (`"goto"` its own name): that re-enters it and runs its actions again (shipped
  Bedtime's `past_midnight` does this to ring until answered).
- **An ask blocks the state** until it's answered, put off, or times out (`timeout` seconds, 120 by default).
  Only then is the first branch tried, so branches can read the answer.
- **`every`** is how often the ways out are tried: `0` (straight through, a pass-through step), `"6s"`
  (responsive, the shipped norm for watching), `1` (a minute, the default), `"2h"` (rare checks).
- **No branches at all**: the state goes back to the program's initial state. An initial state with no
  branches just waits.
- **At most once a cycle**: a program can pass through several `every: 0` states in one cycle, but
  re-entering one it already entered this cycle waits for the next cycle. This stops endless loops.
- **Off and on**: switched off, a program stops where it is. Switched on (and at every app start), it starts
  over in its initial state, its program and state variables reset.

## Branches: the way out

```json
{"program": "stretch", "state": "idle", "goto": "asking", "when": ["stretch_due", "not asking"], "desc": "due, and free"}
```

- `when` is a list. Each item is either **a rule's name** or **an expression** (a condition).
- It passes when **every condition is true** *and* its **rules vote yes** (next section).
- A condition that's unknown (`None`) is **not true**. So `answer == 0` fails both when the answer is 1 and
  when nobody answered.
- Branches are tried **in order**; the first that passes is taken, the rest aren't tried. An empty `when`
  always passes: it is the *else*, and belongs last.
- A branch is identified by its place, `at` (0 = first), among its state's branches.

## Rules and voting

```json
{"name": "stretch_long_sitting", "lhs": "active_streak", "cmp": "ge", "rhs": 50, "softness": 0, "level": 2}
```

- A rule compares two numeric expressions: `gt >`, `ge >=`, `lt <`, `le <=`, `eq ==`, `ne !=`. True/false
  count as 1/0. Text or unknown on either side: it doesn't fire.
- **Softness 0** is a plain yes/no. **Softness s** turns it into a chance that changes smoothly around the
  threshold:

  | how far past the line | `gt`/`ge` chance | `eq` chance |
  | --------------------- | ---------------- | ----------- |
  | 2s below / 2s apart   | 12%              | 14%         |
  | s below / s apart     | 27%              | 61%         |
  | on the line           | 50%              | 100%        |
  | s above               | 73%              | —           |
  | 2s above              | 88%              | —           |

  (`lt`/`le` mirror `gt`/`ge`; `ne` is 1 − `eq`.)
- **The chance is drawn again on every check.** A rule at 27%, checked every 6 seconds, fires within about
  20 seconds. Softness makes *when* it fires uncertain, not *whether*. It suits rare checks, or rules
  combined with a hard gate that only opens briefly.
- **Levels**: a branch's rules are grouped by `level`, highest first. A level passes when **more than half**
  of its rules fire; the first level that fails ends the vote (no). So:
  - to require *all* of several rules, give each its **own level**;
  - to require *most of* several, put them on the **same level** (2 of 3 pass; 1 of 2 doesn't).
- Rules are usually global and named with the program as prefix (`budget_workday`), so they read well in
  `when` lists.

## Variables: scope and lifetime

| Scope     | Lives                                              | Use for                                         |
| --------- | -------------------------------------------------- | ----------------------------------------------- |
| `global`  | kept across restarts (saved)                       | next-time-due, last-done, counters, preferences |
| `program` | from when the program starts (each app start, each switch on) | progress within one run                |
| `state`   | from entering the state to leaving it              | the answer to that state's question             |

- `value` is where it starts: a constant, `null`, or a **string, read as an expression** worked out on its
  first cycle (`"time - 10000"`: "long ago"). So a text start needs inner quotes: `"''"` (empty),
  `"'calm'"`; `""` is refused as an empty expression. A saved global value **overrides** the declared
  start; the start applies only the first time, or after its type changes.
- `type`: `number`, `integer`, `boolean`, `string`, `array`, `object`, `time` (minutes since 1970), `any`,
  or a JSON Schema. A value of another type is refused when set.
- A global name may have one dot (`family.last_call`), but **the part before the dot must not be a
  program's name**: inside a program, `stretch.next_at` reads as reaching into program `stretch`'s scope,
  which is refused ("not allowed in an expression"). Prefer the shipped style: `stretch_next_at`.
- Names are found inside out: a state's own, then its program's, then global. Nothing reaches into
  another program's or state's scope; share through globals.
- A **global list of objects** (`type: {"type": "array", "items": {"type": "object", …}}`) becomes a
  table of records, each with an `id`: it starts empty (no `value`), grows with `append`, shrinks with
  `remove`, and its items' fields can be set (`xs[0].done`).
- Some globals are kept by code and read-only (`asking`, `track`, `work`). `reference.variables[].from` says
  `code` for those.

## Expressions

Python-like: `+ - * / // %`, comparisons, `and or not`, `in`, `is None`, `x if c else y`, lists, fields
(`task.estimate`), items (`xs[0]`, `xs[-1]`), columns of a list (`tasks.deadline`). Text in single quotes:
`app_name == 'Slack'`.

Functions (live list in `reference.functions`):

| Over time (signals, rules, conditions only)         | Now (anywhere)                                       |
| --------------------------------------------------- | ---------------------------------------------------- |
| `ts_mean(x, w)` average of known values, last w min | `min`, `max`, `clip(x, lo, hi)`                      |
| `ts_sum(x, w)` total; on true/false: minutes true   | `len`, `index`, `sort`, `where`, `zip`, `choices`    |
| `ts_min`/`ts_max(x, w)` lowest/highest              | `argmin`, `argmax`                                   |
| `ts_count(x, w)` changes; on true/false: times it became true | `str(x)` to put a number in text           |
| `ts_rank(x, w)`, `ts_corr(x, y, w)`                 |                                                      |
| `delay(x, d)` value d min ago; `every(x, p, how)` one value per p min |                                    |

A window needs history, so `evaluate` gives `null` for one written inline: name it as a signal and evaluate
the name, or try its shape in `playground`. Windows can be fractions of a minute: `ts_min(on_contact, 0.25)` means "for the last 15 seconds".
`ts_min(cond, w)` reads as "**has been true for w minutes**"; `ts_max(cond, w)` as "**was true at some point
in the last w minutes**".

## Actions

Live list and examples: `jq -c '.actions[]' FILE`. Params marked `?` are optional.

| Action    | Does                                                           | Key params                                             |
| --------- | -------------------------------------------------------------- | ------------------------------------------------------ |
| `poke`    | a popup message with a picture and a sound; nothing to answer   | `context`, `title?`                                    |
| `ask_usr` | a question; the answer into `result` (option index, or text)    | `context`, `title`, `result`, `options?`, `default?`, `timeout?` (s, 120), `immediate?` |
| `ask_llm` | asks the LLM; answer in the result variable's type             | `context`, `result`, `timeout?` (s, 10)                |
| `ask_jev` | asks jev several yes/no, choice or score questions at once     | `context`, `questions`, `timeout?` (s, 10)             |
| `set` / `add` / `sub` | a variable, or a field or item of one                | `name`, `expr`, `when?`                                |
| `append` / `remove` | an item into / out of a list                           | `name`, `expr` / `id`, `when?`                         |
| `open`    | opens a page of the app: `today`, `tasks`, `notes`, `apps`, `metrics`, `programs`, `media` (+ `/id`) | `path` (an expression: `"'today'"`) |
| `lock`    | locks the screen                                               | —                                                      |

- **`context`** is a text, or `{"format": "{h:.1f} h so far", "values": {"h": "shallow_today / 60"}}`.
  Format specs are Python's.
- **`ask_usr` options**: a list of texts, or an expression giving them. An option called `"OK"` or `"Later"`
  becomes that button. Without options the user types the answer (a text). `default` is the option
  pre-selected. `immediate: true` removes "Later" (to be answered now).
- **No answer** (put off, away, timed out) leaves the result **unknown**. Plan a branch for `answer is None`.
- **`when`** on set/add/sub/append/remove: only if it's true (`"when": "answer == 1"`).
- An action's expressions are worked out as it runs, so they **can't hold a window** (`ts_*`, `delay`).
- Each action gets an id `program.state.name`, kept across edits; its pictures and sounds are chosen in the
  media library by that id (`get_picks`, `set_picks`), not in the program.
- An action that fails is reported in the log and the state's other actions still run.
- `ask_llm` and `ask_jev` need a provider set up: check `get_settings` / `test_connection` first.

## Programs talking to each other

Programs don't call each other; they share global variables. The shipped ones use these handshakes:

| Variable                  | Set it to `true` to…                         | Read it to know…                    |
| ------------------------- | -------------------------------------------- | ----------------------------------- |
| `session.requested`       | start a focus session                        | —                                   |
| `session.stop_requested`  | stop the focus session                       | —                                   |
| `shutdown_requested`      | start the end-of-day ritual                  | —                                   |
| `session.active`          | —                                            | a focus session is running          |
| `session.minutes`         | —                                            | minutes into the session            |
| `shutdown_done`           | —                                            | today's work is shut down           |
| `asking`                  | — (kept by code)                             | a question is waiting for the user  |

Check the live names in `reference` before relying on one.
