# NF-005 Platforms

| Status | Area | Code |
| --- | --- | --- |
| 🟡 Needs polish | Everything | `proki/platforms/` (the only OS-specific Python) |

macOS (Apple silicon) is tested; Windows is built but not yet tried on a real machine; Linux
runs from source only.

## How it works
- Each OS module gives the same things: start at login, where ActivityWatch and NATS usually
  are, its browsers, lock-screen and system apps, lock the screen, close a tab or a window.
- On Windows, Proki's own window (`proki.exe`) is ignored like any system app.
- The media library's Windows folder is in the app's asset scope, so popups can show it.

## Limits
- Windows needs a test on a real machine: animated media in WebView2, the full welcome.
- Live Nebius and Nemotron requests haven't been tried.
