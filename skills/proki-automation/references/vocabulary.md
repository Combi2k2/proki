# From everyday words to Proki

What people say, and what Proki builds it from. Use it to turn a wish into conditions without asking the
user anything technical. Every name here exists in the shipped Proki; confirm it in the live `reference`
before you rely on it (a user may have changed or removed one), and `evaluate` each condition.
In names like `x_next_at`, `x` stands for the program's name.

## Contents

1. [When: time and calendar](#when-time-and-calendar)
2. [When: what you're doing](#when-what-youre-doing)
3. [Unless: staying quiet](#unless-staying-quiet)
4. [How often](#how-often)
5. [What it does](#what-it-does)
6. [What it remembers](#what-it-remembers)
7. [What Proki can't see](#what-proki-cant-see)

## When: time and calendar

| They say                          | Condition                                        | Notes                                           |
| --------------------------------- | ------------------------------------------------ | ----------------------------------------------- |
| "at 5 pm", "after 17:00"          | `daytime >= 1020`                                | minutes since midnight: h × 60 + m. Pair with once-a-day |
| "between 9 and 12"                | `daytime >= 540 and daytime < 720`               |                                                 |
| "in the morning / evening"        | ask once, or use 6–12 / 18–22                     | say the hours you chose                         |
| "at night", "late"                | `night` (22:00–04:00), `wind_down` (from 22:00), `hard_stop` (00:00–04:00) | shipped signals |
| "on weekdays", "workdays"         | `weekday < 5`                                    | 0 Monday … 6 Sunday                             |
| "on weekends"                     | `weekday >= 5`                                   |                                                 |
| "on Mondays"                      | `weekday == 0`                                   |                                                 |
| "on the 1st of the month"         | `dd == 1`                                        | `mm` month, `yy` year                           |
| "today", "since this morning"     | `time - today` (minutes since the day began)     | Proki's day ends at **04:00**, not midnight     |
| "in 2 hours", "every 2 hours"     | a variable `x_next_at` set to `time + 120`, then `time >= x_next_at` | see patterns: Repeat every |
| "once a day"                      | a variable `x_day`; `x_day < today`, then set `x_day` to `today` | see patterns: Once a day |
| "every Friday at 4"               | `weekday == 4 and daytime >= 960` + once a day   |                                                 |

## When: what you're doing

| They say                                | Build from                                                      | Notes                                          |
| --------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------- |
| "when I'm at the computer"              | `active` (any input in the last 3 min)                          |                                                |
| "when I come back", "after a break"     | `active and quiet_before` (nothing for 3 h before)              | for short breaks: a signal `delay(stepped_away, 1)` and `active` |
| "when I step away"                      | `stepped_away` (nothing for 3 min); longer: `ts_max(active, 10) == 0` as a signal |                   |
| "sitting for an hour without a break"   | signal `ts_min(active, 60)`: active all of the last 60 min       | a break shorter than 3 min doesn't count       |
| "I've been on the computer 6 h today"   | `active_today >= 360`                                           | minutes, kept by the `day` program             |
| "when I'm focused", "in the zone"       | `focus_5m > focused_above`                                      | the user's own focus bands                     |
| "when I'm getting distracted"           | `focus_2m < distracted_below` and `active`                      |                                                |
| "doing deep work"                       | `on_deep` / `depth == 1`                                        | from the app's label                           |
| "on email / chat / a call"              | `label == 'Email'`, `'Chat'`, `'Video calls'`; `on_contact` for any | labels below                               |
| "on YouTube / social media / news"      | `label in ('Videos', 'Social media', 'News')`                   | or a site: `'youtube.com' in tab_url`          |
| "for more than 10 minutes"              | a signal `ts_min(<condition>, 10)`                              | "has been true for 10 minutes"                 |
| "more than 20 minutes in the last hour" | a signal `ts_sum(<condition>, 60) >= 20`                        | true/false sums to minutes                     |
| "in Slack", "in VS Code"                | `app_name == 'Slack'`                                           | check the exact name: `evaluate` `app_name` while it's open, or the apps view |
| "on a page about…"                      | `'word' in app_title`                                           | window title; fragile, say so                  |
| "during a focus session"                | `session.active`                                                |                                                |
| "25 minutes into a session"             | `session.active and session.minutes >= 25`                      |                                                |
| "after I finish a session"              | two states: `idle` → `in_session` on `session.active`; `in_session` → act on `not session.active` | a change is a move between states |
| "when I've focused enough today"        | `focused_today >= focus_goal`                                   | minutes                                        |
| "after I shut down for the day"         | `shutdown_done`                                                 |                                                |
| "when a task is due soon"               | `work.tasks` fields (`deadline`, `status`…)                      | read `reference` for the fields                |

**Labels** Proki sorts every app and page into (live list: `evaluate` `track.labels.name`):

| Group      | Labels                                                            | Depth        |
| ---------- | ----------------------------------------------------------------- | ------------ |
| Code       | Code editor, Terminal, Code hosting, Cloud & servers, Notebooks   | deep         |
| Making     | Documents, Notes, Slides, Spreadsheets, Design                     | deep         |
| Learning   | Documentation, Q&A sites, Papers, Courses; Blogs & articles        | deep; shallow |
| Tools      | AI assistant; Search engine                                       | deep; neutral |
| Contact    | Email, Chat, Video calls                                          | shallow      |
| Organizing | Calendar, Task boards, Banking, Maps & travel                     | shallow      |
| Leisure    | News, Social media, Videos, Games, Shopping; Music & podcasts      | distraction; neutral |
| System     | System, Accounts, App stores; Other                               | neutral      |

The user can relabel apps in the app, so prefer a label ("Chat") over an app name ("Slack") when they mean
the kind of thing.

## Unless: staying quiet

Add these without asking; mention them in the behaviour card.

| Guard                          | Condition                         | Add it when                                      |
| ------------------------------ | --------------------------------- | ------------------------------------------------ |
| no question already waiting    | `not asking`                      | **every** branch into a state that asks          |
| not during a focus session     | `not session.active`              | anything that isn't about the session itself     |
| not on a call                  | `label != 'Video calls'`          | anything with sound or a question                |
| only when they're there        | `active`                          | anything that asks or pokes                      |
| not after the day's shut down  | `not shutdown_done`               | work nudges                                      |
| not at night                   | `not night`                       | work nudges, unless the user works nights        |

## How often

| They say                        | Build                                                                 |
| ------------------------------- | --------------------------------------------------------------------- |
| "once", "just remind me"        | a once-a-day or one-off variable, never a bare condition              |
| "every hour"                    | next-due variable: `time >= x_next_at`, then `x_next_at = time + 60`  |
| "not too often", unstated       | a cooldown: 45–60 min for nudges, a day for check-ins                 |
| "if I say later, ask again soon"| "Later" or no answer → `x_next_at = time + 15`                        |
| "keep at me until I do it"      | each put-off shortens the wait, with a floor (see patterns: Snooze)   |
| "sometimes", "now and then"     | a soft rule checked rarely (`every: "15min"`), or a random-ish cooldown |

## What it does

| They say                             | Action                                                         |
| ------------------------------------ | -------------------------------------------------------------- |
| "remind me", "tell me", "let me know"| `poke` (a popup, a picture and a sound, nothing to answer)      |
| "ask me", "check with me"            | `ask_usr` with options, then branches on the answer             |
| "ask me what…", "let me write…"      | `ask_usr` without options: the answer is text                  |
| "start a session"                    | `set` `session.requested` to `true`                            |
| "stop the session"                   | `set` `session.stop_requested` to `true`                       |
| "start my shutdown"                  | `set` `shutdown_requested` to `true`                           |
| "lock my screen"                     | `lock`: forceful; confirm the user really wants it, give a warning poke first |
| "open my tasks / today"              | `open` with `path` `"'tasks'"`, `"'today'"`, `"'notes'"`, `"'metrics'"` |
| "note it down"                       | `append` to `note` (`{"content": "said"}`; check its fields)   |
| "figure out what it is", "judge"     | `ask_jev` (yes/no, choice, score) or `ask_llm`: needs a provider set up |

**Wording.** Write the text the user will read as a friendly, specific sentence, in the user's language
and tone. Put numbers in with `context.format`: `{"format": "{m:.0f} minutes without a break.", "values":
{"m": "..."}}`. A title is 1–4 words. Options are short verbs: "Done", "Later", "Skip today".

## What it remembers

| They say                             | Variable                                                     |
| ------------------------------------ | ------------------------------------------------------------ |
| "when I last did it"                 | global `x_last_at`, `type: time`, set to `time` on "done"    |
| "how many times I put it off"        | global `x_put_offs`, `type: integer`, `add 1` / `set 0`      |
| "my answer for today"                | global `x_day` + the answer; or a state variable if only that state needs it |
| "a setting I can change"             | global with a clear `desc`; the user changes it in the app or via `set_value` |

## What Proki can't see

Say so in one sentence, and offer what it *can* do:

| Wish                                   | Proki can't see                | Offer instead                                            |
| -------------------------------------- | ------------------------------ | -------------------------------------------------------- |
| "when I'm tired / stressed / happy"    | feelings                       | a check-in question at a sensible moment                 |
| "when I drink water / eat / move"      | the world off the computer     | a timed reminder, with "Done" counted                    |
| "when I'm on my phone"                 | other devices                  | "when you step away", or a question on return            |
| "before my 3 pm meeting"               | the calendar's events          | a fixed time; or the Calendar label when it's open       |
| "when my boss messages"                | message contents or senders    | `app_title` may name the chat: fragile, say so            |
| "how productive I was"                 | the value of the work          | focus and time measures, called what they are; see evidence.md |
