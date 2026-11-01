# F-008 Media

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | Your work | `ui/src/views/media.tsx`, `proki/services/media.py`, `proki/tools/media.py` |

The pictures and sounds popups show and play: Proki's stickers, and your own.

## How it works
- Pictures as a grid and sounds as a list, yours first, grouped by the folder they came from.
- Add files or a folder by button or by dropping them; each is copied into Proki's data folder.
  The same file added twice is kept once.
- Rename one; its key never changes, so automations keep finding it.
- Pools are named sets a popup draws from; a poke or a question can have its own picks.
- A deleted one is gone for good a week later. One still in use can't be deleted.

## Limits
- One large library: packs you can switch between are planned (F-019).
