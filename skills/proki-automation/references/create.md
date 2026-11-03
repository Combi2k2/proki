# Create an automation

From a wish in everyday words to a program running in Proki. Seven steps; don't skip one.

```text
1 hear the wish ─► 2 fill the gaps ─► 3 behaviour card ─► 4 map to Proki ─► 5 check ─► 6 build ─► 7 read back
     (look first)      (≤3 questions)     (user says yes)     (vocabulary,      (evaluate)  (one batch)  (report)
                                                               patterns)
```

## 1. Hear the wish

Write the wish down as five parts. Most of them are in what the user said; mark what isn't.

| Part         | Question it answers                     | "Remind me to stand up every hour, but not in meetings" |
| ------------ | --------------------------------------- | ------------------------------------------------------- |
| **Moment**   | when should it happen?                  | after an hour at the computer                           |
| **Unless**   | when must it stay quiet?                | in meetings (video calls)                               |
| **Does**     | what happens: a word, a question, an act? | a reminder                                            |
| **Answers**  | if it asks, what does each answer do?   | — (unstated)                                            |
| **How often**| how often at most, and after "Later"?   | every hour                                              |

Before asking anything, **look**:
- `reference.programs`: does a shipped or user program already do this, or most of it? (Pomodoro already
  suggests breaks; `hub` already guards chat during sessions; `bedtime`, `morning`, `evening`, `shutdown`,
  `capture`, `task_reminder`…) If one does, offer to adjust it instead (go to [edit.md](edit.md)), unless
  the user clearly wants a separate one.
- [vocabulary.md](vocabulary.md): can Proki see the moment? If not, say so now and offer the nearest thing
  ([What Proki can't see](vocabulary.md#what-proki-cant-see)).
- If the wish judges something fuzzy (focus, wellbeing, "a good day", a pattern over days), also read
  [evidence.md](evidence.md) before going on.

## 2. Fill the gaps

Ask **only** what changes the behaviour and has no good default, **at most three questions, in one
message**, each with a suggested answer. Everything else: use the defaults below and say so.

Good questions (behaviour, with a default):
- "Should it only remind you, or ask so you can tick it off? (I'd ask, with 'Done' and 'Later'.)"
- "Weekdays only, or every day? (Weekdays.)"
- "If you say 'Later', when should it come back? (In 15 minutes.)"

Never ask about states, rules, levels, softness, scopes, signals, `every`, or variable types.

If the wish is already complete, skip to the card.

### Defaults

Use these unless the user said otherwise, and list the ones you used on the card.

| Decision                    | Default                                                                 |
| --------------------------- | ----------------------------------------------------------------------- |
| a word or a question        | a **question with "Done" / "Later"** when there's something to do; a **poke** for pure information |
| quiet during                | another question (`not asking`), a focus session (`not session.active`) unless it's about one, away (`active`); calls (`label != 'Video calls'`) for anything with sound |
| quiet after "Done"          | until the moment comes round again (next day, next hour)                |
| after "Later" or no answer  | ask again in 15 min (nudges), 30 min (daily check-ins)                  |
| at most                     | once an hour for nudges; once a day for check-ins                       |
| days                        | as said; "work" things on weekdays (`weekday < 5`)                      |
| "morning" / "evening"       | 9:00 / 18:00 as the start                                               |
| tone                        | warm, short, concrete; no guilt, no exclamation marks, no streak pressure |
| title / icon / tags         | 1–3 words; a Lucide icon name that fits (`clock`, `coffee`, `footprints`, `phone`, `droplet`); tags from its part of the day (`morning`, `evening`, `focus`, `health`, `work`) |
| escalation                  | **none** unless they ask to be pushed                                   |

## 3. Show the behaviour card

Before the first write, show the user what it will do, in their words, and wait for a yes (or a change).

```text
**Stand-up reminder**
- When: you've been at the computer for 50 minutes without a break.
- Unless: you're in a call or a focus session, or another question is up.
- It asks: "You've been sitting for 50 minutes. Time to stand up?" — Done / Later
- Done: quiet for the next 50 minutes.  Later or no answer: asks again in 10 minutes.
- At most: once every 10 minutes, only while you're sitting.
- Assumed: every day (say if you want weekdays only).
```

Rules for the card:
- Plain sentences. No names of variables, states or rules.
- Quote the exact text the user will see.
- List every assumption you made in one line.
- If the user said "just do it" or the request was fully specific, show the card and build in the same
  turn; say that you did.

## 4. Map it to Proki

1. Pick the recipe from [patterns.md](patterns.md) whose shape fits. Most wishes are recipe 1, 2 or 4.
2. Name everything after the program: program `stretch`, globals `stretch_next_at`, rules `stretch_due`.
   The program name is short, lowercase, `_` only, and not taken (`reference.programs`).
3. Translate each card line with [vocabulary.md](vocabulary.md):
   - **When** → conditions on the branch out of `idle` (a window → a signal first).
   - **Unless** → more conditions on the same branch.
   - **It asks / says** → an `ask_usr` or `poke` action in an asking state.
   - **Answers** → `set` actions with `when`, or branches by answer (recipe 5).
   - **At most** → a `<program>_next_at` cooldown variable, and/or a cooling state.
4. Write the whole program as **one** `apply_changes` batch, in this order: program → globals (variables,
   signals, rules) → states → state variables → branches → actions.

Conditions or rules? Use **plain conditions** (strings in `when`) by default: they're easiest to read and
check. Use a **rule** when a comparison should be soft, when "most of these" should count, or to name a
comparison several branches share.

## 5. Check before writing

- `evaluate` every condition and every action expression that has no window. Each should give a value of
  the type you expect (often `false` right now, which is fine).
- For each window, try its shape in `playground` (`ts_min(a > 0.5, 20)` on the sample focus `a`), then make
  it a signal.
- Walk the card against the branch list, out loud to yourself: *at 17:05 on a Tuesday, here, no session:
  every condition true? Answer "Later": which set runs? No answer: which?* Fix gaps now.
- Check the cold start: on the first run, do the variables' starting values make it ask at a sensible
  time, not instantly and not never? (`value: 0` for a `next_at` means "due now"; `"time + 60"` means "not
  in the first hour".) More: [evidence.md](evidence.md#cold-start).

## 6. Build

Send the batch with `apply_changes`. If it's refused, the error names one place: fix that, send the whole
batch again. Common refusals:

| Error says                                         | Fix                                                             |
| -------------------------------------------------- | --------------------------------------------------------------- |
| `unknown name 'x'`                                 | a typo, or a name that doesn't exist; check `reference`          |
| `not allowed in an expression: prog.x`             | a global whose dotted prefix is a program's name: use `prog_x`   |
| `signal expr can't be empty`                       | a text variable with `"value": ""`: use `"''"`                  |
| `… keeps a window: use a signal's name`            | `ts_*`/`delay` in an action: move it to a signal                 |
| `it comes after the else, so it's never taken`     | a branch after `"when": []`: put the else last (`at`)            |
| `… is there already`, `… is defined twice`         | the name is taken (maybe `idle`, made with the program): pick another, or `update` it |
| `a list of objects starts empty`                   | a global list of objects is a table of records: give it no `value` |
| `answer is of type …`                              | the result variable's type doesn't match: `integer` with options, `string` without |
| `has no state 'x'`                                 | a `goto` or `state` before the state was added, or misspelled   |

## 7. Read back and report

- `get_program` the new program: it's `on`, in `idle`, and each condition shows its value now. Say which
  are true now and which aren't, and so when it will first act.
- If it should act soon and the user wants to see it, offer to trigger it once with `set_value` (e.g. set
  `<program>_next_at` to `0` and wait for the moment) — never fake the moment's conditions.
- Report with the closing block in SKILL.md: *Done / Checked / Not yet seen / To undo*.
