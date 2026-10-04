# Actions in proki today, and how to generalize them

A survey of every prompt, alarm and side effect (2026-10-01): ~60 call sites in 15
modules. The goal: one action model that the `.proki` definition file can describe.

## 1. What triggers an action

| Shape | Examples | Trigger today |
|---|---|---|
| **Rule-triggered** | shallow budget, suggest a session, hub-and-spoke, routine reminder, deep-work block, "anything worth noting?" (shallow 15 s / distraction 5 min), 30-day slip, craftsman question, thinking-walk suggestion, shutdown offer, wrap-up alarm offer, evening "anything new?", focus rating (sampling) | rules on signals, often a pipeline; checked every tick or on a cadence |
| **Flow events** | session: poke / "done?" / wrap-up / away alarm; sprint "time's up"; offline "welcome back"; morning: greet / "finished?" / alarm / "ready?"; bedtime: wind-down / hard stop; grand gesture end; shutdown ritual steps | a state machine in Python reaches a state and emits an event |
| **Follow-ups** | classification (kind → group → kind, "counts as…"); routine ("were you away?" → "what did you do?" → "which one?"); capture (note → openjev "is it a to-do?" → "add it?" → task form); 30-day test (Q1 → Q2 → verdict); craftsman ("no" → "try 30 days without it?"); walk / grand gesture (text → length → … → "what did you get done?"); task hand-over (start / offline / other / done) | the answer to one action |
| **User-started** | tray: sprint, walk, grand gesture, 30-day test, rate focus, new task | a tray item |

## 2. What an action shows

| Kind | Used by | Notes |
|---|---|---|
| **choice** (buttons) | almost everything | 2–10 options, 4 per row |
| **text** (a field + Save / Skip) | "what did you do?", notes, wrap-up, problem for a walk, outcome of a walk / grand gesture | one-line text |
| **alarm** (looping sound) | session away / slipping focus, sprint time's up, morning deadline, bedtime hard stop, wrap-up alarm | always *together with* a choice; stops on an answer or when a condition clears (focus back, user back) |
| notify (system notification) | only the parked nudge rules | |
| tray line (passive) | scoreboard, budget, consistency, 30-day test, sprint countdown | not an action: a display of signals |
| window | task form, task board, breakdown dialog | opened by an effect |

## 3. What an answer does (effects)

A small fixed vocabulary, all in Python today:

- **sessions**: start session, stop session, start sprint / walk / grand gesture
- **tasks**: open the task form (prefilled), mark done, set fields (offline, source), link a note
- **record**: note, verdict, absence activity, focus rating, category / kind, review answer, state
  ("shutdown done", "alarm at 17:25")
- **timing**: snooze / ask later (a cooldown for this action), "5 more minutes", "10 more minutes"
- **system**: lock the screen, close the tab / window
- **chain**: ask another action (follow-ups)
- **background**: ask openjev / Gemini, then continue with the result (classify a note, "still
  there?", to-do?)

## 4. Policies every action follows (scattered in the code today)

- **one popup at a time**; a new action waits (or is dropped) while one is open
- **priority**: session messages replace whatever is showing
- **frequency**: once per visit / stretch / day / week / ever; or every N minutes (cadence)
- **staleness**: a waiting question is dropped after a while (e.g. "what did you do?" after 30 min)
- **scope**: outside sessions; before the shutdown; workdays — these are just rules
- **message templates** filled with signals ("{share:%} of your time", "{key}", "day {n}")

## 5. A generalized action

```
ACTION <name>(
    kind     = ASK | NOTIFY,                 # ASK with options = [] → a text field
    message  = "... {signal} ...",
    options  = ["label" -> effect or ACTION, ...],
    trigger  = (rule, rule, ...)              # or an event from a flow: EVENT session.slipping
    alarm    = none | until_answered | while(rule),
    every    = 30min,                         # how often the trigger is checked (per-check chance)
    once     = visit | stretch | day | week | ever,
    priority = normal | session,
    stale    = 30min,
)
```

- **trigger** groups its rules by their `level`; levels vote in order (each level's quorum is
  part of its `RULE_LEVEL`, e.g. strict = all, relax = majority).
- **options** map to built-in effects (section 3) or to another `ACTION` (follow-ups), so a
  dialog is a small graph of actions.
- **flows stay in Python** at first (sessions, morning, bedtime, shutdown ritual, sprint):
  they emit named events; the `.proki` file decides the message, options and alarm for each.
- **background steps** (openjev) become an effect that runs and then picks the next action by
  its result, e.g. `classify_todo(text) -> (yes: offer_task, no: none)`.

## 6. The same three actions in the definition file

```
RULE_LEVEL strict = 1 (all)
RULE_LEVEL relax  = 2 (majority)

SIGNAL shallow_share := minutes(shallow, today) / minutes(active, today)

RULE outside_session(in_session < 1, level = strict)
RULE before_shutdown(shutdown_done < 1, level = strict)
RULE over_budget(shallow_share > 0.30, softness = 0.05, level = relax)

ACTION budget(kind = ASK,
    message = "Shallow work is at {shallow_share:%} of your time today (limit 30%).",
    options = ["Start a focus session" -> start_session, "Not now"],
    trigger = (outside_session, before_shutdown, over_budget), every = 30min)

RULE on_contact(on_contact_kind > 0, level = strict)
RULE contact_15s(seconds_on_item > 15, level = relax)

ACTION hub(kind = ASK,
    message = "{kind_label} can wait until the session is over.",
    options = ["Back to work", "Stop session" -> stop_session],
    trigger = (in_session_rule, on_contact, contact_15s), once = visit)

ACTION note(kind = ASK, options = [],                     # a text field
    message = "You're on {key}. Anything worth noting, or anything to do?",
    on_answer = save_note -> classify_todo -> (yes: offer_task),
    trigger = (outside_session, on_shallow, shallow_15s), once = visit)
```
