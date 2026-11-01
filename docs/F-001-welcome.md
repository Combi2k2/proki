# F-001 Welcome

| Status | Area | Code |
| --- | --- | --- |
| 🟡 Needs polish | Getting started | `ui/src/components/welcome.tsx`, `ui/app/src/main.rs` (`watching`) |

The first time the main window opens, a few steps introduce Proki and check that it can see what you do.

## How it works
- Each step is a sticker, a title and a line, with Back and Next.
- It checks that ActivityWatch is recording: its window and away watchers both have buckets.
  The launcher installs ActivityWatch first if it's nowhere on the computer.
- It offers ActivityWatch's browser extension, for the pages you visit.
- The AI step opens Settings ([F-015](F-015-ai-services.md)); Later still finishes the welcome.
- Once you finish, it isn't shown again. Settings shows it again on request.

## Limits
- The check sees that a watcher registered, not that it still sends events.
- Input counts need the OS's permission, which the welcome explains but can't grant.
- Not yet tried end to end on an installed Windows build ([NF-005](NF-005-platforms.md)).
