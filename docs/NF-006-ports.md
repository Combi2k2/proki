# NF-006 Local ports

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Settings | `ui/src/views/settings.tsx`, `proki/tools/settings.py`, `proki/settings.py` |

Change the ActivityWatch, message bus and tools ports when a default is taken.

## How it works
- Each must be a different whole number from 1 to 65535.
- Saved in `config.toml`'s `[ports]`; saving a service keeps them.
- Applied together after you quit and reopen Proki. The launcher, engine, backfill, `proki mcp`
  and the app all read them.
- A saved port that isn't usable falls back to the default.

## Limits
- ActivityWatch's browser extension keeps its own port setting: change it there too.
