# Signals as time series (model, 2026-10-01)

A signal is not a variable but a **time series**. Rules read a signal's current value,
or a reduction of it.

## Implemented (2026-10-01)

- `core/signals/base.py`: time moves in cycles of `Stream.cycle` (the config's `"cycle"`, in
  seconds, 10 by default); a `Stream` has one value per cycle (None = unknown). Windows
  are time, never a number of cycles, so changing the cycle changes how often values are
  taken, not what they mean. A `Signal` is a name and an `expr` (both required), e.g.
  `Signal("keys_5m", "ts_mean(keys, 5)")`. Signals and primitives are kept in
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
  `ts_rank` gives where the current value stands in its window (0 to 1). Slow streams:
  `every(x, p, how)` resamples x to one value per p minutes over clock-aligned spans (its
  `period`; `fresh` when a span closes), and windows and `delay` take only fresh values, so
  a long window over a slow stream stays small: `ts_rank(every(focus, 60), 30 * 1440)`
  keeps 720 values.
- `signals/primitive.py`: the only signals module that reads ActivityWatch (`legacy/core/collector.py`
  still does for the rest of proki, for now), and the one that drives the cycles:
  `Primitive.run(now)` fetches what was recorded since the last cycle and ticks through the
  cycles up to now. The first run replays as far back as the longest table (a day with the shipped config:
  8,640 cycles of 10 s, in about 5 s), after which
  ActivityWatch's events are let go and each primitive keeps its own day as a table. After
  a pause the cycles in between are run. Each bucket is read from where its newest event starts, so an event still
  running (a window, a tab you stay on) is never missed. A primitive's value in a cycle comes from the
  event holding at that moment; a value holds until the next event, at most 15 s past its
  event's end. Primitives: recorded (false where ActivityWatch had nothing: it or proki was
  off), app, title, url, sector (the label), depth (the label's category as a level,
  legacy/core/labels.py `DEPTH`); keys, mouse_move, mouse_click, mouse_scroll (per minute).
- The focus score is a signal like any other, in config.json: `focus = deep_share * steady *
  engaged` (each of those an expression over the primitives), then `focus_2m`, `focus_5m`,
  `focus_rise = focus - delay(focus, 2)`, `on_deep = depth == 1`, and `focus_history =
  every(focus, 5)`, kept a week (saved). The older score built on the prepared timeline
  (`legacy/focus/moment.py`) still feeds the scoreboard, but no signal.
- Sampling: a switch shorter than a cycle can be missed (a 5 s visit falls between two
  cycles).
- Not yet: presence from input (away is still the AFK watcher's, in the timeline); state as a
  signal over time (in_session is only known now); task primitives; history beyond the lookback
  (reductions per day / week still live in legacy/metrics/).

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
- **window operators** (numeric, over t, at τ = 2 / 5 / 30 min): depth, fit, hit rate,
  continuity, intensity (`legacy/focus/`); input rate (`timeline.py`, to be split into key and
  mouse intensity); rise = intensity(t) − intensity(t − lag) (`legacy/rules/focus.py`)
- **resampling**: intensity and category per minute → the ledger (the one stored series)

## 3. Reductions (series → fewer values)

- per day / week: deep minutes, streaks, shallow share, first session start, quota
- distributions over weeks: density peak (off time, routine times), empirical CDF
  (reminders), median (consistency), quantile (low-focus threshold, later), weighted lift
  (window × goal)

## Operators

map (lookup) · window(τ, f) · lag · resample · group by day / week + aggregate (sum, count,
ratio, run length, streak) · distribution (density, CDF, median, quantile, lift) · and on
top, the rule: soft threshold → chance → sample, levels voting by majority.

## The config (config.json)

The inputs, every signal that isn't a primitive (the focus score too) and the rules are
defined in JSON, not Python, and compiled by `proki/compiler.py`: `proki/assets/config.json` ships
the defaults, and the app copies it next to the config the first time (`config.json`,
yours to edit; restart proki to apply). Flows will join it later.

    {
      "inputs": [
        {"name": "app", "backfill": 1440},
        {"name": "keys", "backfill": 1440}
      ],
      "signals": [
        {"name": "engaged", "expr": "ts_mean(active, 2)"},
        {"name": "focus_history", "expr": "every(focus, 5)", "backfill": true, "window": 10080, "persist": true}
      ]
    }

Rules go in `"rules"` (`core/rules.py`). A rule isn't a signal: it keeps no history and
gives the chance of firing now, from a comparison of two expressions: `lhs`, `cmp` (gt,
ge, lt, le, eq, ne) and `rhs`. `softness` is like an LLM's
temperature: σ((lhs − rhs) / s) for gt / ge (mirrored for lt / le), a bell curve
exp(−z²/2) for eq (1 − that for ne), and 0 the comparison itself. Rules trigger
together by `level`, the highest first: each level votes by majority, and one that
doesn't approve stops the vote.

    {"name": "focus_high", "lhs": "focus_5m", "cmp": "gt", "rhs": 0.5, "softness": 0.1}

Variables go in `"variables"` (`core/signals/variable.py`): app state, a value that
actions and flows set, not read from the world. A variable is a stream (rules and
expressions read it like any other: `time - last_suggested`) and changes only by `set`,
`add` or `sub`, of one or more variables at once, each by an expression's value at the
moment: `{"set": {"deadline_eod": "deadline_eod + 1440", "daily_metric": 0}}` (`Update`:
its expressions are made up front, so their windows move on every cycle). Its starting
`value` is a constant or an expression worked out once, on its first cycle. Every
variable keeps its latest value (a row in proki.db's `variables` table: name, JSON value,
when it changed), written when it changes and restored at startup; the starting value
counts only while nothing is saved. Resetting (at the end of the day, ...) is a flow's
job, not the variable's.

    {"name": "last_suggested", "value": null}
    {"name": "deadline_eod", "value": "time - clock + 1440"}

`clock` (minutes since local midnight), `weekday` (0 Monday) and `time` (minutes since
1970, for "minutes since") are inputs too, from the cycle's time, not from ActivityWatch.

`inputs` picks the primitives (by name; an expression can only read the ones listed) and
how many minutes of itself each keeps as a table (`backfill`; none if left out). The first
run goes back as far as the longest table. Plain JSON (no comments). Each entry needs a
`name` (and a signal an `expr`); `window` is in minutes. Unknown sections or fields, an
unknown input, a missing name or expr, a name used twice, or an expression reading a
name nobody defines stop proki with a message naming it.

