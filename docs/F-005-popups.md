# F-005 Popups

| Status | Area | Code |
| --- | --- | --- |
| 🟡 Needs polish | Your day | `ui/src/pages/popup.tsx`, `proki/channels/popup.py`, `proki/core/actions/ui.py` |

How automations talk to you: a short question to answer, or a poke to notice.

## How it works
- One popup at a time, each with a picture and a sound from the media library ([F-008](F-008-media.md)).
- A question's options decide its shape: none is a text box, one to three are buttons, four or
  more a dropdown.
- Later dismisses a question as if it timed out (two minutes by default). An `immediate`
  question has no Later.
- A poke is a message that rings until closed, for when you may not be looking.
- Automations can also lock the screen or open a page of the app.

## Limits
- Wording differs across automations; a review of it is still to do.
