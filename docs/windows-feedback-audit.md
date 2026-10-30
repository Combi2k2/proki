# Windows installer feedback audit

Reviewed 2026-10-29. Scope: media loading, ActivityWatch setup, app classification,
and the LLM requests involved in the reported feedback.

## Findings and changes

| Priority | Finding | Change |
| --- | --- | --- |
| High | The webview allowed `$DATA/proki/media`, while Python's Windows data directory is `%LOCALAPPDATA%/proki/proki/media`. Onboarding images use bundled URLs and bypass this problem. | Add the Windows library directory to the asset scope. Both Media and pop-ups use the same file URL bridge. |
| High | Launcher discovery required the input watcher in the main ActivityWatch installation, but the standard distribution omits it. Reinstalling the same archive could never satisfy discovery. Without input events, `active` stays unknown and classification cannot accumulate dwell time. | Freeze the official input watcher separately, include it in the installer resources, and supervise it independently of the server. Recover Proki-owned watcher processes; leave recently reporting external watchers alone. |
| High | Tracking could observe inputs before their refresh and then use the previous program clock during a new stream cycle. | Declare tracking's input dependencies and use the stream cycle clock consistently for observation and dwell. |
| Medium | Windows reports Proki as `proki.exe`, which was missing from the ignored app names. | Ignore release and development executable names on Windows as well. |
| Medium | Onboarding's readiness check tested only whether port 5600 accepted a connection. | Require window, AFK and input recording buckets; explain input collection in the existing setup step. |
| Medium | The LLM envelope used the name `answer`, rather than the requested `reasoning_schema`. | Send `{name: "reasoning_schema", strict: true, schema: ...}` inside `response_format.json_schema`. Preserve the supplied schema and the existing fallback for services that reject structured output. Add Nebius as a selectable provider. |
| Medium | Nemotron requests had no instruction to reduce reasoning. | Prepend a Nemotron-specific system instruction to think less, keep reasoning brief, and produce useful, concrete results in the requested format. Other models retain their prompts. |
| Medium | The pinned input watcher's newer AFK listener counts key-downs, while Proki expects the historical down-plus-up counts. | Adapt counts at the bundled watcher boundary, preserving existing input-rate interpretation. |

The [official ActivityWatch downloads page](https://activitywatch.net/downloads/)
lists the preinstalled watchers. The bundled input watcher and AFK listener sources
are pinned to commits in `packaging/build.sh`; they build in a separate environment
because their `platformdirs` requirement conflicts with the engine's.

## Verification and remaining limits

Regression coverage includes tracking across cycle boundaries, the one-minute
new-app eligibility condition, Windows self-window exclusion, the schema envelope,
Nemotron prompting, watcher discovery and ownership, restart handling, and key-count
compatibility. The Python suite, frontend build, TypeScript check, and Rust check
were run. The standalone watcher was frozen and its help command executed on macOS.
Installer builds now run that command as a smoke check on their own platform.

A Windows machine is still needed to confirm animated media in WebView2 and the
complete installed onboarding flow. No Windows installer was built here. Onboarding
bucket checks establish that each source has registered; they do not establish that
each bucket is still receiving fresh events. Actual OS input permissions remain
necessary. A new app's depth remains unknown until a label or a sufficiently similar
label exists; it is not assigned an invented default.

No live Nebius/Nemotron requests were made. Prompt wording is regression-tested,
but latency and answer quality need comparison against real requests. This is a
focused audit of the reported paths, not a claim that every module has been audited.
