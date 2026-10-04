# proki components

Every part of proki is a small module with one job, explicit inputs and
outputs, its parameters in the config, and its own tests. To improve one part,
change that module (and its parameters) without touching the others.

## Data flow

```
ActivityWatch ─► collector ─► timeline ─► categories.prepare ─┬─► focus.* ─► tray status
                    │                                          └─► analyzer + rules ─► policy ─► nudges
                    └─► current() ─► classifier ─► popup ─► store
```

## Components

| Module | Job | Input → output | Tuned by (config) | Tests |
|---|---|---|---|---|
| `legacy/core/collector.py` | Read ActivityWatch | HTTP → raw `Segment`s; `current()` → what's in focus now | `[activitywatch]` | via command runs |
| `legacy/core/timeline.py` | Build one ordered timeline | windows + away periods + tabs → `Segment`s; `merge()` joins identical neighbours | — | `test_timeline.py` |
| `legacy/core/categories.py` | Categorize + hide untracked names | `Segment`s → categorized, masked `Segment`s | `[[category]]`, `[[track]]` | `test_timeline.py` |
| `legacy/core/classifier.py` | Decide when to ask about an app/site | what's in focus now → `Question` (track / classify / confirm) | `[classification]`, `[jev] min_confidence` | `test_classifier.py` |
| `legacy/core/jev.py` (client: `services/jev.py`, any jev-style API: `JEV_URL`, `JEV_KEY`) | Suggest a category | app name or domain → (category, confidence) | `[jev]` | `test_timeline.py` (mocked) |
| `legacy/core/store.py` | Persist answers | categories, tracking choices, nudges, goal groups + task backlog, state values, sessions, plans ↔ SQLite | — | `test_core.py`, others |
| `legacy/focus/window.py` | Slice one window | `Segment`s, end, τ → stretches + switches (no scoring) | — | `test_focus.py` |
| `legacy/focus/depth.py` | How deep | window → [0, 1] | `shallow_weight` | `test_focus.py` |
| `legacy/focus/stability.py` | Stayed in a small working set? | window → fit × hit rate | `capacity` | `test_focus.py` |
| `legacy/focus/continuity.py` | Stayed on each item long enough? | window → [0, 1] | `dwell_scale_seconds` | `test_focus.py` |
| `legacy/focus/moment.py` | Score one moment | `Segment`s, t, τ → `Moment` (all components + intensity) | `horizons_minutes` | `test_focus.py` |
| `legacy/focus/period.py` | Summarize a period | `Segment`s, start, end → `Period` | `deep_threshold` | `test_focus.py` |
| `legacy/core/sampling.py` | When to ask "how focused are you? (1–5)" | now, away → due or not (random times in working hours, min gap) | `[sampling]` | `test_calibration.py` |
| `legacy/core/calibration.py` | Score vs. your ratings | ratings + segments → rank correlation per component; one-at-a-time parameter sweep | — | `test_calibration.py` |
| `legacy/metrics/ledger.py` | One saved entry per minute: focus intensity + main activity | segments → `MinuteEntry` per finished minute | — | `test_scoreboard.py` |
| `legacy/metrics/day.py` | A day's summary: deep minutes, streaks, time per activity, goal progress | minute entries → `DayScore` | `deep_threshold`, `[scoreboard]` | `test_scoreboard.py` |
| `legacy/metrics/keeper.py` | Score only new minutes (fill in the day at start); today's score | now → saved minutes; `DayScore` | `[scoreboard] day_starts`, `daily_goal_minutes` | `test_scoreboard.py` |
| `legacy/core/session.py` | Focus session behaviour: pokes while focus is low (build-up), "done?" then pokes (free), wrap-up reminders (50 min+), alarm when away | time, low focus?, away since → one `Action` | `[session]` | `test_session.py` |
| `legacy/rules/focus.py` `LowAndNotRising` | "Low focus" in sessions: 2-min score below 0.35 and not rising (up > 0.05 vs. 30 s ago = recovering) | score, time → low? | `low_focus_below` | `test_session.py` |
| `legacy/core/schedule.py` | Today's deep-work block (evening plan, else the default rhythm); when the warm-up / start reminders are due | day, plan → `Block`; now → `Reminder` | `[rhythm]` | `test_rhythm.py` |
| `legacy/metrics/history.py` | Deep minutes per session; the chain of kept days | minute entries, outcomes → numbers | `kept_deep_minutes` | `test_rhythm.py` |
| `legacy/core/rhythm.py` | Glue: today's block, today's sessions, chain length from stored data | store → blocks, sessions, chain | `[rhythm]` | `test_rhythm.py` |
| `legacy/core/backlog.py` | The task backlog's logic: atomic or not (vague / over 50 min), estimate mismatch, workable tasks (steps before their parent), urgency (work left ÷ time to deadline), group choice (urgency × priority), next task | tasks, groups, now → answers | `SESSION_MINUTES`, `MISMATCH_RATIO`, `PRIORITY_WEIGHT` | `test_backlog.py` |
| `legacy/metrics/quota.py` | Daily deep-work quota: +1 h today past 80%; base +1 h after 3 days in a row past 80%; 4–10 h | deep minutes → quota | `[scoreboard] quota_*` | `test_backlog.py` |
| `legacy/core/jev.py` `assess_task`, `suggest_group` | Deep or shallow, size, specific or vague; which existing goal group a task belongs to | task text → `Assessment` / group name | — | `test_backlog.py` |
| `legacy/core/ai.py` | The AI helper (Google Gemini, 3.5 Flash → 3.5 Flash Lite when busy): suggested steps when breaking a task down, a name for a new goal group; never adds tasks itself; time limit, model fallback, pause after failures | prompts → suggestions | `[ai]` | `test_ai.py` |
| `legacy/flows/tasks.py` | Task window, new/edit form, break-down dialog, evening "anything new?", one group's tasks per session | — | — | manual |
| `legacy/flows/rhythm.py` | The block reminder and the timing of the evening prompt | — | `planning_time` | manual |
| `legacy/core/bedtime.py` | Evening wind-down: phase (day / wind-down / hard stop), pokes every 5 min while active, one "10 more minutes" per night, alarm from the hard stop while active | now, active? → `Action` | `[bedtime]` | `test_bedtime.py` |
| `legacy/flows/bedtime.py` | Shows the wind-down popups, rings/silences its own alarm, locks the screen; logs last activity at night and first in the morning | — | — | manual |
| `legacy/core/morning.py` | Morning start: greet on the first activity, routine timer (time + clamp(20%, 5, 20) min), alarm when not back, then suggest the first session | now, active? → `Action` | — | `test_morning.py` |
| `legacy/flows/morning.py` | Shows today's work and the routine question, rings its own alarm, suggests the session; once per day | — | — | manual |
| `legacy/core/routines.py` | Absences (away or laptop asleep, ≥ 5 min) → sometimes "what did you do?" (chance by duration); the taxonomy; openjev sure enough (≥ 0.7) → take its activity, else its best 3 guesses; overnight = sleep | active? over time → `Absence`s; openjev guesses → activity / options | `CONFIDENT`, `UNSURE_OPTIONS` | `test_routines.py` |
| `legacy/metrics/consistency.py` | Consistency of start times: usual start = median of each day's first session (last 14 days, ≥ 3 needed); days on time = first session within ±30 min, among the last 5 | first starts per day → `Consistency` | `ConsistencyParams` | `test_consistency.py` |
| `legacy/core/offline.py` | Offline work in a session: away on a task marked offline = the work (no away alarm or auto-end), credited as deep minutes; away past estimate + 30 min → only the estimate counts, then normal away rules | current task, away since, now → `OfflineStep` | `OFFLINE_GRACE`, `OFFLINE_LIKELY` in `backlog.py` | `test_offline.py` |
| `legacy/flows/routines.py` | Stores every absence, asks about some: the user types what they did, openjev classifies it (in the background); unsure → "which one was it?" with openjev's guesses, "Something else", "Don't ask me this" | — | — | manual |
| `legacy/core/capture.py` | Outside sessions: when to ask "anything worth noting?" (shallow 15 s per visit, distraction 5 min per stretch); `Source` (tab url or app window); `FollowUps`: a task's tab/window not visited for 15 min → "finished?" | segment, category, in session? → `Source` / task id | `CaptureParams` | `test_capture.py` |
| `legacy/flows/capture.py` | The note popup (typed), openjev "is it a to-do?" → task form prefilled and linked to its source; "finished?" with closing the tab/window | — | — | manual |
| `legacy/core/shutdown.py` | The end of the workday: shift ending = time weight (S-curve around the shutdown time) × low focus | now, 10-min focus → 0..1 | `[shutdown]`, `ShutdownParams` | `test_shutdown.py` |
| `legacy/core/offtime.py` | The usual off time (peak of the starts of 3+ h absences); near it?; wrap-ups often missed? | absence starts → time | `OffTimeParams` | `test_shutdown.py` |
| `legacy/flows/shutdown.py` | Offers the ritual (shift ending, session ended near the off time, the wrap-up alarm), offers the alarm when often missed; runs the steps one at a time; "done today" stops capture | — | — | manual |
| `legacy/core/weekly.py` | The weekly review: when it's due (last workday, or after a missed one) and its text | week's deep minutes, goal groups, chain, consistency → text | — | `test_weekly.py` |
| `legacy/core/kinds.py` | What a site/app is (26 kinds in 5 groups + "something else"), each with a description for openjev and a default category | kind → label, default category | the list itself | `test_classifier.py` |
| `legacy/core/experiment.py` | The 30-day test: days, due?, verdict (two noes → quit), slips (10 s per visit, `TimeOnIt`) | segment, key → slip? | `DAYS`, `SLIP_AFTER` | `test_experiment.py` |
| `legacy/flows/experiment.py` | Choosing the service, slip reminders (Close it), the day-30 questions, the tray line | — | — | manual |
| `legacy/core/grand.py` | The grand gesture's session rules (long, breaks allowed) | base params, hours → `SessionParams` | `GrandParams` | `test_experiment.py` |
| `legacy/flows/grand.py` | The one thing, the length, "what did you get done?" | — | — | manual |
| `legacy/core/interpret.py` | What kinds mean for the timeline: watching (streaming, calls) is not away (≤ 3 h); tools (search, AI assistant) take the category of the work before | segments + kind → segments | `WATCH_KINDS`, `TOOL_KINDS`, `WATCH_LIMIT`, `TOOL_CONTEXT` | `test_interpret.py` |
| `legacy/core/sprint.py`, `legacy/flows/sprint.py` | Roosevelt sprint: the next task's estimate as the deadline, countdown, time's up (no task → add one) | now → left / due | `SprintParams` | `test_experiment.py` |
| `legacy/core/hub.py` | Hub-and-spoke: contact kinds during a session → reminder once per visit | segment, kind, in session → remind? | `CONTACT_KINDS` | `test_experiment.py` |
| `legacy/core/association.py` | Which windows serve which goal: (goal of the active task or "open", window) minutes → weighted lift; `Contributes` rule | segments, sessions → window → goals | `AssociationParams` | `test_association.py` |
| `legacy/core/craftsman.py`, `legacy/flows/craftsman.py` | Craftsman approach: per site/app per week, serving a goal (learned association, notes → tasks) or not; `WorthAsking` rule (2 h unserved, not deep); the weekly question; the 30-day test after a "no" | segments, contributions, notes → `SiteWeek`s | `WorthAsking` | `test_craftsman.py` |
| `legacy/core/timeline.py` `attach_inputs` | Input actions per minute per segment, from aw-watcher-input (presses / 2 + clicks) | segments, input events → segments | — | `test_inputs.py` |
| `legacy/focus/depth.py` `mode` | Creating vs. consuming: depth weight × (0.8 … 1) by input rate (soft threshold at 10/min) | input rate → factor | `consuming`, `creating_at`, `creating_softness` in `FocusParams` | `test_inputs.py` |
| `legacy/rules/base.py` | The rule abstraction: quantity vs. soft threshold (threshold, softness, direction, range, steps) → chance → sampled decision; `AllOf`, `Cadence` | context → chance / fire? | per rule | `test_rule.py` |
| `legacy/rules/pipeline.py` | Decision pipelines: numbered levels of rules that vote (majority or a set number); `Signal` = a rule on one named signal | signals → act? | per pipeline | `test_pipeline.py` |
| `legacy/rules/suggest_session.py` | Pipeline: focus building up outside a session → "start a session?" | signals → act? | in the file | `test_pipeline.py` |
| `legacy/rules/*.py` | One rule per file: `budget` (shallow share), `shutdown` (time × low focus), `focus` (low focus in sessions, not rising), `absence` (ask "what did you do?"; `StillThere`: openjev's veto), `reminder` (routine reminders), `capture` (time on shallow / distraction), `walk` (suggest a thinking walk) | per rule | params next to the feature (`BudgetParams`, `ShutdownParams`, …) | per feature |
| `legacy/core/budget.py` | Shallow-work budget: shallow share of active time; soft threshold, prompt sampled with a chance rising with the overshoot | minutes by activity → share; share → prompt? | `[shallow]`, `BudgetParams` | `test_budget.py` |
| `legacy/core/meditation.py` | Productive meditation: when to suggest a thinking walk; the walk as an offline task | session deep minutes → suggest?; problem, minutes → `Task` | `MeditationParams` | `test_meditation.py` |
| `legacy/flows/meditation.py` | The walk popups: suggestion, problem, length, "what did you figure out?" (a note) | — | — | manual |
| `legacy/core/reminders.py` | Routine reminders: usual times per activity (peaks, 3+ days), done today?, sampled chance = share of days already started by now | labelled absences → `Slot`s; now → slot to remind | `ReminderParams` | `test_reminders.py` |
| `legacy/flows/reminders.py` | The reminder popup (Going now / Later / Skip today), outside sessions | — | — | manual |
| `legacy/core/analyzer.py`, `legacy/rules/` | Notice patterns outside sessions (currently none active: parked until scheduled deep-work blocks) | `Segment`s → `Finding`s | per rule | `test_core.py` |
| `legacy/core/policy.py` | Allow an interruption? | `Finding`, now, away → yes/no | `[nudges]` | `test_core.py` |
| `services/activitywatch/server.py` | Run ActivityWatch's server + watchers instead of its own tray app; restart crashed ones; stop them on quit; take over leftovers from a crashed run | module commands → running processes | `[activitywatch] manage`, `modules` | `test_activitywatch.py` |
| `services/activitywatch/client.py` | What the watchers recorded: events per bucket type, the value holding at a moment (gaps held up to 15 s) | REST API → `Recording` | `[activitywatch] host`, `port` | `test_ops.py` |
| `legacy/ui/` | Tray (scoreboard + block/chain/session/task lines, `board.py`), task window / form / break-down dialog (`task_board.py`, `task_form.py`, `breakdown.py`), background calls (`background.py`), scope icon with progress ring (`icon.py`), popup, inbox, looping alarm sound (`sound.py`, Qt audio) | — | `[session] alarm_sound`, `alarm_volume` | `test_scoreboard.py` (text), manual |
| `platforms/` | Per OS: start at login, where ActivityWatch is installed, lock the screen | — | — | manual |
| `assets/sounds/` | Built-in sounds, with `CREDITS.md` (source and license) | — | — | — |
| `legacy/app.py` | Wire it all into the tray app: 2 s poll + 15 s analysis; menu actions | — | `[analysis]` | manual |
| `legacy/cli.py` | Entry point: `proki` starts the tray app | — | — | — |
| `legacy/commands/` | Developer tools, one module per subcommand; `data.py` loads segments for all | — | — | via runs |

## Focus intensity

For a window of length τ ending at time t (`legacy/focus/moment.py`):

```
intensity = depth × fit × hit rate × continuity           each in [0, 1]
```

| Component | Formula | Parameter (default) |
|---|---|---|
| depth | Σ weight(category) × time / Σ time, neutral time left out; deep 1, shallow w, distraction 0, unclassified 0 | `shallow_weight` (0.3) |
| fit | min(1, capacity / exp(entropy of time per item)) | `capacity` (5) |
| hit rate | (hits + 1) / (switches + 1); a hit is a switch back to an item used within τ, never into a distraction | τ = window size |
| continuity | 1 − exp(−mean dwell / d₀), mean dwell = active time / (switches + 1) | `dwell_scale_seconds` (20) |

Undefined when less than 25% of the window is active, or all of it is neutral.
Measured at τ = 2, 10, 30 min (`horizons_minutes`); the middle one is the main score.

A **period** (`legacy/focus/period.py`) samples the main score every minute and
reports mean intensity, deep minutes (score ≥ `deep_threshold`, 0.6), the
longest deep streak, switches into distraction per hour, and the share of time active.

**Calibrating:** proki asks for a 1–5 focus rating a few times a day (and on
demand from the tray). `legacy/core/calibration.py` reports how well each component
agrees with those ratings, and from 20 ratings on, which parameter values agree
best (`proki calibrate` for now; a tray entry once enough ratings exist).

Public-data check: `benchmarks/swell_kw.py`, results in `docs/benchmarks.md`
(interruptions lower the score for 20 of 23 people; fit and hit rate untested there).
