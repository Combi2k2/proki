# F-016 MCP tools

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | AI and assistants | `proki/tools/`, `proki/tools/stdio.py`, `ui/app/src/main.rs` (Install command-line tool) |

An AI assistant (Claude Code, Codex, OpenClaw, ...) works with your tasks, automations, media
and settings.

## How it works
- `proki mcp` is a stdio MCP server: it starts Proki if it isn't running, then passes messages
  to the local tools server with its token.
- Install it from the tray's menu, then add it: `claude mcp add proki -- proki mcp`.
- Tools: records (read, add, change, move, remove), programs (reference, evaluate, playground,
  apply changes, switch, reset, unused), media (library, pools, picks), settings (services,
  ports) and suggestions.
- Program changes are checked together: all are kept, or none.
- The `proki-automation` skill (`skills/proki-automation/`) teaches an assistant to build, change and
  explain automations with these tools: `npx skills add Combi2k2/proki --skill proki-automation`.

## Limits
- Local only: the tools server listens on 127.0.0.1 ([NF-003](NF-003-security.md)).
