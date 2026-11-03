# Recipes

Working shapes for the automations people ask for most. Each one is a whole `apply_changes` batch, or the
part that differs from one. The three full batches were checked against Proki's builder. Copy the shape,
rename everything after the new program (`<program>_<what>`), change the words and numbers to the user's,
then `evaluate` each condition and expression before sending.

| Recipe                                        | For wishes like                                           |
| --------------------------------------------- | --------------------------------------------------------- |
| [1. Once a day, at a time](#1-once-a-day-at-a-time)        | "ask me at 5 if I logged my hours", "a morning check-in"   |
| [2. Watch, then nudge](#2-watch-then-nudge)                | "tell me if I've been on YouTube 20 minutes"               |
| [3. Once per focus session](#3-once-per-focus-session)     | "when I start a session, ask what it's for"                |
| [4. Every N minutes while…](#4-every-n-minutes-while)      | "remind me to stand up every hour I'm at the desk"         |
| [5. One question, several answers](#5-one-question-several-answers) | "ask how I feel: good, tired, stressed"           |
| [6. Snooze that gets firmer](#6-snooze-that-gets-firmer)   | "keep reminding me until I do it, sooner each time"        |
| [7. Hand off to Proki](#7-hand-off-to-proki)               | "start a session when…", "begin my shutdown at 18:00"     |
| [8. A soft, occasional nudge](#8-a-soft-occasional-nudge)  | "now and then", "if it seems like I'm…"                    |

Shared rules for all of them:
- The program's `idle` state is made for you when the program is added (it checks once a minute). Change it
  with `update state` (as recipe 2 does); don't add it again.
- An asking state usually has `every: 0` and a bare `"when": []` branch back to `idle`: ask, record, return.
  A state with **no** branches goes back to `idle` by itself.
- The answer goes into a **state** variable called `answer` (`integer` with options, `string` without).
- Every "ask" branch carries `not asking`; most carry `not session.active` and `active`.

## 1. Once a day, at a time

*"On workdays at 17:00, ask whether I've logged my hours. If I say later, ask again in half an hour."*

```text
idle ──(workday, ≥17:00, not done today, not snoozed, here, free)──► asking ──► idle
asking: ask "Done / Later"; Done → done today; Later or no answer → snooze 30 min
```

```json
[
  {"op": "add", "kind": "program",  "data": {"name": "wrapup", "title": "Hours logged?", "desc": "Asks on workdays at 17:00 whether you logged your hours", "icon": "clock", "tags": ["evening", "work"]}},
  {"op": "add", "kind": "variable", "data": {"name": "wrapup_done_day", "program": "wrapup", "type": "number", "value": 0, "desc": "the day you last said it's done"}},
  {"op": "add", "kind": "variable", "data": {"name": "wrapup_next_at",  "program": "wrapup", "type": "time",   "value": 0, "desc": "not asked again before this"}},
  {"op": "add", "kind": "state",    "data": {"program": "wrapup", "name": "asking", "every": 0, "desc": "asks, then goes back to waiting"}},
  {"op": "add", "kind": "variable", "data": {"name": "answer", "scope": "state", "program": "wrapup", "state": "asking", "type": "integer", "desc": "0 done, 1 later, none: no answer"}},
  {"op": "add", "kind": "branch",   "data": {"program": "wrapup", "state": "idle", "goto": "asking",
    "when": ["weekday < 5", "daytime >= 1020", "wrapup_done_day < today", "time >= wrapup_next_at", "active", "not asking", "not session.active"],
    "desc": "a workday after 17:00, not done yet, and you're free"}},
  {"op": "add", "kind": "action",   "data": {"program": "wrapup", "state": "asking", "name": "logged", "kind": "ask_usr",
    "params": {"title": "Hours logged?", "context": "Before you finish: have you logged today's hours?", "options": ["Done", "Later"], "result": "answer", "default": 0}}},
  {"op": "add", "kind": "action",   "data": {"program": "wrapup", "state": "asking", "name": "mark_done", "kind": "set",
    "params": {"name": "wrapup_done_day", "expr": "today", "when": "answer == 0"}}},
  {"op": "add", "kind": "action",   "data": {"program": "wrapup", "state": "asking", "name": "snooze", "kind": "set",
    "params": {"name": "wrapup_next_at", "expr": "time + 30", "when": "answer is None or answer == 1"}}},
  {"op": "add", "kind": "branch",   "data": {"program": "wrapup", "state": "asking", "goto": "idle", "when": []}}
]
```

Why it's shaped so:
- `wrapup_done_day < today` makes it once a day; `today` turns over at 04:00, so a late night still counts
  as the same day.
- `"Later"` is a real button. Index 1 = Later; **no answer** (`None`) is treated the same, so a missed
  question comes back instead of disappearing.
- If the user wants only one ask a day, Done or not, set `wrapup_done_day` without the `when`.

## 2. Watch, then nudge

*"If videos, social media or news have held me for 20 minutes, give me a word. Not more than once an hour."*

```text
idle (every 6 s) ──(20 min on them, an hour since the last word, free)──► poking ──► cooling ──(left them)──► idle
```

```json
[
  {"op": "add", "kind": "program",  "data": {"name": "drift", "title": "Drift check", "desc": "A word when videos, social media or news have held you for 20 minutes", "icon": "tv", "tags": ["focus"]}},
  {"op": "add", "kind": "signal",   "data": {"name": "drift_on_leisure", "program": "drift", "expr": "label in ('Videos', 'Social media', 'News')", "type": "boolean", "desc": "videos, social media or news in focus"}},
  {"op": "add", "kind": "signal",   "data": {"name": "drift_held", "program": "drift", "expr": "ts_min(drift_on_leisure, 20)", "desc": "on them for the last 20 minutes"}},
  {"op": "add", "kind": "variable", "data": {"name": "drift_next_at", "program": "drift", "type": "time", "value": 0, "desc": "no word before this"}},
  {"op": "update", "kind": "state", "data": {"program": "drift", "name": "idle", "changes": {"every": "6s", "desc": "watching"}}},
  {"op": "add", "kind": "state",    "data": {"program": "drift", "name": "poking", "every": 0}},
  {"op": "add", "kind": "state",    "data": {"program": "drift", "name": "cooling", "every": "6s", "desc": "until you leave them"}},
  {"op": "add", "kind": "branch",   "data": {"program": "drift", "state": "idle", "goto": "poking", "when": ["drift_held", "time >= drift_next_at", "not asking"]}},
  {"op": "add", "kind": "action",   "data": {"program": "drift", "state": "poking", "name": "word", "kind": "poke",
    "params": {"title": "Still here?", "context": "Twenty minutes in. Back to what you meant to do?"}}},
  {"op": "add", "kind": "action",   "data": {"program": "drift", "state": "poking", "name": "cooldown", "kind": "set", "params": {"name": "drift_next_at", "expr": "time + 60"}}},
  {"op": "add", "kind": "branch",   "data": {"program": "drift", "state": "poking", "goto": "cooling", "when": []}},
  {"op": "add", "kind": "branch",   "data": {"program": "drift", "state": "cooling", "goto": "idle", "when": ["not drift_on_leisure"]}}
]
```

Why it's shaped so:
- **The window lives in a signal** (`drift_held`), so the branch only reads a name.
- **Two brakes**: the cooldown (`drift_next_at`) caps it at once an hour, and `cooling` waits until the user
  leaves before it can count 20 minutes again. Drop `cooling` (poking → idle) if they want a word every hour
  they stay.
- `every: "6s"` on `idle` makes it notice within seconds. For anything measured in tens of minutes,
  `"1min"` is enough and lighter.

## 3. Once per focus session

*"When I start a focus session, ask what it's for."*

The session's start time (`session.started`) names the session, so one global remembers which session it
asked in.

```json
[
  {"op": "add", "kind": "program",  "data": {"name": "intent", "title": "Session intent", "desc": "Asks once per focus session what it's for", "tags": ["focus", "session"]}},
  {"op": "add", "kind": "variable", "data": {"name": "intent_asked_for", "program": "intent", "type": "number", "value": 0, "desc": "the session it last asked in, by when it started"}},
  {"op": "add", "kind": "variable", "data": {"name": "intent_said", "program": "intent", "type": "string", "value": "''", "desc": "what you said this session is for"}},
  {"op": "add", "kind": "state",    "data": {"program": "intent", "name": "asking", "every": 0}},
  {"op": "add", "kind": "variable", "data": {"name": "answer", "scope": "state", "program": "intent", "state": "asking", "type": "string"}},
  {"op": "add", "kind": "branch",   "data": {"program": "intent", "state": "idle", "goto": "asking",
    "when": ["session.active", "session.minutes >= 1", "intent_asked_for != session.started", "not asking"]}},
  {"op": "add", "kind": "action",   "data": {"program": "intent", "state": "asking", "name": "remember_session", "kind": "set", "params": {"name": "intent_asked_for", "expr": "session.started"}}},
  {"op": "add", "kind": "action",   "data": {"program": "intent", "state": "asking", "name": "what_for", "kind": "ask_usr",
    "params": {"title": "This session", "context": "What's this session for?", "result": "answer"}}},
  {"op": "add", "kind": "action",   "data": {"program": "intent", "state": "asking", "name": "keep", "kind": "set", "params": {"name": "intent_said", "expr": "answer", "when": "answer is not None"}}}
]
```

Why it's shaped so:
- It marks the session **before** asking, so an ignored question isn't asked again in that session.
- No options: the user types; the answer is a `string`. A text variable starts at `"''"` (a quoted empty text).
- `asking` has no branches, so it goes back to `idle` by itself.
- Proki already ships a task picker for sessions (`task_picker`): check `reference.programs` before adding
  a near-duplicate, and offer to adjust that one instead.

## 4. Every N minutes while…

*"While I'm at the desk, remind me to stand up every 50 minutes."*

Recipe 1's shape with a different gate and a different snooze:

```json
{"op": "add", "kind": "signal", "data": {"name": "stretch_sitting", "program": "stretch", "expr": "ts_min(active, 50)", "desc": "at the computer all of the last 50 minutes"}}
```
```json
"when": ["stretch_sitting", "time >= stretch_next_at", "not asking", "not session.active", "label != 'Video calls'"]
```
- Done → `stretch_next_at = time + 50`; Later or no answer → `time + 10`.
- A real break (3+ minutes away) resets `stretch_sitting` by itself, so they aren't asked right after one.
- "every hour, sitting or not" → drop the signal and use `active` alone.

## 5. One question, several answers

*"Around 15:00, ask how I'm doing: good, tired or stressed. Tired: suggest a walk. Stressed: open my tasks."*

```json
"params": {"title": "How's it going?", "context": "Quick check: how are you doing?", "options": ["Good", "Tired", "Stressed"], "result": "answer"}
```
Branches out of `asking`, **in this order** (specific first, the else last):

```json
{"goto": "walk",  "when": ["answer == 1"]},
{"goto": "tasks", "when": ["answer == 2"]},
{"goto": "idle",  "when": []}
```
- `walk`: a `poke` ("A ten-minute walk resets more than coffee."), no branches → back to idle.
- `tasks`: `{"open": {"path": "'tasks'"}}`, no branches.
- "Good" (0) and no answer both fall to the else. Mark the day done in `asking` before the ask (as recipe 3
  does) so it asks once a day either way.
- To keep the answers for later (a mood log), `append` them to a global list, or ask whether they'd like
  them kept at all.

## 6. Snooze that gets firmer

*"Remind me to call home. Each time I put it off, come back sooner."*

The user-made `call_family` program does this (read it with `get_program`). Its parts:

| Part              | Value                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------- |
| remembered        | `family.last_call` (time), `family.put_offs` (integer), `family.next_prompt` (time)    |
| on "I called"     | `last_call = time`, `put_offs = 0`, `next_prompt = time + 10080` (a week)               |
| on "Later"        | `add put_offs 1`; `next_prompt = time + max(30, 240 / (put_offs + 1) / (1 + (time - last_call) / 10080))` |
| the words         | they count up: `{"format": "{days:.0f} days since your last call…", "values": {"days": "(time - family.last_call) / 1440"}}` |

Always keep a **floor** (`max(30, …)`) so it never asks every minute, and reset the count on success.
Escalation is pressure: build it only when the user asked to be pushed. Its namespace (`family`) differs
from its program's name (`call_family`), which is why its dotted names are allowed.

## 7. Hand off to Proki

Programs share globals. Set one of these from an action and the program that owns it does the rest:

```json
{"set": {"name": "session.requested",      "expr": true}}   // start a focus session
{"set": {"name": "session.stop_requested", "expr": true}}   // stop it
{"set": {"name": "shutdown_requested",     "expr": true}}   // begin the end-of-day ritual
```

Pattern: ask first ("Start a session?" with `["Start", "Not now"]`), then a `starting` state that sets the
flag. Shipped `suggest` is the model: read it with `program_specs`.

## 8. A soft, occasional nudge

*"Now and then, if it seems I'm in the flow, offer a session."*

Shipped `suggest` uses soft rules: `focus_5m` above `focused_above` with `softness: 0.1`, `focus_rise`
above 0.15 with `softness: 0.05`, all on the same level so most of them must agree, under hard gates on
higher levels (no session, the day isn't shut down, not suggested in about 45 minutes).

Remember the chance is drawn again at every check. Keep soft rules **behind** a hard gate that limits how
often the check can pass (a cooldown), or on a state that checks rarely (`every: "15min"`), or "now and
then" becomes "within a minute".
