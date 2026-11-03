# Change an automation

Tuning, rewording, quieting, extending, pausing or removing a program that exists. The rule: **find
exactly the part the complaint is about, change only that, read it back.**

```text
1 find the program ─► 2 read it ─► 3 translate the complaint ─► 4 change ─► 5 read back and report
```

## 1. Find the program

The user names it in their words ("the break thing", "that call reminder"). Match on `title`, `desc` and
`tags` in `reference.programs`. Several fit, or none: ask with the titles, one line each.

## 2. Read it

- `get_program` to see what it does and its live values (what's true now, where it is).
- `program_specs` to see the parts **as edited**, with each branch's and action's position (`at`), and
  `default` (Proki ships it: it can be reset) / `changed` (the user has edited it).
- Retell it to yourself as a behaviour card ([create.md](create.md#3-show-the-behaviour-card)). If the
  user asked "what does it do?", that card is the answer.

## 3. Translate the complaint

| The user says                                  | Usually means                                    | Change                                                       |
| ---------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------ |
| "too often", "nagging", "it keeps asking"       | the cooldown is short, or there's none           | lengthen the `…_next_at` / `time - last` gap; add one if missing |
| "it asks again right away after I say Later"    | Later/no answer isn't routed to a snooze          | set the snooze on `answer is None or answer == <Later>`      |
| "it pops up at a bad time"                      | a missing guard                                  | add the condition: `not session.active`, `label != 'Video calls'`, `not asking`, `active`, time window |
| "only on weekdays / not on Sundays"             | a day condition                                  | add `weekday < 5` / `weekday != 6` to the branch out of idle |
| "later in the day", "at 6 instead"              | the time condition                               | change the number in `daytime >= …` (h × 60)                 |
| "it's too sensitive", "it fires when I'm fine"  | the threshold, or a window too short             | raise/lower the rule's `rhs`, lengthen the window in the signal, or remove softness |
| "it never fires"                                | see [diagnose](explain.md#diagnose) first        | fix what the diagnosis finds                                 |
| "change the text", "be nicer", "in Vietnamese"  | an action's words                                | `update action`: `context`, `title`, `options` (whole `params`) |
| "add a 'Skip today' button"                     | a new option and what it does                    | add the option at the end, a `set … when answer == <its index>`; check older indices still mean the same |
| "also when …", "and then …"                     | a new branch or a new state                      | add it; mind the branch order                                |
| "make it a question / just tell me"             | poke ⇄ ask                                       | swap the action; add or remove answer handling               |
| "push me harder" / "gentler"                    | escalation                                       | add/remove the escalating snooze (patterns 6), firmer/softer words |
| "different picture / sound"                     | the action's picks                               | `get_picks` / `set_picks` with the action's `id`             |

When a complaint has two readings ("too often" = shorter cooldown, or wrong moment?), check the program
first; ask only if the program doesn't tell you.

## 4. Change

- Small and exactly specified ("make it 18:00"): say the one change and do it.
- Anything that changes behaviour beyond the words they used: show a two-line before/after card first.

  ```text
  Before: asks again 10 minutes after "Later".
  After:  asks again 30 minutes after "Later", and never during a call.
  ```
- Send it as one `apply_changes` batch, even for two changes, so they land together or not at all.

Writing updates correctly:
- Find the spec by its identifying fields ([tools.md](tools.md#finding-what-to-update-or-remove)); branches
  and actions by `program`, `state`, `at`, read **just now** from `program_specs`.
- `changes` replaces whole fields. To change one word in an action, send its whole `params` with that word
  changed. To add a condition, send the whole `when` list with it added.
- A shipped program (`default: true`) is edited the same way. The user's version then differs from
  Proki's (`changed: true`); `reset_program` brings back Proki's.
- Changing a global's `type` drops its saved value (it starts over from `value`). Say so when you do it.
- An action keeps its `id` when it changes, so its pictures and sounds stay.

## 5. Read back and report

`get_program` again: the change is there, the conditions read as expected now. Report with the closing
block in SKILL.md, including how to undo (the old value, in words).

## Lifecycle

| The user wants                       | Do                                                           | Undo                                 |
| ------------------------------------ | ------------------------------------------------------------ | ------------------------------------ |
| "pause it", "stop it for now", "turn it off" | `switch_program` `on: false`                        | `switch_program` `on: true` (starts over at idle) |
| "not today", "skip the next one"     | `set_value` the program's next-due/done-today global (e.g. `wrapup_done_day` to `today`'s value: `evaluate` `today`) | set it back |
| "ask me now" (to try it)             | `set_value` its cooldown global to `0`; its moment still has to be true | — |
| "put it back how it was" (shipped)   | `reset_program`: confirm first, the user's edits to it are lost | none: note their edits first        |
| "delete it"                          | for a user's own program: `remove_program` (takes everything it brings); confirm first, keep the `program_specs` you read so it can be re-added. For a shipped one, offer switching off instead | add back from the kept specs |
| "clean up what's unused"             | `unused` → show the list in words → remove the ones they agree to via `apply_changes` | add back |

Never switch off, reset or remove a program the user didn't name, even if it seems related or redundant.
Mention it instead.
