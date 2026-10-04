# Deep Work → proki

Every idea from Cal Newport's *Deep Work*, with a first idea for how proki could
support it. We design and build these one at a time; each `→` line is a
starting point to refine, not a decision.

Status: `[ ]` not started · `[~]` designing/building · `[x]` done

## Foundations (needed by many items below)

- [x] **AFK awareness**: read ActivityWatch's AFK bucket; drop away time; never nudge while away
- [x] **Browser tabs**: use the ActivityWatch web extension for tab URL/title
- [x] **App categories**: user labels apps/sites as deep, shallow or distraction
- [x] **Focus sessions**: explicit "start focus" with a length and allowed apps
- [ ] **Input intensity** (optional): `aw-watcher-input` counts to tell working from idling

## Core ideas

  *(noted 2026-09-29 as promising: would tell reading from idle/watching better than the 3-min AFK timer; not set up yet)*
- [x] **Deep vs. shallow work**
  → classify every stretch of activity as deep or shallow (via categories + sessions)
- [ ] **Deep work hypothesis** (valuable, rare, meaningful)
  → onboarding/weekly message framing why the numbers matter; no feature on its own
- [~] **Quality = time × intensity**
  → score blocks by length *and* lack of interruptions, not just time spent
- [~] **Attention residue**
  → fragmentation rule exists; add interruption loops (repeated short visits to Slack/mail)

## Rule 1: Work deeply

- [ ] **Depth philosophies as configuration, not labels** (decided 2026-09-29): people
  aren't put into one type; each philosophy is a way to calibrate blocks and strictness.
  - [x] **Rhythmic**: same time every day + a chain of kept days
  - [ ] **Bimodal**: whole deep days vs. open days
  - [ ] **Monastic**: most of the day deep, shallow only in set windows
  - [ ] **Journalistic**: deep work whenever time appears (current ad-hoc sessions)
- [~] **Ritualize**: where, how long, how you work, what supports you
  → focus-session template: duration, allowed apps, pre-session checklist
- [x] **Grand gesture**
  → optional "big session" mode: long block, strict allowlist, all nudges but blockers off
  *(built 2026-09-29: tray → Grand gesture…; one long session (4 h / 8 h), wrap-up only at the end, breaks allowed (alarm 20 min, end 45 min); outcome kept as a note)*
- [x] **Hub-and-spoke collaboration**
  → separate "collaboration" and "solo" blocks; don't nudge about Slack during collaboration
  *(built 2026-09-29: in a session, 15 s on email / chat / a call → "can wait until the session is over", once per visit)*
- [x] **4DX 1: Focus on the wildly important**
  → user sets 1–2 goals; sessions are tagged with the goal they serve
  *(covered: goal groups with priorities; each session works on one group)*
- [x] **4DX 2: Act on lead measures**
  → track deep hours per goal (a lead measure), not outcomes
  *(covered: deep hours per day (quota) and per goal group (weekly review))*
- [x] **4DX 3: Keep a compelling scoreboard**
  → tray shows today's deep hours; simple daily/weekly chart
- [x] **4DX 4: Cadence of accountability**
  → weekly review popup: deep hours vs. goal, what helped, what got in the way
  *(built 2026-09-29: in the last workday's shutdown ritual; deep work per day vs. the
  daily goal, per goal group with its priority, chain, consistency, last week's answer;
  "what will you change next week?")*
- [~] **Be lazy (real downtime)**
  → after the workday ends, stop work nudges; flag work apps opened late in the evening
  *(partly: no capture questions after the shutdown; evening wind-down. Not built: flagging work apps late in the evening)*
- [x] **Shutdown ritual**
  → end-of-day popup: review inbox, park open loops for tomorrow, say "done"
  *(built 2026-09-29: 18:00 on weekdays; today's notes → task or note, what's on your
  mind → tasks, today's deep work and tomorrow's start, "Shutdown complete"; then no
  more capture questions that day)*

## Rule 2: Embrace boredom

- [ ] **Breaks from focus, not from distraction**
  → user schedules internet/distraction blocks; nudge when distraction apps are used outside them
- [ ] **Don't fill every lull**
  → detect "short idle → distraction app" pattern; gentle check-in, not a block
- [x] **Work like Roosevelt** (short, intense deadlines)
  → "sprint" session: user picks a task and a tight deadline; countdown in tray
  *(built 2026-09-29: tray → Sprint…; the deadline is the task's own estimate, countdown in the tray, "time's up" rings: done / 5 more / stop)*
- [x] **Productive meditation**
  → after a long session, suggest a walk with one problem to think about; ask for the result afterwards
  *(built 2026-09-29: thinking walk after good sessions or from the tray; counts as offline deep work; the outcome is kept as a note)*
- [ ] **Memory training**
  → out of scope for proki; mention in docs only

## Rule 3: Quit social media

- [ ] **Craftsman approach to tools**
  → weekly report per app/site: time spent vs. whether the user marked it as serving a goal
- [x] **Law of the vital few**
  → show which few activities produce most of the deep hours
  *(built 2026-09-29: "Most deep hours" in the weekly review: top 3 deep sites/apps)*
- [x] **30-day test**
  → user picks a service to quit for 30 days; proki tracks slips and asks the two questions at the end
  *(built 2026-09-29: tray → 30-day test…; slips = 10 s on it per visit, reminder with Close it; Newport's two questions on day 30; two noes → quit for good)*
- [ ] **Don't use the internet to entertain yourself**
  → evening/weekend report of entertainment browsing; optional planned-leisure prompt

## Rule 4: Drain the shallows

- [ ] **Schedule every minute**
  → morning planning popup with time blocks; compare plan vs. actual, allow re-planning
- [x] **Measure the depth of each activity**
  → ask the user to rate unknown activities once ("how long to train a graduate to do this?")
- [x] **Shallow-work budget**
  → user sets a percentage; tray warns when shallow time exceeds it
  *(built 2026-09-29: soft limit 30%, sampled prompts; tray and weekly review)*
- [x] **Fixed-schedule productivity**
  → user sets a workday end; shutdown ritual triggers then
  *(covered: the shutdown ritual at the workday end)*
- [ ] **Become hard to reach**
  → batch Slack/mail into scheduled windows; small-task inbox collects what comes up in between
- [ ] **Make senders do more work / process-centric email**
  → out of proki's reach (no email access); tips in docs only
- [ ] **Don't respond to everything**
  → out of scope; docs only

## Daily rhythm (user ideas, 2026-09-29)

- [ ] **Shift deep work toward the morning**, gradually (a few hours after waking tends
  to be best for most people; night-shift workers not covered for now)
- [x] **Plan tomorrow before bed** (prompted), so the morning starts with an obvious plan
  → also covers Newport's *shutdown ritual*. First version (time/task/warm-up dialog)
  replaced by "What needs to be done tomorrow?" feeding the to-do list (done)
- [x] **Task backlog** (replaces the day-plan to-do list and the small-task inbox): incoming
  tasks with deadline, own estimate, goal group; broken down until atomic
- [x] **Goal groups + session group choice** (urgency × priority), one group per session
- [x] **Daily deep-work quota** 4–10 h, rising past 80%
- [x] **Tasks at session start**, handed over one at a time
- [~] **AI integration**: conversation, planning, task breakdown, encouragement
- [x] **Sleep anchor**: wind-down pokes in the evening, escalating late at night; be
  understanding, not judgmental, when people resist it
- [ ] **Warm-up before deep work**: good-habit shallow work (morning routine, email,
  news) as an on-ramp, time-boxed. (No separate warm-up reminder: decided 2026-09-29)
- [ ] **Calendar / task-tracker integration** (calendar, Jira, Trello): place deep work
  inside events that look like deep work, without clashing with the rest
- [~] **Daily routines** (meals, shower, sport, morning routine): learned from the user's
  own data (typical times, not fixed numbers), then gently prompted. Collecting answers: done;
  reminders from typical times: next
- [ ] **Shallow and distraction periods** scheduled in the open time; deep work capacity
  is limited, so planned downtime is part of the design
