# NF-002 Privacy and local data

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Everything | `proki/settings.py` (where things are kept) |

Your activity stays on your computer. Only what an AI request needs leaves it, to the provider
you chose.

## How it works
- ActivityWatch records app names, window titles and pages, on this computer.
- Its input watcher records counts of keys and clicks, never which keys.
- Proki's data folder: `proki.db` (everything you make), `media/`, `suggestions.json`.
- Its config folder: `config.toml` (services, ports), `keys.json` and `tools-token`, both
  readable by you only.
- An LLM or Jev request carries the context that question needs, nothing more.

## Limits
- A suggestion you send ([F-017](F-017-contribute.md)) goes to the developer's sheet, with the
  contact you give.
- No export or backup yet (F-018, F-022).
