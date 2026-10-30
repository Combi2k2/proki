# F-002: what the feature review asks for

## Follow-up audit — 2026-10-30

- Onboarding keeps its first two messages and gives the setup steps a more conversational
  voice. The brain setup step opens Settings directly; Later still completes the welcome.
- Settings names the services LLM and Jev, includes colored Nebius and NVIDIA provider
  marks, and provides compact controls for ActivityWatch, NATS and MCP ports. Changes
  take effect together after restart; service saves preserve the port table. The launcher,
  engine, backfill command, MCP proxy and native app read the saved configuration.
- Appearance preferences and duplicate light-theme tokens were removed. All app windows
  start in dark mode, including users who previously saved a light preference.
- Import-graph and exported-binding checks found no unused UI modules after cleanup. Removed 34
  unreachable component declarations and the imports and exports they left behind.
  Helpers still used inside a component were kept, even when their exports were removed.
- Python layout was compared with unchanged `storage.py`, `services/activitywatch.py`,
  `tools/media.py` and `tools/records.py`, as well as the existing untracked installer
  entry point and tests. The formatter-only changes were removed: edited modules retain
  the project's aligned assignments, compact tool definitions and short guards. Repeated
  key-file reads were removed. Ruff's 21 unused-import findings in `core/ops/__init__.py` are intentional
  operator registration imports; deleting them would break expression lookup. No other
  Pyflakes findings were reported in `proki/` or `launch.py`.
- Removed the unused `benchmarks/` folder, obsolete Windows bootstrap, completed key and
  notes migration scripts, and the old Jev smoke script. These paths had no active callers;
  the benchmark and bootstrap imported packages already removed from Proki. Historical
  benchmark results remain in `docs/benchmarks.md`, without a stale execution command.
- Moved the remaining toggle variants into their sole consumer, `toggle-group.tsx`, and
  removed `toggle.tsx`. Removed the now-unreferenced `separator.tsx`, the unused `DoLabel`
  component and its imports, plus 23
  unnecessary exports from application modules; locally used helpers and types stay private.
- Verification covers Python regressions, native port parsing/validation, TypeScript
  unused-symbol checks, the frontend build, and isolated Chrome flows for onboarding,
  Settings navigation, provider selection, dark mode and port saving at desktop and
  narrow widths. New port settings do not disconnect the running app.

Remaining limits: Windows/WebView2 needs a native installer retest. Browser-extension
ports must be matched in the extension's own settings. Vite still reports its existing
large bundle and configuration-loader warnings. No live provider credentials were used
in the browser preview. The broader brevity prompt present in the LLM client was kept;
the context regression now checks that the instruction and supplied context both arrive.

## Objective

FEATURE_REVIEW.md, worked through: the programs made simpler where they ask for it (notes,
labels), the names the app can't do without kept safe, and the app's views (the automation
editor and its graph above all) made clearer to read and to change.

Scale: epic. 8 milestones, 29 slices. Complexity: very high overall; each slice low to medium.
Left out, as the review says: focus sessions and tasks' mechanics (fine as they are), the
sticker market place, the idea and thought pages, the theme chooser, Apps and time (not
reviewed yet).

## What there is (where each ask lands)

    notes         main.json: the `notes` variable (a list, kept in var_notes) and the signals
                  notes.inbox, notes.todos, notes.next_id, notes.next_due, notes.sort_at;
                  note_sorter.json (13 states: noidea, unsure, maybe, sure ask the same thing
                  in 4 wordings); capture, shutdown, task_picker, task_reminder append to it;
                  task_planner removes a todo once it's a task; serve.py on_notes; ui notes.tsx
    labels        classify.json (13 states, the same 4 wordings); `track` is
                  programs/code/classify.py's Track (frozen)
    app's names   serve.py READS: what the app reads, checked at each build (focus and
                  focus_lines aren't in it); a task's fields are work.py's Task (frozen): name,
                  desc, key, estimate, deadline, status, done_when, checkpoint are all there
    jev test      tools/settings.py test(): jev needs a model named before it's tried
    editor        ui programs.tsx (1005 lines: the state view, "Does its actions…" at 428),
                  program-forms.tsx (actions, branches), inspect.tsx (the resources drawer)
    graph         ui program-graph.tsx: dagre only (no spring layout in git history: it's new)
    live view     editor.detail(): the state now, `waking` (its next try), each condition's
                  value now. Which action is running isn't shown anywhere: it's in
                  core/programs.py (frozen)
    others        settings.tsx, manual.tsx + lib/preview.ts (the playground), metrics.tsx,
                  media.tsx + tools/media.py, today.tsx, main.tsx (the nav), popup copy in
                  the programs' JSON

## Milestones and slices

    M1 the programs                                        (no UI)
      1.1 the note sorter's 4 asks in 1 state              —
      1.2 the labels' 4 asks in 1 state                    —
      1.3 the app's names kept: focus, focus_lines          —
      1.4 the notes as `note`, bucket by bucket             a one-off script
      1.5 a sorted note kept, with where it went            1.4
      1.6 the labels without `track`                        dropped (Q2)
      1.7 the popups' wording, livelier and varied          1.1, 1.2
    M2 the services                                         —
      2.1 jev tried before its models are fetched           —
      2.2 settings, compact: one service at a time          —
      2.3 the provider a dropdown, with its logo            2.2
      2.4 a typed answer's schema in jsonjoy-builder        —
    M3 the automation editor                                —
      3.1 the state an overlay over the graph               —
      3.2 back: the state you were on                       3.1
      3.3 "every" said nowhere                              —
      3.4 actions: drag handle | icon + name | desc | edit, delete      3.1
      3.5 dragging: accepted or refused, as the board's cards           3.4
      3.6 branches: drag handle | ✓/✗ each condition | desc | goto | edit, delete   3.4
    M4 the resources drawer                                 —
      4.1 ✓/✗ coloured                                      —
      4.2 a typed variable edited by its type               —
      4.3 hidden variables shown or not                     —
    M5 the graph                                            —
      5.1 the nodes' text bigger                            —
      5.2 the capsules: one size, no name, along their line, clickable   —
      5.3 spring layout, as an option                       5.2
      5.4 waiting: an hourglass, and the time left          —
      5.5 a branch tried: ✓/✗ at its gate, the flow through  5.2
      5.6 a state's actions done, k of n                    dropped (Q3)
    M6 the notes and tables views                           M1 1.5
      6.1 the todos shown too, each note's link             1.5
      6.2 "Tables": every kind of record, as a table        —
    M7 the playground                                       —
      7.1 "Make it yours" gone                              —
      7.2 smoke variables: fake data, windowed operators work, its effect drawn   —
    M8 small things                                         —
      8.1 Today: no scroll bar                              —
      8.2 metrics in blue                                   —
      8.3 the media in buckets (its folders)                —
      8.4 a folder of stickers imported at once             —

M2, M4, M7 and M8 don't wait on anything: they can go in any order, alongside M1.

## Tasks

M1 the programs

  1.1 the note sorter's 4 asks in 1 state                                              done
    AC: a note's sorted as before (each confidence asked as now), from one `asking` state.
    [x] proki/programs/config/note_sorter.json: noidea, unsure, maybe, sure become `asking`,
        its wording worked out in the ask's context (`guess is None`, `conf >= 0.7`, `>= 0.4`);
        due's and weighing's 4 ways out become 1 each
    [x] tests/test_rituals.py: each confidence, the wording asked

  1.2 the labels' 4 asks in 1 state                                                    done
    AC: an app's label asked as before, from one `labeling` state.
    [x] proki/programs/config/classify.json: noidea, unsure, maybe, sure as above; looking's
        4 ways out become 1 (its label none, or proki's or jev's)
    [x] tests/test_rituals.py: the maybe and unsure wordings

  1.3 the app's names kept                                                             done
    AC: removing or retyping focus or focus_lines is refused, saying the app reads it; the
    editor shows them as the app's (a lock, no delete).
    [x] proki/serve.py READS: focus, focus_lines (number, array of numbers)
    [x] the editor's reference(): `"app": true` on the names READS has; ui programs.tsx
        KeptLine: the lock, no delete
    Note: a task's fields are code (Task): they can't be removed already; checked, not changed.

  1.4 the notes as `note`, bucket by bucket            (see "The notes, redesigned")          done
    AC: `note.todo`, `note.idea`, `note.thought`, `note.unsorted` are each a bucket's notes;
    no name starts with `notes`; your notes are all still there.
    [x] main.json: the variable and its signals renamed; every program that reads them
    [x] proki/serve.py on_notes, noted: the new names (and each note's link, read)
    [x] The one-off notes rename (script retired after completion): your copy's specs and var_notes renamed; run on a
        copy first, with a backup, your go-ahead before your proki.db
  1.5 a sorted note kept, with where it went                                           done
    AC: a todo made a task stays, in Todo, with its link to the task's group; the app opens it.
    [x] main.json: `link` on a note (a page's path, none: not dealt with yet)
    [x] task_planner.json: the todo's `link` set to 'tasks/' + its group's id, not removed;
        note.todo the ones without a link
  1.6 the labels without `track`                          (needs classify.py, frozen)
    AC: classify.json reads the apps as a kind of record (`apps`) and the one in focus as a
    signal; nothing named track.*
    [ ] proki/programs/code/classify.py: Track's names as `apps` (the kind) + `app` (in focus)
    [ ] classify.json, and what else reads track.* (depth's input)
  1.7 the popups' wording
    AC: each ask has several wordings, one picked at random; read through with you.
    [ ] each program's ask_usr: its format a choice of 2 to 4 (an expression's pick)

M2 the services
  2.1 jev tried before its models are fetched                                          done
    AC: "Test connection" for jev answers ok or why, with no model picked yet.
    [x] proki/tools/settings.py test(): no model: the provider's first listed, else its models
        fetched and the first of them, else said
  2.2 settings, compact                                                                done
    AC: the settings page shows one service's setup at a time; a change says it's saved where
    it was made.
    [x] ui/src/views/settings.tsx: a tab a service; unsaved changes said beside Save and on the tab
  2.3 the provider a dropdown with its logo                                            done
    [x] ui settings.tsx: shadcn Select; the logos as published (@lobehub/icons-static-svg 1.101.0, MIT) in
        ui/src/assets/providers/, by the provider's id (no logo key needed); openjev and Custom an icon
  2.4 a typed answer's schema in jsonjoy-builder                                       done
    AC: an LLM action's answer type is built in jsonjoy-builder, and saved as its schema.
    [x] ui package.json: jsonjoy-builder 1.0.4 (MIT); fields.tsx: an object type's fields are its field
        list (no JSON source), inline under the Type row as a list's "each one" is, loaded once one
        is shown; shown-only types keep the short list; schema-builder.css: the app's tokens, light
        and dark, its add button after the fields as every list has it
    [x] its schemas (draft-07 $schema, nested, enum, format, anyOf) pass the action's check

M3 the automation editor
  3.1 the state an overlay           AC: a state opens over the graph; a click outside closes it.   done
    [x] programs.tsx: Over, in the middle of the window, the rest dimmed behind it as a dialog's
        is; a click outside it, its close or Escape (no dialog open) closes it, back to the graph;
        program-graph.tsx: the state open ringed, onPane
  3.2 back                           AC: back goes to the state before, as far back as you went.    done
    [x] programs.tsx: a trail of the states gone through, in the program; Back names the one before;
        a rename replaces its place, leaving the program or closing empties it
  3.3 "every" said nowhere           programs.tsx:428 gone (the hourglass, 5.4, says it)           done
    [x] programs.tsx: the state's "checks its transitions every" line gone (the graph's "· 1 min"
        stays until 5.4's hourglass takes its place)
  3.4 actions: one line each         AC: grip | icon + name (Poke, Ask, Lock, Open, LLM, Jev, Set,
                                     Add, Sub, Append, Remove) | desc | edit, delete; no number   done
    [x] program-forms.tsx: ACTIONS each a short name, its lucide icon (Jev a key square, the LLM a
        robot's head) and its tint, behind the icon (the form's Kind says the same names);
        programs.tsx: the action's line, its desc or else what it does, in code. A state's only way
        out isn't called the else
  3.5 dragging, as the board's       AC: a drop that's kept shows it, one refused springs back
                                     with why (as the tasks' cards do)                            done
    [x] programs.tsx: Ordered and Line sortable (dnd-kit, the board's sensors: a pointer, or Space
        and the arrows), the up / down arrows gone; a drop shown at once, a refused one back where
        it was, shaken, with "Not moved:" and why under the list
  3.6 branches: one line each        AC: grip | each condition, ✓ green / ✗ red, one under the
                                     other | desc | goto | edit, delete                          done
    [x] programs.tsx: Way, its desc first, then each condition under it in columns (mark | the
        condition, cut when long | a rule's desc), a rule ✓ when it's more likely than not to fire,
        what doesn't hold greyed; where it goes in a column of its own; Truth, the green tick, red
        cross or dash, shared with the drawer. Long keys (states, programs, variables, fields,
        apps) cut, whole on hover
    Files: ui/src/views/programs.tsx, program-forms.tsx (split out: program-state.tsx, the
    overlay, its actions and branches), the icons from lucide-react.

M4 the resources drawer
  4.1 ✓/✗ coloured (done: Truth, as the branches') · 4.2 a typed variable's editor by its type (a number, a list, an object's
  fields) (done: the Now field, yes/no, a number, a time, a text, a list's items, an object's fields, else JSON) · 4.3 hidden
  variables (`_x`) shown on a switch (done, as you choose: any line hidden by its eye, kept in this window; the switch shows
  them, greyed)
    Files: ui/src/views/inspect.tsx; editor.reference(): hidden ones too, marked

M5 the graph
  5.1 text bigger (done) · 5.2 capsules: one size, no name, along their edge, a click opens the branch (done: its
      number, turned along its arrow, the lanes' apart)
  5.3 spring layout (d3-force), a switch beside the layout's (done: no columns, no Tidy; the boxes laid out once
      by springs. Springs, a view beside curved, elbow and straight: live, its arrows arcs, a box dragged pulls
      the others, a double-click fixes one (its border bolder); a box no longer lost while you drag it)
  5.4 waiting: an hourglass on the state, and the time left to `waking` (done: a clock, by the second)
  5.5 each cycle, the branch tried: the conditions' values now drawn at its gate, ✓ and the
      flow through, ✗ and it stops (from the conditions' values: what would happen now) (done: in the state it's in, the
      capsules tinted green or red only while it checks and a second after, the ones after the one taken not tried;
      the flow only while it checks, a halo and a turning hourglass while it waits; read each second while a wait's
      over; while its actions run, a ring running round it and "doing...")
  5.6 k of n done, a ring on the state (needs core/programs.py, frozen: which action runs)
    Files: ui/src/views/program-graph.tsx, ui package.json (d3-force)

M6 the notes and tables views
  6.1 the Todo bucket shown; each note's link ("→ Thesis", opens it)    ui notes.tsx    done
  6.2 "Tables" in the nav: each kind (work.groups, work.tasks, yours), its records read_records
      gives, as a table                                                  ui main.tsx, tables.tsx  done
      (a tab a kind; id, your fields, what proki works out, made and changed; a head sorts, a
      search filters, a list or a record opens as its own table; read only)

M7 the playground
  7.1 "Make it yours" gone                                               ui manual.tsx   done
  7.2 the playground, on smoke data of its own (proki/assets/smoke.json): 2 signals, a value a
      minute; 2 numbers, a list, a text, a record, records            proki/playground.py,
      ui playground.tsx                                                                  done
      (on review: not your names made up, its own. The signals on top, read only; on the left an
      operator on one of them, a cursor sweeping through time showing what it reads: every's
      bin and its mean, a window and its mean, min or max, the minute delay reads; an
      expression of your own, on its names, else yours as they are now; an action (set, add,
      sub, append, remove) on its variables. On the right its variables: the place the end of
      what you type names outlined, what an action changed flashing. Then the docs. Found out
      first: the registry swapped for the call, its signals played back as `fill` does, so no
      core change; yours and the clock are as they were after)
  7.3 the variables as the drawer shows them; each action's what and where to start; the
      docs a deck                                                        ui playground.tsx,
      deck.tsx, manual.tsx                                                               done
      (on review: the variables' lines the drawer's (its icon, name and value, a list or record
      opened in place), so both are refined as one. An action switched to starts on one that
      works (remove: tasks, id 2; xs holds numbers, no ids), and says what it does; `true`
      unknown is told to be True. The topics, whose examples couldn't run on the playground's
      names, are a deck of ten slides: a screenshot each, ui/src/assets/help/<slide>.png, a
      placeholder saying which until it's there, and what it shows under it)
  7.4 expressions coloured as Python is, shown or typed                  ui code.tsx,
      program-forms.tsx, programs.tsx, fields.tsx, playground.tsx, manual.tsx, deck.tsx  done
      (on review: keywords, True/False/None, strings, numbers, the functions called, the names
      and the operators each a colour of their own, in both themes. Typed: the field's text
      drawn over it, coloured, its caret and selection its own. Where: a transition's
      conditions, shown and in its form; an action's expression; a field's formula and then;
      the playground; the reference; the deck's code)

M8 small things
  8.1 Today: no scroll bar · 8.2 metrics in blue · 8.3 the media grouped by its folder
  (bugcat/, yours/), one group open at a time · 8.4 a folder added at once (add_media `path`
  a folder: each picture and sound in it)                                                    done
    (8.1 the panels' scroll bars hidden, still scrolling · 8.2 one blue, `--metric`, each mode's ·
    8.3 grouped by the folder in the name ("bugcat/sad"), else Yours or Proki's: the keys of yours
    can't say it (`yours/<hash>`, the library's, frozen), a name shown without its group's folder ·
    8.4 "Add a folder", or one dropped: each picture and sound in it, its subfolders' too, named
    after it, "stickers/happy")

## The notes, redesigned (what the review asks)

    note                 the notes, each:
      id, content, at, due        as now
      bucket                      Unsorted | Todo | Idea | Thought (as the popups say them: only
                                  Inbox renamed)
      guess, conf, urgency        jev's, as now
      link                        where it was dealt with: a page's path ("tasks/3"); none: not yet
    note.open            the ones not dealt with yet: no link (where takes one condition, so
                         note.todo goes through it)
    note.unsorted        the ones not sorted yet           (was notes.inbox)
    note.todo            the todos not made tasks yet      (was notes.todos)
    note.idea            the ideas
    note.thought         the thoughts
    note.next_id, note.next_due, note.sort_at     as now

A note is never removed by a program now, only by you. The notes view shows each bucket, the
todos too, and a note with a link says where it went and opens it there. The idea and thought
pages come later: their notes' link stays empty till then.

## Anti-rationalization check

- 1.4 is a rename across 6 programs, the app and your database: one slice, since half-renamed
  names don't build. The script is its own task, run on a copy first.
- 5.5 shows what would happen now, from the conditions' values, not the engine's real trip:
  said so in its AC, so it isn't sold as more.
- 7.2 has its unknown (can a made-up series go through the windowed operators without core?)
  found out in its first task, before the UI.
- No "the copy later": 1.7 reads every ask through with you, not just the ones in the review.

## Risks

    RISK: renaming notes → note leaves your copy's programs (in proki.db) on the old names
    IMPACT: your note programs stop building; the app's notes view is empty
    LIKELIHOOD: high without the script
    MITIGATION: the one-off script renames your specs and var_notes together; on a copy first,
          a backup, and your go-ahead

    RISK: 1.6 and 5.6 need frozen files (programs/code/classify.py, core/programs.py)
    IMPACT: they can't be done as written
    LIKELIHOOD: certain
    MITIGATION: your go-ahead for those files (Q2, Q3); without it, 1.6 waits and 5.6 is dropped

    RISK: jsonjoy-builder's schemas aren't what an LLM action takes (its own keywords)
    IMPACT: a type built there is refused as it's saved
    LIKELIHOOD: medium
    MITIGATION: 2.4's first task: build one, check it passes the action's check; else limit
          its keywords (checked: they pass)

    RISK: dragging actions reorders `at`, and the board's drag code is in tasks.tsx (726 lines)
    IMPACT: two drag-and-drops that drift apart
    LIKELIHOOD: medium
    MITIGATION: the board's accept/refuse effect lifted into one component both use (3.5)

    RISK: 7.2's smoke series need the operators to read a made-up history
    IMPACT: the playground can't show windowed operators
    LIKELIHOOD: medium
    MITIGATION: found out first; if the history can be handed in (Stream.storage is set from
          outside), it's done there, else 7.2 is cut to instant operators and said so

## Checkpoint gates

- Gate 0: done: every review item found in the code, the frozen files and the data it touches.
- Gate 1 (after 1.1–1.3, 2.1): the suite passes; the note sorter and labels asked for real once.
  Passed 2026-10-27 (307 tests). On the way: jev's key was malformed (401 on every ask), saved
  again; the 8 websites its failed guess had marked as asked were reset to be guessed again
  (a backup first: proki.db.bak-2026-10-27-reguess).
- Gate 2 (after 1.4–1.5): the script run on your copy, your notes counted the same before and after.
  Passed 2026-10-27: 9 notes (6 Idea, 3 Thought) before and after, read back from the engine;
  a backup first (proki.db.bak-2026-10-27-notes).
- Gate 3 (after M3): a state opened, an action and a branch dragged, back used, in the app.
- Gate 4 (after M5): the graph watched through one program's cycle (pomodoro).
- Gate final: the review's items each checked off with you; the suite, ruff and the UI's build.

## Decisions

- Q1, the `note` space: as designed above (one `note` list, a list per bucket).
- Q2, classify.py: stays frozen, and `track` stays: 1.6 is dropped (that review note was written
  before the backend review was done).
- Q3, core/programs.py: stays frozen; 5.6 (the k of n ring) is dropped. The actions mostly run
  within one cycle, so it'd rarely show anything between 0 and n; the hourglass (5.4) and the
  branch tried (5.5) say where the flow is.
- Added on review: the sidebar's New note became **Contribute** (the tray's New note stays). It has
  the code on GitHub, Buy me a coffee (soon), and a suggestion form. A suggestion is kept in the
  outbox in proki's data folder until it reaches the developer's Google Sheet (scripts/vault.gs,
  deployed as a web app, its URL as `VAULT` in proki/tools/suggestions.py). It's sent at once,
  then the main window retries on start, when the computer is back online, and every ten minutes.
