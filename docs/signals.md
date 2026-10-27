# Signals as time series (model, 2026-10-01)

A signal is not a variable but a **time series**. Rules read a signal's current value,
or a reduction of it.

## Implemented (2026-10-01)

- `core/signals/stream.py` (with `expr.py`, the expressions, and `signal.py`): time moves in cycles of `Stream.cycle` (the config's `"cycle"`, in
  seconds, 10 by default); a `Stream` has one value per cycle (None = unknown). Windows
  are time, never a number of cycles, so changing the cycle changes how often values are
  taken, not what they mean. A `Signal` is a name and an `expr` (both required), e.g.
  `Signal("keys_5m", "ts_mean(keys_pressed, 5)")`. Signals and primitives are kept in
  `Stream.registry`; expression names are looked up there on the first cycle. Each cycle,
  `advance(t)` moves a stream on to the cycle at t (a window pushes and drops; the cached
  value goes) and `current()` gives its value, worked out when first asked.
  `Stream.tick(t)` advances every stream once, inputs first. Every stream has a `period`
  (how often it takes a new value), `backfill` (it keeps its history as a table of
  (time, value) rows, filled in when it starts), a `window` (how much time the table keeps;
  None: as far back as its inputs' tables reach) and `persist` (the table is also saved in
  proki's database, `signal_history`, so it reaches back past the startup replay). A saved
  table is taken as it is up to its last row; the cycles after it add to it. A stream added
  while proki runs is filled in from the tables the others keep, each playing its rows back
  in time order (`Stream.fill`). `Stream.now` is the current cycle's time.
  Expressions: Python syntax via `ast`, a whitelist, no `eval`.
- `core/ops/`: our own operators, one file per operator (`ts_mean.py`: `TsMean`, called
  `ts_mean` in expressions; a new file registers itself),, which know nothing of clocks: `lift` (also + − * /,
  comparisons, and / or / not), `delay`, and windows `ts_sum`, `ts_mean`, `ts_max`, `ts_min`,
  `ts_count`. Queues hold (time, value): a window over w minutes holds what came in the
  last w minutes, whatever the input's period; when a window starts, it fills its queue
  from its input's table, if the input keeps one. Time is always in minutes.
  `ts_rank` gives where the current value stands in its window (0 to 1), `ts_corr(x, y, w)`
  how closely two move together (-1 to 1). Slow streams:
  `every(x, p, how)` resamples x to one value per p minutes over clock-aligned spans (its
  `period`; `fresh` when a span closes), and windows and `delay` take only fresh values, so
  a long window over a slow stream stays small: `ts_rank(every(focus, 60), 30 * 1440)`
  keeps 720 values. Lists: `xs[i]` an item (-1: the last), `xs.name` a column (every
  item's field), and `min` / `max` / `argmin` / `argmax` / `sort` / `len` / `zip` over their
  known items: `tasks[argmin(tasks.deadline)]`, `zip(groups.name, groups.desc)`.
- `core/primitives/` (one file per primitive, a folder per source: `aw/` what ActivityWatch recorded, `sys/` the clock, `proki/` what proki works out from the window in focus (label, depth), each folder's `base.py` what its primitives share, the top `base.py` `Primitive` and the cycles' `run`): the only code that reads ActivityWatch, and the one that drives the cycles:
  `Primitive.run(now)` fetches what was recorded since the last cycle and ticks through the
  cycles up to now. The first run replays as far back as the longest table (a day with the shipped config:
  8,640 cycles of 10 s; only the streams that keep the past run them, windows and tables, the
  rest is worked out at the present cycle: a few seconds), after which
  ActivityWatch's events are let go and each primitive keeps its own day as a table. After
  a pause the cycles in between are run. Each bucket is read from where its newest event starts, so an event still
  running (a window, a tab you stay on) is never missed. A primitive's value in a cycle comes from the
  event holding at that moment; a value holds until the next event, at most 15 s past its
  event's end. Primitives: running (false where ActivityWatch had nothing: it or proki was
  off), app_name, app_title, tab_url, label, depth (the label's category as a level),
  keys_pressed, mouse_move, mouse_click, mouse_scroll (per minute), daytime, time, weekday,
  dd, mm, yy (from the cycle's time). Each says what it is (`desc`), shown as you hover it.
- The focus score is a signal like any other, in main.json: `focus = deep_share * steady *
  engaged` (each of those an expression over the primitives), then `focus_2m`, `focus_5m`,
  `focus_rise = focus - delay(focus, 2)`, `on_deep = depth == 1`, and `focus_history =
  every(focus, 5)`, kept a week (saved). Persisted signals are the metrics (the Metrics
  window), and `proki-backfill` replays their past from what ActivityWatch recorded.
- Sampling: a switch shorter than a cycle can be missed (a 5 s visit falls between two
  cycles).
- Presence is from input: `active` (any key or mouse input the last 3 minutes), not the
  AFK watcher. App state is variables (`in_session`, ...), streams like the others.
- `work` is an object: `work.tasks` and `work.groups` the records proki keeps, `work.task` and `work.group` the ones at hand; `work.plan` is the one plan at hand (a group as it'd be, its changes a table).

## Series types

- **interval series**: a value over [start, end), piecewise constant (the window in focus)
- **event series**: values at points in time (input counts every 5 s)
- **sampled series**: a regular grid (the per-minute ledger)

## 1. Primitive series (recorded)

| Series | Type | Source |
|---|---|---|
| app, window title | interval | ActivityWatch window watcher |
| tab URL, tab title | interval | browser extension |
| away / present | interval | AFK watcher |
| **key intensity** (key presses / min) | event | aw-watcher-input (`presses` / 2: down and up are both counted) |
| **mouse intensity** (clicks, movement, scrolling / min) | event | aw-watcher-input (`clicks`, `deltaX/Y`, `scrollX/Y`) |
| in session, its goal group, current task | interval | proki's state |
| time | — | the clock |

**User answers are not primitive signals.** They are the inputs of chained workflows:
an action node's answer flows along an edge to the next node. When an answer must be
remembered for later signals (labelled breaks → usual meal times; notes that became
tasks; verdicts), a workflow node **writes a record**, and the record store is a source
for reductions, like any other history.

## 2. Derived series (one value per moment)

- **lookups** (per interval): URL → domain → category, kind; tracked / masked; lock screen →
  away; watching fills away; tools take the category of the work before
- **window operators** (numeric, over t, at τ = 2 / 5 min): depth, steadiness, engagement,
  focus, key and mouse intensity, rise = focus(t) − focus(t − lag)
- **resampling**: `every(x, p)`, one value per span (hourly, daily). Persisted, these are the
  stored series (the metrics)

## 3. Reductions (series → fewer values)

- per day / week: deep minutes, streaks, shallow share, first session start, quota
- distributions over weeks: density peak (off time, routine times), empirical CDF
  (reminders), median (consistency), quantile (low-focus threshold, later), weighted lift
  (window × goal)

## Operators

map (lookup) · window(τ, f) · lag · resample · group by day / week + aggregate (sum, count,
ratio, run length, streak) · distribution (density, CDF, median, quantile, lift) · and on
top, the rule: soft threshold → chance → sample, levels voting by majority.

## The programs (main.json and the program files)

The inputs, the signals (the focus score too), the variables, the rules and the programs
are specs, one per node (`proki/model/specs.py`), kept in proki.db. `proki/programs/config/`
(main.json and a file per program, read by `proki/model/defaults.py`) ships the defaults.
You change yours through the tools (`proki/tools/`, over MCP): node by node (`add_rule`,
`update_state`, `remove_program`, ...) or a whole file of JSON at once, from the Programs
window or from an AI agent. Each change is checked by building it aside, and kept only if
it runs. A default you never changed follows proki's, and any of yours can go back to
its default. The JSON below is a file's shape.

    {
      "cycle":     10,
      "inputs":    [{"name": "app_name", "backfill": "1d"}, {"name": "keys_pressed", "backfill": "1d"}],
      "variables": [{"name": "in_session", "value": false}],
      "signals":   [{"name": "engaged", "expr": "ts_mean(active, 2)"},
                    {"name": "focus_history", "expr": "every(focus, 5)", "backfill": 10080, "persist": true}],
      "rules":     [{"name": "focus_high", "lhs": "focus_5m", "cmp": "gt", "rhs": 0.5, "softness": 0.1}]
    }

- **inputs** pick the primitives, by name, and how many minutes of itself each keeps as
  a table (`backfill`). The first run goes back as far as the longest table.
- **signals** are a name and an expression. `backfill` keeps a table, `persist` saves it
  (a metric).
- **variables** are app state, set by actions (`set`, `add`, `sub`), kept across restarts
  (proki.db's `variables`). A starting `value` is a constant or an expression worked out on
  the first cycle.
- **rules** are soft comparisons (`core/rules.py`): `lhs`, `cmp` (gt, ge, lt, le, eq, ne),
  `rhs`. `softness` is like an LLM's temperature: σ((lhs − rhs) / s) for gt / ge (mirrored
  for lt / le), a bell curve for eq. Rules fire together by `level`, the highest first:
  each level votes by majority, and one that doesn't approve stops the vote.

**Programs** (`core/programs.py`) are state machines running side by side. Each has a file,
`<name>.json` beside main.json, with the variables, signals and rules it brings:

    {"variables": [...], "signals": [...], "rules": [...],
     "program": {"initial": "idle", "variables": [...], "states": {
       "idle":   {"every": 0.1, "next": [{"goto": "asking", "when": ["focus_high", "not in_session"]}]},
       "asking": {"do": [{"ask_usr": {"context": "Start a session?", "title": "Ready?", "options": ["Start", "Not now"],
                                      "result": "answer", "default": 1}}],
                  "next": [{"goto": "starting", "when": "answer == 0"}, {"goto": "idle"}]},
       ...}}}

A state takes its actions as it's entered (`do`), waits `every` minutes (1 by default),
then tries its `next`: a state's name, or branches tried in order like if / elif / else,
each `when` a list of rules (voted together) and conditions (expressions, all true). No
branch passes: it waits `every` more and tries again. No `next`: back to `initial`.
Entering a state, even the one it's in, runs its `do` again.

Everything named can say what it's for in a line, `desc`: a program (with its `tags`), a
state, a branch, a variable, a signal, a rule. The Programs window shows them. An input's
is written in code, as its module's first line (`core/primitives/`).

Variables live in scopes: global (a file's `variables`), the program's, or a state's (an
ask's `result`, `answer`). A name is found from the inside out. A variable lives as long
as what owns it: a state's goes back to its starting value when the state is left, a
program's when the program starts over (each start, or switched on again), and a global
one is kept across restarts. Signals and rules are
global. Full names read the others' (`suggest.asking.answer`).

**Actions** (`core/actions/`): `set` / `add` / `sub` a variable, `ask` you (`usr`), jev or
an LLM (its answer later in a variable of the state, while it waits only this program
waits), `poke` a message, `lock` the screen, `open` a page by its path. A poke with `"alarm": true`
rings while it's on the screen, and stops as it's closed (a question never rings: you're
there to answer it). A context
fills in values as it's said: `{"format": "{h:.1f} h so far", "values": {"h": "shallow_today / 60"}}`.

Shipped programs: `focus_session`, `suggest`, `budget`, `hub`, `day`, `morning`, `evening`,
`bedtime`. What's in code (`proki/programs/code/`) is the records: the config reads and
writes them as variables (`work.task`, `work.group`, `note`, ...).

Plain JSON (no comments). A mistake (an unknown section or field, input, name, a name used
twice, an expression reading a name nobody defines) stops the compile with a message
naming where it is.
