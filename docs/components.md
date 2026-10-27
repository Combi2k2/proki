# proki components

Every part of proki is a small module with one job, explicit inputs and outputs, its
parameters in the config, and its own tests. To improve one part, change that module (and
its parameters) without touching the others.

## Data flow

```
ActivityWatch ─► primitives ─► signals ─► rules ─┐
the clock     ─┘  (inputs)    (expressions)      ├─► programs ─► actions ─► channels ─► the UI (NATS)
                                    variables ◄──┘   (states)    (do)        (popup, jev, llm)
```

Each cycle (10 s), every input and signal moves on to the cycle's time, then the
programs whose wait is over wake up. A program's state takes its actions as it's entered,
and its `next` reads the signals, variables and rules.

## Components

| Module | Job | In → out | Parameters | Tests |
|---|---|---|---|---|
| `core/primitives/` | The inputs: what ActivityWatch recorded (app_name, app_title, tab_url, keys_pressed, mouse_*, running), the clock (daytime, time, weekday, dd, mm, yy), labels (label, depth). It drives the cycles (`Primitive.run`) | ActivityWatch events → one value per cycle | the config's `inputs` (`backfill`) | `test_signals.py`, `test_ops.py` |
| `core/signals/` | Streams, expressions, signals, variables, and their history tables (persisted ones in proki.db) | expressions → streams | the config's `signals`, `variables` | `test_signals.py`, `test_variables.py` |
| `core/ops/` | Operators: over time (`ts_sum`, `ts_mean`, `ts_max`, `ts_min`, `ts_count`, `ts_rank`, `ts_corr`, `delay`, `every`), each cycle (`min`, `max`, `clip`, `str`), and over a list (`argmin`, `argmax`, `sort`, `len`, `zip`), each saying how it's called | streams → a stream | in each expression | `test_ops.py` |
| `core/rules.py` | A soft comparison of two expressions: the chance of firing now. Rules vote by level | values → chance → fire? | the config's `rules` (`softness`, `level`) | `test_rules.py` |
| `core/actions/` | What a state does as it's entered: `set` / `add` / `sub` (var.py), `ask_usr` / `ask_jev` / `ask_llm` (ask.py), `poke` (ringing with `alarm`) / `lock` / `open` (ui.py) | an action's entry → done | each action's params | `test_programs.py`, `test_engine.py` |
| `core/programs.py` | State machines side by side, each woken by the engine's cycles | states, branches → the next state | each state's `every`, `next` | `test_programs.py` |
| `model/` | Your programs as specs, one dataclass per node (`specs.py`, each with its JSON Schema), `Scope` (names), the operations that change them (`Model`: add, update, remove, each checked by building it aside), `Builder` (specs → what runs), `Defaults` (the shipped JSON ↔ specs) | specs → streams, rules, programs | the specs | `test_model.py`, `test_programs.py` |
| `programs/shipped.py`, `storage.SpecDB` | Your programs kept in proki.db, a table per kind of node; the defaults coming in, one you never changed following proki's, and one back to its default | the shipped files → your specs | — | `test_shipped.py`, `test_editor.py` |
| `engine/` | Runs the config cycle by cycle, checks a config aside and reloads it | now → a cycle | the config's `cycle` | `test_engine.py`, `test_editor.py` |
| `channels/` | Asking on the bus: you (popup.py), jev and an LLM (one worker each), and the UI's one-way messages | a question → its answer | `[jev]`, `[llm]` | `test_engine.py`, `test_llm.py` |
| `programs/code/classify/` | Track an app or not, and label each window (similar titles, jev, the LLM, or you) | what's in focus → questions, labels | `[classification]`, `[[track]]` | `test_rituals.py` |
| `core/records/` | A kind of record's table the config reads and writes as variables (the table, one record), fields of yours (an expr, jev, the LLM, a value set), their asks, and the variables code keeps | `records_<kind>` in proki.db → variables | the fields of yours | `test_table.py`, `test_tasks.py` |
| `programs/code/work.py` | The board (groups of tasks), the task records (`work.task`, `work.tasks`), the group records (`work.group`, `work.groups`), the plan (`work.plan`, one at a time: a group as it'd be and the changes to its tasks) and the weight's fields | the board → variables | — | `test_tasks.py`, `test_plan.py` |
| `programs/config/` | main.json (the global scope), and the config programs: pomodoro, suggest, budget, hub, day, morning, evening, bedtime, capture, shutdown, notes, classify, task_tracker, task_reminder, task_picker, task_planner (a todo into a group's tasks) | — | in each file | `test_focus_session.py`, `test_rituals.py` |
| `serve.py`, `editor.py` | What the UI asks for: tasks, ideas, today, metrics; the program editor | requests (proki.app.*) → answers | — | `test_serve.py`, `test_editor.py` |
| `backfill.py` | The persisted signals' past, replayed from ActivityWatch | days → signal_history | `--days` | manual |
| `services/` | ActivityWatch's API, the NATS bus, jev, LLMs, the supervisor that runs NATS, ActivityWatch and the UI | — | `[activitywatch]`, `[nats]` | `test_bus.py`, `test_supervisor.py` |
| `platforms/` | Per OS: where things are installed, lock the screen | — | — | manual |
| `ui/` | The app (app/, its pages in src/): tray, popup, main window (Today, Tasks, Ideas, Metrics, Programs) | messages on the bus → what you see | — | manual |

## Focus

The focus score is a signal of the config (`programs/main.json`), like any other:

    focus = deep_share * steady * engaged          each in [0, 1]

| Part | Expression | Means |
|---|---|---|
| `deep_share` | `ts_mean(depth, 2)` | how deep the windows in focus were, the last 2 minutes |
| `steady` | `1 / (1 + switches / 4)`, `switches = ts_count(app_name, 2)` | few app switches |
| `engaged` | `ts_mean(active, 2)` | input (keys, mouse) the last 2 minutes |

`focus_2m`, `focus_5m` are its averages, `focus_rise` how it moved the last 2 minutes.

Public-data check of an earlier score: `docs/benchmarks.md`.
