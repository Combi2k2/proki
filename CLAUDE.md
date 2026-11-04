# Proki

A focus companion: a Python engine (`proki/`) runs your automations over what ActivityWatch records, and a
Tauri + React app (`ui/`) shows your day, tasks, notes and the automations themselves. The engine's tools
serve the app and AI agents alike, over MCP (`proki/tools/`).

```bash
python -m pytest -q                                   # the engine's tests (the venv is active already)
cd ui && npx tsc --noEmit -p . && npx vite build      # the app: types, then a build (there's no lint config)
```

## Skills to load

Load the skill **before** the work, not after. When none of these fits, use `find-skills` to look for one.

| When you're about to | Load |
| --- | --- |
| change anything in `ui/src` | `ui-ux-pro-max`, `impeccable` |
| write or change words, labels, empty states, or a screen's layout | `better-interface` (it routes to `better-writing`, `better-layout`, ...) |
| add a function, a helper or a component | `graphify`: query the graph for an existing one first (`/graphify query "..."`), and refresh it after (`/graphify . --update`) |
| work on dialogs, selects, tooltips | `shadcn` |
| build, change or explain an automation, or touch the MCP tools | `proki-automation` (the project's own, `skills/proki-automation/`) |
| start a feature bigger than a fix | `planning-and-task-breakdown`, then `incremental-implementation` |
| hunt a bug or a failing test | `systematic-debug` |
| finish a change, before committing | `code-simplification`, then `git-commit` |

Redundant logic is this codebase's recurring cost: the same walk, parse or lookup written twice in two
files. Searching first (`graphify`, `grep`) is cheaper than merging later.

## Code style

The full rules are in `.claude/rules/principle-code-style.md`; the files under `proki/core/`, `proki/model/`,
`proki/settings.py` and `proki/tools/base.py` show them in practice. In short:

- **Short, expressive names**: a past participle for what a value is (`said`, `kept`, `found`), a verb for
  what a function does. No `data`, `result`, `tmp`, no type in a name.
- **No helper that isn't needed**: one earns its definition when two places call it, or it names a step.
  A one-use helper, lambda or wrapper is inlined.
- **Neighbouring lines look alike**: `=` and `:` aligned, trailing comments aligned, one-line `if`s only
  in a group. Lines up to ~160 to keep a statement whole. Never flatten a one-name-a-line import.
- **Docstrings speak to the caller only**: what to give and what comes back, never how it works; no
  constants, file names or framework names ("the app", not "Tauri"). A module's docstring lists what it
  gives as an aligned table.
- Validation in `__post_init__`, raising `ValueError` that says what's wrong and what was given.
  Truthiness over `is not None` unless `0`, `""` or `False` mean something.
- An `__init__.py` exports only what downstream code imports from it.
- The same style in TypeScript: aligned `const` groups, short names, one docstring line per component
  saying what it shows and what its props mean.

### Off limits

- **Frozen files, never edited**: `proki/utils.py`, `proki/types.py`, `proki/storage.py`,
  `proki/settings.py`, `proki/tools/base.py`, and everything in `proki/channels/`, `proki/services/`,
  `proki/core/`, `proki/engine/`, `proki/programs/code/`, `proki/model/`. A change there is the user's call:
  ask.
- **`.env` files** only through the credentials tools, never read or written directly.
- **Commits** only when asked; `area: what changed` messages; a file the user edited on disk is theirs
  (point out a bug, don't revert it).
- **Icons and logos** from lucide-react or a published set, its source named. Never a hand-drawn SVG.

## Design taste

What the user has asked for, round after round. Keep it.

- **One thing, one look.** The same kind of thing looks and behaves the same everywhere: a table you made
  and one the app keeps open the same dialog; inputs list like signals; every resource's dialog has the
  same rows in the same order.
- **Changed where it's read.** Values read as plain text; a dotted underline on hover says it can be changed;
  a click edits it in place (`Editable`, `ui/src/views/in-place.tsx`). No input-box chrome on what's
  already there. Forms stay for making something new.
- **Details open over, not down.** A row that has more to show opens a dialog over the one you're in; it
  doesn't expand the list.
- **Tables when things line up.** Things with the same parts sit in a table with real columns, a header row,
  and room for what goes in them (three chips fit a sources column). An implicit table is made explicit.
- **Chips with an icon, one vocabulary.** Write sources: `expr`, `auto`, `user`, `proki`, `jev`, `llm`.
  Readers: `auto`, `rule`, `signal`, `variable`, `proki`. Each has its own icon and tint; an action shows
  its icon on its tint wherever it appears (`Tinted`).
- **Colour means something.** Types have their colour (`--type-<kind>`), used for the icon, the type's
  name and a value's brackets (`[…]`, `{…}`, the dots grey). Tints follow the sidebar: Automations
  emerald, Metrics cyan, Apps violet. Colours come from tokens in `ui/src/index.css`, never a raw hex.
- **Words are plain and short.** Say what it is to the person using it: "Nothing reads it.", "Set by you",
  "None: it waits." No engine names, no framework names, no jargon a user wouldn't say. One ellipsis
  character (`…`), never three dots.
- Proki is dark-themed; shadcn (Radix) and Tailwind v4 are the kit.

## Where things are

| Part | Where |
| --- | --- |
| the engine: signals, rules, programs, records | `proki/core/` (frozen), `proki/engine/` (frozen) |
| what the app and agents read and change | `proki/editor.py`, `proki/tools/` |
| the automations Proki ships | `proki/programs/config/` (JSON), `proki/programs/code/` (Python, frozen) |
| the app's views | `ui/src/views/`; the window `ui/src/pages/main.tsx`; the tools' types `ui/src/lib/proki.ts` |
| one page a feature | `docs/` (F-0xx features, NF-0xx the rest) |
