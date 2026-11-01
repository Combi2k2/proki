# NF-003 Security

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Everything | `proki/tools/server.py`, `launch.py` (`nats.conf`), `ui/*.html` |

Only Proki and what you connect can reach its local services.

## How it works
- ActivityWatch, NATS and the tools server listen on 127.0.0.1 only.
- One token, made the first time and readable by you only, guards both the tools server
  (`Bearer`, compared in constant time) and NATS (written to `nats.conf`, mode 0600).
- The engine and the app read the token to connect; `proki mcp` sends it for the assistant.
- Expressions are parsed with a whitelist, never `eval`'d.
- Each app page sets a Content Security Policy: its own scripts only, local media.
- API keys are kept in `keys.json` (0600) and never shown again.

## Limits
- Another program running as you can read the token.
- On Windows, mode 0600 does nothing: the files are protected by your user folder's permissions.
- Installers aren't signed ([NF-004](NF-004-release.md)).
