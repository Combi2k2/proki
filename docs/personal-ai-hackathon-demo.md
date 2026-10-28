# Proki — a personal AI that leaves the day yours

## Demo in one sentence

An agent helps choose the next piece of work from your calendar and Proki tasks; Proki then protects the time, while the user stays in control of every change.

**Length:** about 3½ minutes  
**Story:** one person, one deadline, one focused work block.  
**Style:** calm, precise, human. Let the product carry the story. Use a clean desktop capture, restrained music, and a few purposeful transitions. Avoid a feature tour.

## What is real, and what the demo needs

Already in Proki: local app and website tracking through ActivityWatch, focus sessions, task and idea boards, prompts such as the in-session email/chat reminder, configurable programs, and an MCP server with a local bearer token. The codebase also has an OpenAI-compatible LLM service.

Demo integration to prepare: connect an agent such as Hermes to Proki's MCP server and a **read-only calendar MCP**; add a reusable `prepare-focus-block` skill; configure the agent to ask before any write. Proki does not currently ship this agent panel, calendar connector, or agent approval flow, so show them as a separate connected assistant unless you build that UI first.

Use **NVIDIA Nemotron 3.5 Lightning** as the agent model, served through Nebius Token Factory's OpenAI-compatible endpoint. Nemotron is an NVIDIA open model; Nebius currently lists this model on its public inference endpoint. The model request is hosted: Proki's monitoring and task history stay on the computer, but the calendar and task details selected for the agent are sent to the chosen inference provider. Say that plainly in the demo. [NVIDIA model page](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b), [Nebius Nemotron inference](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference)

Hermes supports MCP servers and per-server tool filtering, which fits the read-only calendar plus narrowly scoped Proki tool setup. [Hermes MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)

**OpenShell/NemoClaw is an optional stretch for this demo.** Proki's MCP endpoint currently binds to `127.0.0.1`; an isolated agent sandbox will need a deliberate, tested path to that host service. Don't claim the agent is sandboxed unless that path is working. NemoClaw's current primary tested platforms are Linux and DGX Spark, so rehearse on the actual judging machine. [NemoClaw overview](https://docs.nvidia.com/nemoclaw/latest/about/overview.html)

## Set the scene

It is 10:12. The user has a call at 11:00 and a launch brief to finish. The calendar already contains the call. Proki has a `Launch` task group with a few real-looking open tasks. The user's ActivityWatch setup is running and has classified email/chat as shallow work.

The agent's `prepare-focus-block` skill says: check the next calendar event; read Proki groups and tasks; recommend one next step that fits the available time; do not write until approved; only use the connected calendar and Proki tools. For this take, allow `read_records`, `add_record`, and `change_record` on Proki, and read-only calendar tools. Keep destructive tools hidden.

## Timed script

### 0:00–0:20 — The day is already moving

**Picture:** Quiet desktop. Proki's Today page shows focus and the next task. A small clock reads 10:12. No dashboards or title cards yet.

**Voiceover:** “A personal assistant should understand the shape of your day—and help with the next thing that matters.”

**Transition:** The clock ticks once. The assistant opens beside Proki; keep both windows visible so the relationship is clear.

### 0:20–0:55 — Ask for help in plain language

**On screen, user types:**

> I have a call at 11. Check my calendar and Proki tasks. What is one useful thing I can finish before then? Don't change anything yet.

**Action:** Hermes uses the Calendar MCP to read the next event and Proki MCP `read_records` for `work.groups` and `work.tasks`. Briefly show the two tool names and their read-only results. Show the selected model label: **Nemotron 3.5 Lightning · Nebius**.

**Agent says:** “You have about 40 minutes before your call. The launch brief is open. A useful next step is to draft its opening paragraph.”

**Voiceover:** “The agent brings together only the tools you connected.”

**Transition:** The suggested next step becomes a simple review card. No spinning brain animation; keep the result legible.

### 0:55–1:25 — The user approves one change

**Agent says:** “I can add ‘Draft the opening paragraph’ to Launch, estimated at 25 minutes. Add it?”

**Action:** User selects **Add task**. Hermes calls Proki MCP `add_record` with the existing Launch group ID, task name, short description, and estimate. Show the returned task in Proki's task board.

**Voiceover:** “The agent proposes. You decide. The task is kept in Proki, not buried in chat.”

**Transition:** Match-cut the task card into Proki's Today page. The agent window recedes; Proki becomes the main view.

### 1:25–1:55 — Start the work

**Action:** User starts a focus session from Today. When Proki asks what they are working on, type “Draft the opening paragraph” and confirm the matching Launch task if prompted. Show the running session and selected task.

**Voiceover:** “Now Proki takes over the part it is built for: keeping the work visible and the session moving.”

**Transition:** Let the session timer settle. Cut to the email app and hold for the real reminder trigger; don't fake a notification.

### 1:55–2:35 — A gentle interruption, at the right moment

**Action:** After email or chat remains in focus long enough for Proki's existing Inbox Guard to trigger, show its prompt:

> Email, chat and calls can wait until the session is over.

User chooses **OK** and returns to the brief. The other choice, **Stop session**, remains visible so the user can end the session if priorities changed.

**Voiceover:** “It doesn't lock the door. It gives you a moment to choose.”

**Transition:** Close the prompt. Return to the task and focus session. Let the music resolve, not swell.

### 2:35–3:15 — The useful context persists

**Action:** Show the task still in Proki's board, then the Today page with the active session. Open a small “Connected tools” detail in the agent view showing Calendar as read-only and Proki tasks as the only writable service. If no such UI exists yet, use a simple demo overlay; label it **Demo integration**.

**Voiceover:** “Proki keeps the task and your work history on this computer. The agent only sees what you chose to connect. And when it wants to change something, it asks first.”

**On-screen text, one phrase at a time:**

- Your work stays in Proki.
- Your tools are your choice.
- Every change is yours to approve.

### 3:15–3:30 — Close

**Picture:** Proki Today page, calm and uncluttered. The task is visible beside the session state.

**Voiceover:** “Proki. A little more room for the work that matters.”

Fade to the Proki mark and the line: **Your day, still yours.**

## Rehearsal checklist

- [ ] Seed a Launch group, several believable tasks, and a calendar event at 11:00.
- [ ] Connect Hermes to Proki's MCP endpoint and the read-only calendar MCP.
- [ ] Add and rehearse the `prepare-focus-block` skill; make its approval prompt explicit before `add_record` or `change_record`.
- [ ] Configure and verify Nemotron 3.5 Lightning through Nebius Token Factory; show the real model name in the agent UI.
- [ ] Run ActivityWatch and the browser extension; confirm email/chat is classified so Inbox Guard triggers during the take.
- [ ] Rehearse the 15-second email/chat trigger and the task-picker prompt; reset Proki state between takes.
- [ ] Keep a recorded backup of the same real run in case a live service stalls. Never fake tool results as live.
- [ ] If using OpenShell/NemoClaw, verify the sandbox can reach only the intended MCP endpoint and model route before recording.

## Demo guardrails

- Call the agent, Calendar MCP, approval card, and focus-prep skill **demo integrations** until they are implemented and tested.
- Say “local” about Proki's activity history and task store; don't imply the hosted model sees no data. The prompt includes the selected calendar/task context.
- Keep the calendar read-only. Let the agent make one small Proki change after explicit approval.
- Don't use a long feature list, a synthetic “AI is thinking” animation, or a fake instant focus insight. One believable workflow is stronger.

## Product references

- Proki's existing surface and privacy description: [README](../README.md)
- MCP server and local bearer-token behavior: [tools/server.py](../proki/tools/server.py)
- Current task tools: [tools/records.py](../proki/tools/records.py)
- Existing session reminder: [hub.json](../proki/programs/config/hub.json)
- Existing session and task selection flows: [pomodoro.json](../proki/programs/config/pomodoro.json), [task_picker.json](../proki/programs/config/task_picker.json)
