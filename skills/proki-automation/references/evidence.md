# Fair evidence for fuzzy goals

Read this when a wish judges something Proki can only see indirectly: focus, distraction, overwork,
wellbeing, "a good day", or a pattern over days or weeks. Simple reminders ("at 17:00", "every hour")
don't need it, except the [cold start](#cold-start) section.

The task is to keep the user's intent while choosing evidence and a response that are fair to them.
Don't start from a threshold or a state diagram; first work out what the hoped-for experience means and
whether Proki can observe it.

## Contents

1. [The design chain](#the-design-chain)
2. [Read time-series evidence correctly](#read-time-series-evidence-correctly)
3. [Cold start](#cold-start)
4. [What the focus measures mean](#what-the-focus-measures-mean)
5. [Why Pomodoro nudges when it does](#why-pomodoro-nudges-when-it-does)
6. [Worked design: inviting a focus-program review](#worked-design-inviting-a-focus-program-review)

## The design chain

Make each link explicit before building:

```text
the principle ─► observable evidence ─► window and coverage ─► decision ─► proportionate response ─► feedback
```

1. **Clarify the principle.** What experience is hoped for, and what must be protected? Don't assume more
   activity, a higher focus score or fewer breaks is always better.
2. **Look before modelling.** `reference` and `get_program` show the live measures and behaviour. Trace a
   measure you rely on to its expression (`reference.signals[].expr`).
3. **Test whether the evidence supports the claim.** Units, sampling, window, missing data, persistence,
   coverage, confounders. A proxy is evidence *about* a construct, not the construct. A short window can't
   show a daily or weekly pattern.
4. **Choose a fair comparison.** Prefer the user's own bands (`focus_lines`) and personal baseline to
   universal thresholds. Allow for ramp-up, breaks, schedule, task type, and days with too little data.
5. **Respond in proportion.** Require sustained or repeated evidence. Use a low-pressure question, a
   cooldown and an easy "Later". Don't repeat an action just because its trigger stays true.
6. **Close the loop.** Let the user interpret the evidence and change their programs. A program meant to
   improve other programs **invites a review**; it never rewrites them silently.
7. **Grow from results.** Start with the smallest useful behaviour, check typical cases and false alarms,
   ask whether it helped, and add complexity only when new evidence changes a decision.

If the conclusion can't be drawn from what exists, explain the gap and propose the missing signal,
coverage measure, record or code support (and, with the user's agreement, `suggest` it to Proki's
developer). Don't invent functions, and don't smuggle unrelated meaning into a variable. Keep such a
design a sketch until its inputs are measurable.

## Read time-series evidence correctly

Before using a measure, know:

| Property       | Ask                                                                  |
| -------------- | -------------------------------------------------------------------- |
| meaning, units | what does the input record, and what does the signal estimate?       |
| cadence, window| how often is it sampled, how far back do its functions look?         |
| coverage       | are unknown periods skipped (`ts_mean`), counted as zero, or unknown? |
| persistence    | does history survive a restart (`persist`), and how much (`backfill`)? |
| confounders    | what else moves this proxy besides the behaviour of interest?        |

Proki's functions: arithmetic, comparisons, logic, list fields and items, and `ts_mean`, `ts_sum`,
`ts_max`, `ts_min`, `ts_count`, `ts_rank`, `ts_corr`, `delay`, `every`, plus list helpers (see
[mechanics.md](mechanics.md#expressions)). `every(x, p, how)` makes one value per clock-aligned span of
`p` minutes (`mean`, `sum`, `max`, `min`, `last`); it isn't a time-of-day classifier. There's no standard
deviation, median or percentile.

**Inactive is not missing.** `active` comes from recent input, while time runs on when the user is away.
`focus` may read zero while they're away, so a whole-day average is pulled down by time off. For claims
about work quality or the shape of a day, define the valid work periods and coverage explicitly.

## Cold start

Treat the first run as part of the behaviour, not a nuisance. Check five situations:

1. **No saved state**: what does each variable mean before any answer or data?
2. **Warm-up**: do rolling windows, `delay` or persisted series have enough known samples yet?
3. **Partial history**: enough recorded activity and valid periods for the comparison?
4. **Restart or edit**: a saved global loads instead of its declared start; a changed `type` drops it.
5. **Reset by scope**: program variables restart with the program, state variables on leaving the state.
   Is that right for this value's life?

How Proki starts values: a constant or an expression (a string `value`, worked out on the first cycle,
unknown while it's being worked out). A saved global loads instead. Program and state variables are
never saved. (Code: `core/signals/variable.py`, `model/build.py`.)

Rules:
- Use `null` for "unknown yet" only if the type and every reader handle it. Otherwise keep the type clean
  and add an explicit guard (`<program>_ready`, a count of valid days).
- Keep `0` and `false` for real observations. Don't let "no history" read as low focus, no urgency, or "no".
- Require minimum samples, elapsed time, valid days or a user calibration before a judging rule can fire.
- Make the waiting state safe while evidence is missing. Unknown conditions don't pass, so put the
  evidence-ready branch before any else, and make sure the else can't trigger an intervention.
- Keep first-use defaults apart from the user's choices and learned baselines; never overwrite a
  deliberate preference with a derived default on restart.
- For timers, choose the first run on purpose: `<program>_next_at` starting at `0` means "due now";
  `"time + 60"` means "not in the first hour".

## What the focus measures mean

From the shipped global scope (`program_specs` with `name: null`):

| Signal        | Expression (shipped)                                       | Means                                       |
| ------------- | ---------------------------------------------------------- | ------------------------------------------- |
| `active`      | `ts_max(keys_pressed + mouse_click + mouse_scroll + mouse_move, 3) > 0` | any input in the last 3 min      |
| `engaged`     | `ts_mean(active, 2)`                                       | share of the last 2 min active              |
| `deep_share`  | `ts_mean(depth, 2)`                                        | depth of the work in focus, from its label  |
| `switches`    | `ts_count(app_name, 2)`                                    | app changes in 2 min                        |
| `steady`      | `1 / (1 + switches / 4)`                                   | lower with more switching                   |
| `focus`       | `deep_share * steady * engaged`                            | a short-window composite, about 0–1         |
| `focus_2m`, `focus_5m`, `focus_rise` | smoothed and rising focus             |                                             |
| `focus_lines` | the user's band edges; `distracted_below` first, `focused_above` last | their own lines             |
| `focus_history` | `every(focus, 5)`, kept 7 days                           | 5-minute samples                            |
| `focus_hourly`, `deep_daily`, … | hourly for 30 days, daily for a year     | longer views of different measures          |

Focus is a handy proxy for deep context, steadiness and recent activity. It is **not** effort, value,
motivation, fatigue or wellbeing, and a low value doesn't say why. Look at its parts and the label
assumptions before choosing a response.

## Why Pomodoro nudges when it does

In shipped `pomodoro`, the `focusing` state tries, in order: an explicit stop, away for longer, away, the
50-minute break, a once-per-session "done?" check after 25 minutes when focus is low **and** not recovering,
then an ordinary slipping-focus nudge. `session_low_focus` compares `focus_2m` with `distracted_below`;
`session_not_recovering` compares `focus_2m_rise` with `0.05`; they sit on separate levels, so both must hold.

The ordinary nudge goes through `slipping`: one poke on entry, a minute's wait, back to `focusing`. The
25-minute check sets `asked_done` before asking, so it asks once per session. At 50 minutes it offers a
break. It uses context (an explicit session), persistence (low and not recovering), elapsed time, the
user's control, and a bounded response. It never ends a session because focus dipped.

Carry that logic, not its numbers: gate on context, require enough evidence, allow recovery, limit
repetition, let the user decide.

## Worked design: inviting a focus-program review

**Principle.** A good day may have a strong focused stretch, then lower or uneven focus that leaves room
for recovery and other work. The aim is a sustainable pattern that fits the user, not a high index all
day. If the pattern suggests their focus automations no longer fit, invite them to review those programs.

**Decide what "blocky" means.** Ask: one strong early block then a steep drop? Many short bursts? One long
plateau? Each needs different evidence; don't encode "blocky" as one invented threshold. A fair summary
likely needs:

1. focus by time-of-day bins, so a strong start isn't confused with a high score all day;
2. activity coverage per bin and a minimum number of valid days;
3. a personal baseline or an expectation the user approved;
4. a rule that tells a normal break or a thin day apart from a pattern they want to change.

The shipped `focus_history` gives 5-minute samples but no work periods, coverage, shape or baseline, and
the current functions may not express the bins and validity checks. If they can't, design and validate the
missing signals in code first. Don't send speculative expressions to `apply_changes`.

**Shape, once a validated summary exists:**

```text
idle
 └─ weekly check due AND enough valid bins/days
      ├─ no pattern that matters to the user → schedule the next check
      └─ possible mismatch AND cooldown over → asking
           ├─ "Review programs"     → open the programs view → cooldown → idle
           ├─ "Later"               → short snooze → idle
           └─ "This pattern is fine" → long dismissal → idle
```

Word it tentatively: *"Your recent days show a strong early focus stretch and less later. Does that feel
sustainable, or would you like to look at your focus programs?"* Take "it's fine" as a real answer, not a
failure. Don't change `focus_lines`, Pomodoro's timing or any other program yourself; make the review
easy. Check the design against: a strong start then an intended break, steady moderate focus, thin-data
days, and fragmented work the user does want help with. It stays quiet when evidence is thin.

This is a design example, not ready Proki JSON: confirm each measure, action and statistic in the live
`reference` before building.

## Code to read when needed

- Shipped measures and automations: `proki/programs/config/main.json`, `pomodoro.json`, `suggest.json`,
  `budget.json`, `day.json`.
- Fields of every spec: `proki/model/specs.py`. Building and type checks: `proki/model/build.py`,
  `proki/core/signals/expr.py`.
- Time functions: `proki/core/ops/`. Rules and states: `proki/core/rules.py`, `proki/core/programs.py`.
