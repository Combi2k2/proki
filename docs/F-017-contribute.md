# F-017 Contribute

| Status | Area | Code |
| --- | --- | --- |
| 🟡 Needs polish | AI and assistants | `ui/src/views/contribute.tsx`, `proki/tools/suggestions.py`, `scripts/vault.gs` |

Send the developer a suggestion, even offline.

## How it works
- The page links Proki's code on GitHub and has a suggestion form, with a way to reach you.
- A suggestion is kept in Proki's data folder until it's delivered to the developer's sheet.
- It's sent at once; the main window retries on start, when back online, and every ten minutes.
- Assistants can send one too, through [F-016](F-016-mcp.md).

## Limits
- Buy me a coffee isn't there yet.
- A suggestion is at most 5,000 characters.
