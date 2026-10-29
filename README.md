<p align="center">
  <img src="cover.png" alt="Proki — a focus companion for planning, focus sessions, and ideas" width="960" />
</p>

<h1 align="center">Make room for the work that matters.</h1>

<p align="center">
  Proki helps you see where your time goes, decide what to do next, and return to the work when your attention wanders.
</p>

<p align="center">
  <a href="https://github.com/Combi2k2/proki/stargazers"><img src="https://img.shields.io/github/stars/Combi2k2/proki?style=flat&label=GitHub%20stars" alt="GitHub stars" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Combi2k2/proki?style=flat" alt="MIT license" /></a>
  <img src="https://img.shields.io/badge/macOS-tested-2f855a?style=flat" alt="macOS tested" />
  <img src="https://img.shields.io/badge/status-early%20build-blue?style=flat" alt="Early build" />
</p>

<p align="center">
  <a href="#why-proki">Why Proki</a> &nbsp;·&nbsp;
  <a href="#what-you-can-do">What you can do</a> &nbsp;·&nbsp;
  <a href="#your-day-stays-yours">Privacy</a> &nbsp;·&nbsp;
  <a href="#try-proki">Try Proki</a> &nbsp;·&nbsp;
  <a href="#for-builders">For builders</a>
</p>

---

## Why Proki

Good intentions are easy to lose in a busy day. Proki is a focus companion that helps you make a plan, stay with a task, and keep useful thoughts from slipping away.

It offers gentle check-ins around your work, so you can make progress without turning productivity into another source of pressure. Your activity history stays on your computer, and you choose which apps and websites count toward your focus.

## What you can do

### Your day

| What you need | How Proki helps | Review |
| --- | --- | --- |
| Start well | A welcome the first time you open it: ActivityWatch checked (and installed for you), and your browser's extension a click away. | - [ ] Looks good<br>- [ ] Needs work |
| See today at a glance | **Today** shows your focus through the day, your daily goal and streak, your next task, a box for what's on your mind, and the routines at work. | - [ ] Looks good<br>- [ ] Needs work |
| Stay with a task | Start a focus session from Today or the tray, tied to a task; a gentle popup when you drift, need a break, or it's time for bed. | - [ ] Looks good<br>- [ ] Needs work |

### Your work

| What you need | How Proki helps | Review |
| --- | --- | --- |
| Make a plan | **Tasks** groups your todos under goals, with a clear next one; talk a todo through and Proki splits it into smaller ones. | - [ ] Looks good<br>- [ ] Needs work |
| Keep the thought | **Notes** catches an idea, a todo or a thought as it comes; Proki sorts it for you. | - [ ] Looks good<br>- [ ] Needs work |
| Something to smile at | **Media**: the stickers and pictures Proki's popups show, in folders, yours to add to. | - [ ] Looks good<br>- [ ] Needs work |

### Insight

| What you need | How Proki helps | Review |
| --- | --- | --- |
| Know where time goes | **Apps**: each app and website you use, and whether it counts as focus, a break or a distraction. You decide. | - [ ] Looks good<br>- [ ] Needs work |
| Watch the trend | **Metrics**: your focus and the signals behind it, over the day and the weeks. | - [ ] Looks good<br>- [ ] Needs work |

### Advanced

| What you need | How Proki helps | Review |
| --- | --- | --- |
| A routine that fits | **Automations**: every nudge and check-in is a routine you can read, switch off or change, and what each one uses is shown beside it. | - [ ] Looks good<br>- [ ] Needs work |
| Your own records | **Tables**: tasks, notes and lists of your own, with fields you add; some worked out for you by a rule or by AI. | - [ ] Looks good<br>- [ ] Needs work |
| Help from AI | Choose the AI service behind planning, sorting and the popups' words; its key stays on this computer. | - [ ] Looks good<br>- [ ] Needs work |
| Work with your assistant | Claude Code, Codex, OpenClaw and other assistants reach your tasks, notes and routines through `proki mcp` (see [For builders](#for-builders)). | - [ ] Looks good<br>- [ ] Needs work |

*As you try each feature, mark whether it feels ready or needs more polish.*

## Your day stays yours

Proki and ActivityWatch keep your activity history on your computer. Depending on your ActivityWatch setup, the activity it records may include app names, window titles, browser pages, and counts of keyboard and mouse activity. ActivityWatch’s input watcher records counts only, not the keys you press.

If you choose to connect an AI service, Proki sends it the information needed for that request. You choose the provider, and its service key stays on your computer, in a file only you can read.

## Try Proki

Proki is an early build, actively being shaped around real workdays. It has been tested on macOS (Apple silicon). The Windows installer is built the same way but has not been tested on a real machine yet, and Linux has no installer.

Download the latest installer from [Releases](https://github.com/Combi2k2/proki/releases). Everything Proki needs is inside it, except [ActivityWatch](https://activitywatch.net/), which records the windows you're in: if it isn't on your computer, Proki installs it for you the first time it starts. The welcome then offers ActivityWatch's extension for your browser (Chrome, Edge, Brave and other Chromium browsers, or Firefox).

**macOS:** open the `.dmg` and drag Proki to Applications. The app isn't signed yet, so macOS says it's damaged or can't be checked. Run this once, then open it as usual:

```bash
xattr -cr /Applications/proki.app
```

**Windows:** run the installer. The app isn't signed yet, so SmartScreen warns you: choose **More info**, then **Run anyway**.

<details>
<summary><strong>Run it from the source</strong></summary>

The current build requires [ActivityWatch](https://activitywatch.net/), [NATS](https://nats.io/), [uv](https://docs.astral.sh/uv/), and [Node.js](https://nodejs.org/). On macOS, install NATS with Homebrew, then run these commands from the project folder:

```bash
brew install nats-server
uv sync
cd ui && npm install && npm run app
cd ..
uv run launch.py
```

For website tracking, add ActivityWatch’s browser extension. Quit Proki or press `Ctrl-C` in the terminal to stop the app.

</details>

## For builders

Proki can connect to compatible AI assistants through a local, password-protected connection. An assistant can read or update tasks, routines, media, and settings. Only connect assistants you trust.

In the app, choose **Install command-line tool…** from the tray menu (from the source: `uv tool install -e .`). Then add Proki to an assistant as a command, `proki mcp`; it starts Proki if it isn't running:

```bash
claude mcp add proki -- proki mcp
codex mcp add proki -- proki mcp
openclaw mcp set proki '{"command":"proki","args":["mcp"]}'
```

An assistant started from the Dock may not find `proki`: give it the full path the tray menu shows.

To build the installers: `packaging/build.sh` on macOS or Windows (Git Bash), or run the **release** workflow on GitHub; a `v*` tag publishes them as a release.

Explore the [feature review](docs/F-002-feature-review.md), [product architecture notes](docs/components.md), and [demo script](docs/personal-ai-hackathon-demo.md).

## License

[MIT](LICENSE)
