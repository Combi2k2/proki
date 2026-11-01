# F-013 Tables

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Make it yours | `ui/src/views/tables.tsx`, `ui/src/views/fields.tsx`, `proki/core/records/`, `proki/serve.py` (`proki.app.fields`) |

Each kind of record (tasks, groups, notes, your own) as a table, with fields you define.

## How it works
- A row per record: its id, your fields, what Proki works out for it, then when it was made
  and changed. Sort by a column, search across all of them.
- A list or a record in a cell opens as its own table.
- A field has sources in order, the first with a value wins: a value you set, an expression,
  Jev, or the LLM.
- Rename a field and what reads it follows; remove one Proki shipped and it comes back as shipped.
- Automations read and write records as variables (`work.tasks`, `work.task`, ...).

## Limits
- This page reads records; add and change them in their own pages (Tasks, Notes), or through [F-016](F-016-mcp.md).
