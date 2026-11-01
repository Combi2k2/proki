# F-012 Signals and formulas

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Make it yours | `proki/core/signals/`, `proki/core/ops/`, `proki/core/primitives/`, `proki/core/rules.py`, `proki/programs/config/main.json` |

Measures written as formulas over what ActivityWatch recorded, that automations read.

## How it works
- Inputs, once a cycle (10 s): the app, title and page in focus, its label and depth, key and
  mouse counts, and the clock.
- A signal is a name and an expression in Python syntax, read with a whitelist (never `eval`).
  Windows are in minutes, whatever the cycle.
- Operators over time (`ts_mean`, `ts_sum`, `ts_count`, `delay`, `every`, ...), per value
  (`min`, `clip`, ...) and over lists (`argmin`, `sort`, `zip`, ...): one file each in `core/ops/`.
- Rules are soft comparisons: a chance of firing, voted by level.
- The focus score: `focus = deep_share * steady * engaged`, each 0 to 1, over the last 2 minutes.
- At start, the past day is replayed so windows are full from the first cycle.

## Limits
- A switch shorter than a cycle can be missed.
- Presence is from input in the last few minutes, not ActivityWatch's away watcher.
