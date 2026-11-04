# F-017 Support

| Status | Area | Code |
| --- | --- | --- |
| 🟡 Needs polish | AI and assistants | `ui/src/views/support.tsx`, `proki/tools/suggestions.py`, `scripts/vault.gs` |

Send the developer a suggestion, even offline.

## How it works
- The page links Proki's code on GitHub and its Buy me a coffee page, and has a suggestion form, with a
  way to reach you.
- A suggestion can carry up to three pictures: added from a file, or a screenshot pasted in. Each is
  shrunk to 1600 pixels on its longer side and kept as a JPEG.
- A suggestion is kept in Proki's data folder until it's delivered to the developer's sheet.
- It's sent at once; the main window retries on start, when back online, and every ten minutes.
- Assistants can send one too, through [F-016](F-016-mcp.md).

## Limits
- A suggestion is at most 5,000 characters, and each picture 2 MB.
- Dropping a picture on the form doesn't add it yet; adding one or pasting it does.
