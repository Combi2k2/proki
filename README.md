# proki: procrastination killer

proki runs quietly in the background, watches how you work (only in the apps you
choose), and nudges you at good moments: when your focus slips, when a session has run
long, when it's time to wind down.

Everything stays on your machine, except what you let jev or an LLM see (an app's name
and a window title).

## Requirements

- [ActivityWatch](https://activitywatch.net): it records window activity, and proki reads
  it through its local API. With `[activitywatch] manage = true`, proki starts its
  background programs itself. Add its browser extension for websites, and
  aw-watcher-input for key and mouse activity.
- [NATS server](https://nats.io) (`brew install nats-server`): the message bus between the
  engine and the UI. The launcher starts it.
- Python 3.11+ with [uv](https://docs.astral.sh/uv/), and Node.js for the UI.

## Usage

```bash
uv sync                                  # the engine's dependencies
(cd ui && npm install && npm run build)  # the UI
uv run launch.py                         # start it all: NATS, ActivityWatch, the engine, the UI, kept running
uv run proki                             # the engine alone, for what's already running
uv run proki-backfill --days 14          # the metrics' past, from what ActivityWatch recorded
uv run pytest                            # the tests
```

The app can be opened by itself too (`ui/app/target/release/bundle/macos/proki.app`): it finds
the engine where the engine is, on its own.

On Windows, [`scripts/windows/proki.bat`](scripts/windows/proki.bat) installs and starts
proki, but it was written for the app before the UI was rewritten: it doesn't install
NATS or build the UI yet.

## What you see

- **The tray**: your focus over the last 5 minutes, a running session's minutes next to
  the icon, and the menu: open proki, a new note, start or stop a focus session, Tasks,
  Ideas, Metrics, Programs, quit.
- **The popup**: proki's questions and messages, one at a time. A message with an alarm
  rings while it's on the screen, and stops as you close it.
- **The main window**:
  - **Today**: your focus now, the last 24 hours (deep, shallow, active minutes) and your
    next task
  - **Tasks** and **Ideas**: your tasks in goal groups, and the thoughts you kept
  - **Metrics**: the history of any persisted signal, switched on and off
  - **Programs**: the config's programs, edited and run without restarting, with what
    they can use (inputs, signals, variables, rules, actions) and their values now

## What it does

Programs run side by side, each a state machine. Most are written in the config (JSON,
`proki/programs/config/`), the rest in code (`proki/programs/code/`).

| Program | What it does |
|---|---|
| `focus_session` | a session you start (tray, or a suggestion) and stop: a poke when focus slips, "is this session done?" after 25 minutes, time to wrap up after 50, a ringing poke when you're away 5 minutes, the end after 10 |
| `suggest` | focus building up outside a session: start one? |
| `budget` | shallow work over 30% of the day: a session? |
| `hub` | email and chat during a session: a reminder |
| `morning` | the first activity: today's work, the routine timer, a question at its end |
| `evening`, `bedtime` | "anything new?" at 21:30, and pokes from 22:00, a ringing poke and a question to lock the screen from 00:00 |
| `day` | the day's deadline, moved on at its end |
| `classify` (code) | an app proki hasn't seen: track it? A window without a label: jev's or the LLM's guess to confirm, or yours |
| `task_planner` | a todo talked through into a group's tasks: changes suggested on its card |
| `task_reminder` | a task due soon, or stuck, now and then outside a session: and what's in the way, once put off again and again |
| `task_picker` | a session without a task: what you're on, jev's group and task for it for you to confirm, or a todo for the planner |
| `capture` | "anything worth noting?" on shallow work or a distraction stretch, handed to the planner |
| `shutdown` | the end of the workday: what's still open (tasks, through the planner), the week, then tomorrow |

Only tracked apps are recorded by name. When you use an untracked app, proki asks whether
to track it, and how it counts (deep, shallow, distraction, neutral). "Don't track"
keeps only a hash of its name. Browsers are tracked per website.

## Settings

Set in the app, under Settings → Services: the LLM a program's asks go to, and jev. Each is a
provider (OpenAI, Anthropic, Google, OpenRouter, or a custom one at your URL), its key and a
model: try the connection, fetch the models there, pick one and save. It's asked from then on.
The key is kept in your computer's keychain, the rest in `config.toml` in proki's config folder
(`~/Library/Application Support/proki/` on macOS).

Everything else runs on this machine as the launcher starts it: ActivityWatch on port 5600, the
message bus on 4222, and the tools on 9144.

Your signals, rules and programs are kept in
proki.db, made from the defaults the first time, changed in the Programs window or by an
AI agent through the same tools (MCP, on 127.0.0.1, port 9144, with the token in
`tools-token` next to config.toml). Each can go back to its default.

## Layout

```
launch.py         starts NATS, ActivityWatch, the engine and the UI, and keeps them running
proki/
  __main__.py     the engine (`proki`, `python -m proki`): your programs, served on the bus and as tools
  settings.py     where proki's files are, and the services it asks
  storage.py      proki.db: the app's state, variables, persisted signals
  serve.py        what the UI asks the engine for (proki.app.*): tasks, ideas, today, metrics
  editor.py       the Programs window: your programs as files of JSON, checked, kept and run
  backfill.py     proki-backfill: the metrics' past
  core/
    signals/      Stream and the cycles, expressions, signals, variables
    primitives/   the inputs, a folder per source: aw/ ActivityWatch, sys/ the clock, proki/ labels
    ops/          time-series operators, one file each (ts_mean, every, delay, ...)
    rules.py      Rule: a soft comparison, the chance of firing now
    actions/      what a state does as it's entered: var.py, ask.py, ui.py
    programs.py   Program: state machines, each woken by the engine's cycles
  model/          your programs as specs (one per node: program, state, branch, action, variable,
                  signal, rule, input), the operations that change them, built into what runs
  engine/         Engine: the programs run cycle by cycle, each change checked aside, then kept
  channels/       asking you (popup.py), jev and an LLM, on the message bus
  programs/       every program, as shipped:
    config/       the config's files: main.json (the global scope: inputs, variables, signals,
                  rules) and one JSON file per program
    code/         the programs written in code: classify, notes, tasks/
    shipped.py    the defaults coming into your programs (kept in proki.db), and back to one
  services/       ActivityWatch, NATS, jev, LLMs, the supervisor the launcher runs them with
  platforms/      the only OS-specific code
  errors/         what proki raises on purpose
  assets/         media: the alarm's sound
ui/               the app: the tray, the popup, the main window (app/: `npm run app`), and
                  its pages (src/, React)
```

## Platform status

| | macOS | Windows | Linux X11 | Linux Wayland |
|---|---|---|---|---|
| Tested | yes | not yet | not yet | not yet |
| Window tracking | ✅ | ✅ | ✅ | needs `awatcher` |
