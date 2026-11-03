# The Proki MCP tools

Every tool the `proki` MCP server gives, grouped by job: when to reach for it, what to send, and the traps.
Tool names are `mcp__proki__<name>` and are deferred: load them with `ToolSearch` (`select:a,b,c`) first.
A mistake comes back as the tool's error, naming the one place to fix (`stretch.idle: way out to 'asking':
unknown name 'stretch_du'`). Fix that place and send again.

## Contents

1. [Reading](#reading) · 2. [Changing programs](#changing-programs) · 3. [Running state](#running-state) ·
4. [Media](#media) · 5. [Records](#records) · 6. [Settings](#settings) · 7. [Suggestions](#suggestions)

## Reading

None of these change anything. Use them freely.

| Tool            | Use it to                                                                 | Send                      |
| --------------- | ------------------------------------------------------------------------- | ------------------------- |
| `reference`     | see everything a program can use, with live values, and every program      | nothing                   |
| `get_program`   | see one program as it runs: current state, each condition's value now, `uses` | `name`                |
| `program_specs` | see one program's specs as they're edited, in order, with `default`/`changed` | `name` (null: global scope) |
| `list_specs`    | list all specs of one kind (e.g. every rule), optionally of one program   | `kind`, `program?`        |
| `evaluate`      | an expression's value and type now                                        | `expr`                    |
| `playground`    | try an expression or action on made-up data                               | `expr?`, `action?`, `variables?` |
| `unused`        | list what nothing depends on, as removal changes                           | nothing                   |

**`reference`** is ~160 KB. When the answer is saved to a file, query it with `jq` (examples in SKILL.md
Setup). Each signal and variable carries `value` (now), `scope`, and `from` (`config` or `code`: kept by
code, read-only). `programs[]` has `on`, `state` (current), `kind` (`config` editable, `code` built-in).

**`get_program`** is the diagnosis tool. Each state lists `do` (actions), `vars`, and `next`: each branch
with `conds` (each `{expr, value}` **evaluated now**) and `rules`. Top level: `on`, `state` (where it is now),
`waking` (when it next checks), and `uses` (every variable, signal, rule and input it reads, with values,
and whether it `sets` them).

**`program_specs`** gives the editable form: `program`, `states`, `branches`, `actions`, `variables`,
`signals`, `rules`, each in order. **A branch's or an action's `at` is its position among its state's**
(count from 0, in this list's order). Use it to find what to `update`. `default: true` means Proki ships
this program (it can be reset); `changed: true` means the user's version differs from the shipped one.

**`evaluate`** works an expression out as an action would: windows (`ts_*`, `delay`, `every`) give `null`.
Evaluate a signal by name instead.

**`playground`** has its own sample signals, a value a minute from 09:00: `a` (focus, 0–1) and `b` (keys a
minute, with an away gap of `null`s), and sample variables `goal`, `streak`, `xs`, `mood`, `task`, `tasks`.
With `expr`, it returns the value at each minute, so windows work there. With `action`
(`{"set": {"name": "streak", "expr": "streak + 1"}}`; set, add, sub, append, remove) it returns the variables
after. The user's own signals and variables aren't there; nothing of theirs changes.

## Changing programs

Each of these **changes the running app immediately**.

### `apply_changes`: the default way to write

```json
{"changes": [
  {"op": "add",    "kind": "program",  "data": {"name": "stretch", "title": "Stretch breaks", "desc": "…", "tags": ["health"]}},
  {"op": "add",    "kind": "state",    "data": {"program": "stretch", "name": "asking", "every": 0}},
  {"op": "update", "kind": "rule",     "data": {"name": "stretch_due", "changes": {"rhs": 60}}},
  {"op": "remove", "kind": "branch",   "data": {"program": "stretch", "state": "idle", "at": 1}}
]}
```

- `kind` is one of `input`, `variable`, `signal`, `rule`, `program`, `state`, `branch`, `action`.
- `data` is what the matching single tool takes (`add_rule`, `update_rule`, `remove_rule`…).
- The changes apply **in order**, then the whole result is **built and checked once**. Any mistake: none is
  kept, and the error names the place. So one batch can add a program and everything it needs, in any
  order that refers only to things added earlier or already there.
- An added `program` gets its `initial` state (`idle`) made for it if the batch doesn't add one.
- Returns each change's result: the spec added or updated, or the list removed.

### Fields of each kind

Required fields are **bold**. Full schemas: the `add_<kind>` tool's arguments, or `proki/model/specs.py`.

| Kind       | Fields                                                                                                    |
| ---------- | --------------------------------------------------------------------------------------------------------- |
| `program`  | **`name`**, `title`, `desc`, `icon` (kebab-case Lucide-style name; empty: from tags), `tags`, `initial` (`idle`) |
| `state`    | **`program`**, **`name`**, `desc`, `every` (minutes, or `"6s"`, `"5min"`, `"1h"`; default 1)               |
| `branch`   | **`program`**, **`state`**, **`goto`**, `when` (rule names and expressions; `[]` = else), `desc`, `at`     |
| `action`   | **`program`**, **`state`**, **`kind`** (`poke`, `ask_usr`, `set`…), `params`, `name` (made if left out), `desc`, `at` |
| `variable` | **`name`**, `scope`, `program`, `state`, `value` (start), `type`, `desc`                                  |
| `signal`   | **`name`**, **`expr`**, `scope`, `program`, `state`, `type`, `backfill` (history kept: minutes or `"1d"`), `persist` (saved across restarts; needs backfill), `desc` |
| `rule`     | **`name`**, **`lhs`**, **`cmp`** (`gt ge lt le eq ne`), **`rhs`**, `softness` (0), `level` (1), `scope`, `program`, `state`, `desc` |
| `input`    | **`name`** (a primitive Proki knows), `backfill`                                                          |

Scope fields: `global` takes no `state` (a `program` if one brings it); `program` takes its `program`;
`state` takes `program` and `state`. Names are letters, digits and `_`. Name a program's globals with its name and an underscore
(`stretch_next_at`); a dotted prefix that's a program's name is refused (see mechanics.md).

### Finding what to update or remove

`update` and `remove` find a spec **by its identifying fields**; `update` adds `changes`.

| Kind                         | Found by                              |
| ---------------------------- | ------------------------------------- |
| `program`, `input`           | `name`                                |
| `variable`, `signal`, `rule` | `name`, `scope`, `program`, `state`   |
| `state`                      | `program`, `name`                     |
| `branch`, `action`           | `program`, `state`, `at`              |

```json
{"op": "update", "kind": "action", "data": {"program": "stretch", "state": "asking", "at": 0,
  "changes": {"params": {"title": "Stand up?", "context": "You've sat for an hour.", "options": ["Done", "Later"], "result": "answer", "default": 1}}}}
```

Traps:
- **`changes` replaces whole fields.** Changing one param of an action means sending the **whole**
  `params` object, with the rest as it was (copy it from `program_specs`). The same for `when` lists.
- **`at` shifts.** After removing or inserting a branch or action, the later ones' `at` change. In one batch,
  order removals from the highest `at` down, or re-read `program_specs` between writes.
- **Renaming** a program or state with `update` renames what it owns (its states, branches, actions) along
  with it. Expressions elsewhere that name it aren't rewritten: search them first.
- **Removing** a program removes its states, branches, actions and every variable, signal and rule it
  brings. Removing a state removes its branches, actions and state-scoped specs. The result lists all of it.
  Removal can't be undone except by adding it back: keep the `program_specs` read from before.

### The single-spec tools

`add_<kind>`, `update_<kind>`, `remove_<kind>` for each of the 8 kinds do one change each (same data as
above). Use them only for a one-field tweak; anything that needs two changes to build goes in one
`apply_changes`.

### Cleaning up

- **`unused`** lists what no program's way out, no app view and no metric depends on, down any chain, as
  ready-made removal changes. Read-only. Useful to show what's stale.
- **`remove_unused`** removes **all** of that, across every program, at once. Only when the user asks for a
  clean-up, after showing them the `unused` list. To remove just some, send those changes yourself through
  `apply_changes`.

## Running state

| Tool             | Does                                                                     | Notes                                 |
| ---------------- | ------------------------------------------------------------------------ | ------------------------------------- |
| `switch_program` | turns one on or off (`name`, `on`)                                       | on again, it starts over in its initial state; the reversible way to "stop it" |
| `set_value`      | sets a variable now (`name`: its full name, `value`)                     | "skip today", "ask me now", test a branch; type must fit |
| `reset_program`  | puts a shipped program back as Proki ships it, with what it brings (`name`; null: global scope) | only where `program_specs` says `default: true`; loses the user's edits to it |
| `cycle`          | reads (no args) or sets (`seconds`) how often Proki looks                 | global: changes every program's pace and the computer's load. Not for one program |

## Media

A poke shows a picture and plays a sound; a question can too. They're chosen **by the action's id**
(`program.state.name`, shown in `program_specs`), not in the program.

| Tool                       | Does                                                                |
| -------------------------- | ------------------------------------------------------------------- |
| `get_media`                | the library: `kind` (`image`/`sound`), `keys`, `offset`, `limit`    |
| `add_media`                | copies a file or a folder of the user's in (`path`)                 |
| `rename_media`, `remove_media` | renames one (key stays) / removes some (gone after a week)      |
| `get_picks`, `set_picks`   | what one action draws from, by its id                               |
| `list_pools`, `set_pool`   | what popups draw from where no action says (e.g. `questions`)       |

## Records

Tasks and groups the user keeps in Proki: `work.groups`, `work.tasks` (others listed by `read_records`'
error if a name is wrong). Times are ISO text.

| Tool                                   | Does                                              |
| -------------------------------------- | ------------------------------------------------- |
| `read_records`                         | a kind's records, in the user's order             |
| `add_record`, `change_record`          | a new one / some of its fields                    |
| `remove_record`, `move_record`         | delete (a group takes its tasks) / reorder. To set one aside, `change_record` its `status` to `dropped` |
| `read_ops`, `add_op`, `change_op`, `remove_op` | changes suggested to the groups' tasks    |

Programs read records through variables (`work.tasks`, `work.task`, `note`…); check their fields in
`reference.variables`.

## Settings

`ask_llm` and `ask_jev` only answer if their provider is set up.

| Tool              | Does                                                                     |
| ----------------- | ------------------------------------------------------------------------ |
| `get_settings`    | each service as set: provider, url, model (null: not set)                |
| `set_settings`    | changes them. Never ask the user to paste a key into chat; send them to the app's settings |
| `test_connection` | whether one answers                                                       |
| `list_models`     | the models at a provider                                                  |

## Suggestions

`suggest` keeps a note for Proki's developer (sent with `send_suggestions` once online). Use it when the
user wants something Proki can't observe or do yet, with their agreement.
