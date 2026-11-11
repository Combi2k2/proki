# Proki's docs

One short file per feature (`F-NNN`) and per concern that runs across them (`NF-NNN`). Each reads in
a minute. Older plans and audits are in git history, before the commit that added this file.

## Features

| ID | Feature | Status |
| --- | --- | --- |
| [F-001](F-001-welcome.md) | Welcome | 🟡 |
| [F-002](F-002-tray-and-pause.md) | Tray panel and pause | ✅ |
| [F-003](F-003-today.md) | Today | ✅ |
| [F-004](F-004-focus-sessions.md) | Focus sessions | ✅ |
| [F-005](F-005-popups.md) | Popups | 🟡 |
| [F-006](F-006-tasks.md) | Tasks and plans | ✅ |
| [F-007](F-007-notes.md) | Notes | ✅ |
| [F-008](F-008-media.md) | Media | ✅ |
| [F-009](F-009-apps.md) | Apps and labels | ⚪ |
| [F-010](F-010-metrics.md) | Metrics | 🟡 |
| [F-011](F-011-automations.md) | Automations | ✅ |
| [F-012](F-012-signals.md) | Signals and formulas | ✅ |
| [F-013](F-013-tables.md) | Tables | ✅ |
| [F-014](F-014-help.md) | Help and playground | ✅ |
| [F-015](F-015-ai-services.md) | AI services (LLM, Jev) | ✅ |
| [F-016](F-016-mcp.md) | MCP tools | ✅ |
| [F-017](F-017-support.md) | Support | 🟡 |
| F-018 | Import and export automations | 📌 |
| F-019 | Media packs | 📌 |
| F-020 | A catalog of shared packs | 🔍 |
| F-021 | Accounts: your own key, or Proki's services | 🔍 |
| F-022 | Your data on another device | 🔍 |

## Across features

| ID | Concern | Status |
| --- | --- | --- |
| [NF-001](NF-001-architecture.md) | Architecture | ✅ |
| [NF-002](NF-002-privacy.md) | Privacy and local data | ✅ |
| [NF-003](NF-003-security.md) | Security | ✅ |
| [NF-004](NF-004-release.md) | Installers and releases | 🟡 |
| [NF-005](NF-005-platforms.md) | Platforms | 🟡 |
| [NF-006](NF-006-ports.md) | Local ports | ✅ |
| [NF-007](NF-007-ui-audit.md) | UI audit: the checklist and each screen's flow | 📌 |

*✅ ready · 🟡 needs polish · ⚪ not reviewed · 📌 planned · 🔍 exploring.* A planned or
exploring item gets its file once its approach is settled.

## The format

```markdown
# F-NNN Name

| Status | Area | Code |
| --- | --- | --- |
| ✅ Ready | where it sits in the app | the main files |

What it gives you, in one or two sentences.

## How it works
- at most six points, each one line or two

## Limits
- what it doesn't do yet, or what to know
```

Keep a file under about 40 lines. Status uses the legend above and matches the README's.
A change to a feature updates its file in the same commit.
