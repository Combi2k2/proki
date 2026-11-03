# Explain and diagnose

Answering questions about Proki's automations: what one does, how the machinery works, and why something
did or didn't happen. Nothing here writes; a fix found while diagnosing goes through [edit.md](edit.md).

## Contents

1. [Answer at the user's level](#answer-at-the-users-level)
2. [What a program does](#what-a-program-does)
3. [How the machinery works](#how-the-machinery-works)
4. [Diagnose](#diagnose)

## Answer at the user's level

Read the question for its level and answer at that level, live facts first:

| They ask                                          | Level      | Answer with                                                         |
| ------------------------------------------------- | ---------- | ------------------------------------------------------------------- |
| "what does the bedtime one do?"                   | behaviour  | a behaviour card in plain sentences, from `get_program`             |
| "how does Proki know I'm focused?"                | concept    | what it sees and how it combines it, then what it *can't* tell      |
| "what's a rule / a state / a signal?"             | mechanism  | one sentence each, the example taken from *their* programs          |
| "why is softness 0.1 there?", "how do levels vote?" | engine   | the exact behaviour from [mechanics.md](mechanics.md), with numbers |

- Lead with the answer in one or two sentences, then detail only if it helps.
- Use **their** programs as examples (`get_program`), not made-up ones.
- Say what's live: "right now your focus reads 0.62, above your 0.6 'focused' line."
- Don't dump JSON or expressions on a behaviour-level question. Do show them on an engine-level one.
- Close with one offer, if one fits: "Want it to stay quiet during calls too?"

## What a program does

1. `get_program <name>`.
2. Walk from the initial state as a story: what it waits for (the branch out of idle, in words), what it
   does (actions, quoting the text), what each answer leads to, how it returns.
3. Add when it **acts next**: which conditions are true now (`conds[].value`), where it is now (`state`),
   when it checks next (`waking`).
4. If it's switched off (`on: false`), say so first.

```text
**Inbox guard** (on, waiting)
During a focus session, once email, chat or a call has been in front of you for 15 seconds, it says
"Email, chat and calls can wait until the session is over" with OK / Stop session. It won't say it again
until you've left them. Right now: no session, so it's quiet.
```

## How the machinery works

Plain-words version, to adapt (exact details in [mechanics.md](mechanics.md)):

- **What Proki sees**: the app and window in front, the web address in a browser, what kind of thing it is
  (its label: Chat, Videos, Code editor…), how deep that kind of work usually is, keys and mouse per
  minute, whether the computer is on, and the clock. Nothing off the computer, nothing inside messages.
- **Measures (signals)** combine those over time: "active" is any input in the last 3 minutes; "focus" is
  depth × steadiness (few app switches) × how active you've been, over a couple of minutes.
- **Memory (variables)**: what an automation needs to remember: when it last asked, what you answered, how
  many times you put it off. Some last across restarts, some only while it's at one step.
- **Automations (programs)** are a few steps (states). Each step does something as it starts (a popup, a
  question, remembering something), then waits for one of its ways out, checked in order: the first one
  whose conditions all hold is taken.
- **Conditions and rules**: a condition is a yes/no ("it's after 17:00"). A rule is a comparison that can
  be soft: near the line it's a maybe, so a nudge doesn't come at exactly the same moment every time.
- **Questions** wait for your answer. "Later", ignoring it, or walking away all count as no answer, and
  each automation decides what that means.

## Diagnose

For "why didn't it…", "why does it keep…", "it did X at a weird time". Work through in order; stop at the
first cause that explains it, and say it in one sentence.

### It didn't fire

| # | Check                                    | How                                                                  | Cause if…                                                     |
| - | ---------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------- |
| 1 | it's on                                  | `get_program` → `on`                                                  | `false`: switched off                                          |
| 2 | where it is                              | `state`, `waking`                                                    | not in the state that waits for the moment: it's stuck waiting elsewhere (a cooling state whose way back never comes true; an ask still open) |
| 3 | which condition blocks                   | the branch's `conds[].value` now                                      | a `false` one is the blocker; `null` means **unknown** (no data yet, no answer, a name nothing sets) and blocks too |
| 4 | the rules                                | `reference.rules[].chance` for the branch's rules                     | a chance of 0, or several on one level where most fail; a higher level blocking a lower one |
| 5 | the cooldown                             | `evaluate` `<program>_next_at - time`, `today` vs the done-day global | a positive number: it's waiting that many minutes; done-day equals `today`: done for the day |
| 6 | the moment, at that time                 | for a past miss, the conditions then: windows (`focus_history`, `engaged_history`), `running` | the moment wasn't true (e.g. a 2-minute break reset a "50 minutes without a break") |
| 7 | was something else up                    | `asking` at the time; another program's question                      | `not asking` held it back while another question waited       |
| 8 | Proki was running                        | `running` input; the computer asleep                                  | no cycles, no automations                                     |

### It fires too often, or at the wrong time

| Check                                     | Cause if…                                                                        |
| ----------------------------------------- | -------------------------------------------------------------------------------- |
| what sets the cooldown, and on which answers | it isn't set on "Later" or on no answer, so it asks again at the next check   |
| the branch back to idle                   | it returns at once and the moment is still true: needs a cooldown or a cooling state |
| soft rules and `every`                    | a soft rule checked every few seconds fires within the minute, whatever its chance |
| a self-loop (`goto` its own state)        | re-entering re-runs its actions: intended for ringing, wrong for a once-off      |
| the time condition                        | `daytime` is minutes since midnight; a `today` boundary at 04:00 can surprise late nights |
| two programs doing the same thing         | another program (shipped or the user's) gives a similar nudge: check `reference.programs` |

### Report

```text
Why: <one sentence, the cause, in behaviour terms>.
Seen: <the value that shows it, e.g. "the 'not in a session' condition is false: a session is running">.
Fix: <the change in one sentence> — want me to make it?
```

If nothing explains it, say what you checked, what each showed, and what to watch next time it happens
(e.g. "when it misses again, tell me the time and I'll read the history").
