// A stand-in for the app, in a browser (`npm run serve`): each page loads made-up rows, so it can
// be seen and tried without the engine. Only in development; the app's own build never has it.

import type { Board, Reference, Today } from "@/lib/proki"

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString()
const day = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString()

const board: Board = {
  groups: [
    { id: 1, name: "Finish the thesis draft", desc: "Chapters 3 and 4, ready for review", questions: [], tags: ["study"], estimate: 420,
      deadline: day(5), status: "open", created_at: ago(9000), updated_at: ago(60) },
    { id: 2, name: "Renew the visa", desc: "", questions: ["Which documents does the office still need?"], tags: ["papers"], estimate: 90,
      deadline: day(12), status: "open", created_at: ago(5000), updated_at: ago(600) },
    { id: 3, name: "Errands", desc: "", questions: [], tags: ["home"], estimate: 40, deadline: null, status: "open",
      created_at: ago(3000), updated_at: ago(30) },
  ],
  tasks: [
    { id: 1, group: 1, name: "Write the intro", key: "write-the-intro", desc: "", done_when: ["2 pages"], after: [], checkpoint: false, note: "",
      estimate: 40, deadline: null, status: "open", created_at: ago(9000), updated_at: ago(60) },
    { id: 2, group: 1, name: "Fix the figures", key: "fix-the-figures", desc: "", done_when: [], after: [1], checkpoint: false, note: "",
      estimate: 30, deadline: null, status: "open", created_at: ago(9000), updated_at: ago(60) },
    { id: 3, group: 1, name: "Outline chapter 4", key: "outline-chapter-4", desc: "", done_when: [], after: [], checkpoint: false, note: "",
      estimate: 25, deadline: null, status: "done", created_at: ago(9000), updated_at: ago(60) },
    { id: 4, group: 2, name: "Book an appointment", key: "book-an-appointment", desc: "", done_when: [], after: [], checkpoint: false, note: "",
      estimate: 15, deadline: day(3), status: "open", created_at: ago(5000), updated_at: ago(600) },
    { id: 5, group: 3, name: "Buy milk", key: "buy-milk", desc: "", done_when: [], after: [], checkpoint: false, note: "",
      estimate: 10, deadline: null, status: "open", created_at: ago(3000), updated_at: ago(30) },
  ],
  ops: [
    { id: 1, group: 1, op: "add", task: null, fields: { name: "Ask Anna to proofread", estimate: 10 }, after: ["write-the-intro"] },
    { id: 2, group: 1, op: "change", task: "write-the-intro", fields: { estimate: 60, done_when: ["2 pages", "Anna has read it"] }, after: null },
    { id: 3, group: 1, op: "remove", task: "fix-the-figures", fields: {}, after: null },
  ],
  rows: { study: ["study", "work"], papers: ["papers"], home: ["home", "errands"] },
}

const today: Today = {
  focus: 0.72, deep_minutes: 214, shallow_minutes: 61, active_minutes: 312, in_session: false, tasks_open: 4,
  day: {
    samples: Array.from({ length: 70 }, (_, i) => Math.min(1, Math.max(0, (i % 7 < 4 ? 0.68 : 0.3) + Math.sin(i * 1.7) * 0.18))),
    every: 5, lines: [0.35, 0.5], goal: 240, focused: 185, week: 1210, streak: 3,
  },
  next: { task: board.tasks[0], group: board.groups[0], deadline: day(5) },
  after: [{ task: board.tasks[3], group: board.groups[1] }, { task: board.tasks[4], group: board.groups[2] }],
}

const program = (name: string, title: string, icon: string, desc: string, on: boolean, state: string, tags: string[]) =>
  ({ name, title, desc, icon, on, state, states: ["idle", state], kind: "config" as const, tags })

const reference: Reference = {
  inputs: [], signals: [], rules: [],
  variables: [
    { name: "focus_goal", desc: "minutes of focused work you aim for each day", type: "number", value: 240, persist: false, scope: "global", from: "config" },
    { name: "session.active", desc: "whether a focus session is on", type: "boolean", value: true, persist: false, scope: "global", from: "config" },
    { name: "away", desc: "whether you've stepped away", type: "boolean", value: false, persist: false, scope: "global", from: "config" },
    { name: "trip", desc: "the trip you're planning", type: "any", value: { city: "Hanoi", nights: 3, booked: false, stops: ["Hue"] }, persist: false, scope: "global", from: "config" },
    { name: "streak", desc: "days in a row with a session", type: "number", value: 12, persist: false, scope: "global", from: "code" },
    { name: "work.tasks", desc: "every task, by its group then its place", type: "any", persist: false, scope: "global", from: "code",
      value: [{ name: "Write the intro", estimate: 40, done_when: ["2 pages"], spent: 12 }, { name: "Fix the figures", estimate: 25, done_when: [], spent: 0 }] },
    { name: "work.task", desc: "a task on your board", value: null, persist: false, scope: "global", from: "code",
      fields: [{ name: "work.task.name", desc: "", type: "string", value: "Write the intro", persist: false },
               { name: "work.task.score", desc: "", type: "number", value: 0.82, persist: false },
               { name: "work.task.done_when", desc: "", type: "any", value: ["2 pages", "Anna has read it"], persist: false }] },
  ] as Reference["variables"],
  functions: [{ name: "len", call: "len(xs)", about: "how many items a list has" }],
  actions: [{ name: "set", params: ["name", "expr", "when"], about: "set a variable to an expression's value", example: null }],
  programs: [
    program("morning", "Morning start", "sunrise", "Plans your day with you each morning", true, "idle", ["day"]),
    program("pomodoro", "Focus sessions", "timer", "Focus sessions with short breaks in between", true, "working", ["focus"]),
    program("bedtime", "Bedtime", "bed-double", "Reminds you to wind down at night", true, "idle", ["day"]),
    program("budget", "Busywork check", "hourglass", "Keeps an eye on time spent on small things", true, "counting", ["focus"]),
    program("task_reminder", "Task reminders", "bell", "Nudges you about tasks that are due or stuck", true, "idle", ["tasks"]),
    program("note_sorter", "Note sorter", "notebook-pen", "Sorts your notes into todos, ideas and thoughts", true, "idle", ["notes"]),
    program("call_family", "", "", "Reminds you to call home on Sundays", false, "idle", ["life"]),
  ],
}

const notes = {
  Unsorted: [{ id: 1, text: "Look into a standing desk", at: ago(40), guess: "Idea", conf: 0.7, sorts_at: day(0.4) }],
  Todo: [{ id: 2, text: "Email the landlord about the heater", at: ago(300), due: day(1) }],
  Idea: [{ id: 3, text: "A weekly review that writes itself", at: ago(2000) }],
  Thought: [{ id: 4, text: "Mornings go better after a walk", at: ago(4000) }],
}

let outbox = 0  // the suggestions waiting
const smoke = {  // the playground's, as proki/assets/smoke.json has them (made up the same way)
  a: Array.from({ length: 120 }, (_, i) => Math.round(Math.min(1, Math.max(0, 0.55 + 0.3 * Math.sin(i / 14) + 0.12 * Math.sin(i / 3.1))) * 100) / 100),
  b: Array.from({ length: 120 }, (_, i) => (i >= 70 && i < 78 ? null : Math.max(0, Math.round(35 + 30 * Math.sin(i / 9) + 9 * Math.sin(i * 1.7))))),
}
const played: Record<string, { desc: string; value: unknown }> = {
  goal: { desc: "minutes of focus you aim for a day", value: 240 }, streak: { desc: "days in a row you reached it", value: 3 },
  xs: { desc: "a list of numbers", value: [4, 8, 15, 16, 23, 42] }, mood: { desc: "a text", value: "calm" },
  task: { desc: "a record: one task", value: { id: 2, name: "Write the intro", estimate: 40, done: false } },
  tasks: { desc: "records: a list of tasks, each with its id", value: [{ id: 1, name: "Outline the thesis", estimate: 25, done: true }, { id: 2, name: "Write the intro", estimate: 40, done: false }, { id: 3, name: "Ask Anna to proofread", estimate: 10, done: false }] },
}
/** What the engine's operators give, a minute at a time, for `op(a, w)`; else the expression's length, held. */
function operated(expr: string): unknown[] {
  const m = /^(\w+)\((a|b), (\d+)\)$/.exec(expr)
  if (!m) return smoke.a.map(() => expr.length)
  const [, op, of, w] = m, xs = smoke[of as "a" | "b"], n = Number(w)
  const known = (from: number, to: number) => xs.slice(Math.max(0, from), to + 1).filter((v): v is number => v !== null)
  return xs.map((_, t) => {
    if (op === "delay") return t - n >= 0 ? xs[t - n] : null
    if (op === "every") { const end = Math.floor(t / n) * n, k = known(end - n, end - 1); return end - n < 0 || !k.length ? null : k.reduce((a, b) => a + b, 0) / k.length }
    const k = known(t - n + 1, t)
    if (op === "ts_count") return k.filter((v, i) => i && v !== k[i - 1]).length
    if (!k.length) return null
    return op === "ts_mean" ? k.reduce((a, b) => a + b, 0) / k.length : op === "ts_sum" ? k.reduce((a, b) => a + b, 0) : op === "ts_min" ? Math.min(...k) : Math.max(...k)
  })
}
const tools: Record<string, (args: Record<string, unknown>) => unknown> = {
  playground: ({ expr, action, variables }) => {
    const vars = Object.fromEntries(Object.entries(played).map(([k, v]) => [k, { ...v, value: (variables as Record<string, unknown> | undefined)?.[k] ?? v.value }]))
    if (action) {  // set, of a place: its value as JSON (true, 3, 'text')
      const [kind, params] = Object.entries(action as Record<string, { name: string; expr: string }>)[0]
      if (kind !== "set") return { error: `the preview only sets (${kind})` }
      const steps = params.name.match(/\w+|\d+/g)!, value = JSON.parse(params.expr.replace(/'/g, '"').replace(/^True$/, "true").replace(/^False$/, "false").replace(/^a > 0.5$/, "true"))
      const whole = structuredClone(vars[steps[0]].value) as Record<string, unknown>
      let at = whole
      for (const k of steps.slice(1, -1)) at = at[k] as Record<string, unknown>
      if (steps.length > 1) at[steps.at(-1)!] = value
      vars[steps[0]] = { ...vars[steps[0]], value: steps.length > 1 ? whole : value }
    }
    const values = expr ? operated(String(expr)) : undefined
    return { start: "09:00", signals: { a: { desc: "how focused you were, minute by minute (0 to 1)", values: smoke.a }, b: { desc: "key presses a minute (unknown while you were away)", values: smoke.b } },
             variables: vars, ...(values ? { values, type: "number" } : {}) }
  },
  suggest: () => ({ waiting: navigator.onLine ? 0 : ++outbox }),
  send_suggestions: () => ({ waiting: (outbox = navigator.onLine ? 0 : outbox) }),
  reference: () => reference,
  apply_changes: () => [],
  set_value: () => ({}),
  evaluate: ({ expr, smoke }) => {
    if (!smoke) return { value: String(expr).length, type: "integer" }
    const made = (smoke as { values: number[] }).values.map(Number), mean = (i: number) => made.slice(Math.max(0, i - 4), i + 1).reduce((a, b) => a + b, 0) / Math.min(5, i + 1)
    return String(expr).includes(">") ? { values: made.map((_, i) => mean(i) > 5), type: "boolean" } : { values: made.map((_, i) => mean(i)), type: "number" }  // as a 5-minute mean would
  },
  switch_program: ({ name, on }) => {
    const found = reference.programs.find((p) => p.name === name)
    if (found) found.on = Boolean(on)
    return { ok: true }
  },
  program_specs: ({ name }) => ({ default: true, changed: false, signals: [], rules: [], inputs: [],
                                  variables: [{ name: "trip", desc: "the trip you're planning", value: null, scope: "global",
                                                            type: { type: "object", properties: { city: { type: "string", description: "where to" },
                                                                    nights: { type: "integer" }, booked: { type: "boolean" }, stops: { type: "array", items: { type: "object", properties: { at: { type: "string", description: "the town" }, by: { type: "string", enum: ["bus", "train", "car"], description: "how you get there" } } } }, tags: { type: "array", items: { type: "string", enum: ["beach", "city", "food", "hiking", "museums", "nightlife", "family"] }, description: "what it is about" } }, required: ["city"] } }],
                                  ...(name ? { program: { name, desc: "", tags: [], initial: "idle" }, actions: [
                                                 { id: "a1", program: name, state: "working", name: "poke", desc: "tells you it's started", kind: "poke", params: { text: "'Focus'" } },
                                                 { id: "a2", program: name, state: "working", name: "set", desc: "", kind: "set", params: { name: "session.active", expr: "true" } },
                                                 { id: "a3", program: name, state: "working", name: "ask_llm", desc: "what you're on", kind: "ask_llm", params: { prompt: "'What now?'" } }],
                                               states: [{ name: "idle", desc: "", every: 1 }, { name: "working", desc: "", every: 1 }],
                                               branches: [{ program: name, state: "idle", goto: "working", when: ["focus > 0.5", "not away", "low_focus"], desc: "you've started" },
                                                          { program: name, state: "idle", goto: "working", when: ["ts_max(active, 7) == 0 and session.minutes > 25"], desc: "no activity for about 10 minutes, well into a session" },
                                                          { program: name, state: "working", goto: "idle", when: [], desc: "" }] } : {}) }),
  get_program: ({ name }) => {
    const found = reference.programs.find((p) => p.name === name)
    return found && { ...found, initial: "idle", waking: new Date(Date.now() + 185_000).toISOString(), vars: [], uses: { inputs: [], signals: [], variables: [], rules: [] },
                      states: [{ name: "idle", desc: "waits for its moment", every: 1, do: [], next: [{ goto: "working", conds: [{ expr: "focus > 0.5", value: true }, { expr: "not away", value: false }], desc: "you've started",
                                     rules: [{ name: "low_focus", desc: "focus over the last 2 minutes is low", lhs: "focus_2m", cmp: "lt", rhs: "0.4", softness: 0.1, level: 2, chance: 0.8 }] },
                                   { goto: "working", conds: [{ expr: "ts_max(active, 7) == 0 and session.minutes > 25", value: false }], rules: [], desc: "no activity for about 10 minutes, well into a session" }] },
                               { name: "working", desc: "while you work", every: 1, do: [], next: [{ goto: "idle", conds: [], rules: [], desc: "" }] }] }
  },
  get_settings: () => ({
    services: {
      llm: { provider: "openrouter", url: "https://openrouter.ai/api/v1", model: "google/gemini-3.5-flash-lite" },
      jev: null,
    },
    providers: {
      llm: {
        openai:     { name: "OpenAI", url: "https://api.openai.com/v1", key: false },
        anthropic:  { name: "Anthropic", url: "https://api.anthropic.com/v1", key: false },
        google:     { name: "Google", url: "https://generativelanguage.googleapis.com/v1beta/openai", key: false },
        openrouter: { name: "OpenRouter", url: "https://openrouter.ai/api/v1", key: true },
        custom:     { name: "Custom", url: "", key: false },
      },
      jev: {
        openrouter: { name: "OpenRouter", url: "https://openrouter.ai/api/alpha/decisions", key: false },
        openjev:    { name: "openjev", url: "https://api.openjev.sh/v1/systemone", key: false, models: ["systemone"] },
        custom:     { name: "Custom", url: "", key: false, models: [] },
      },
    },
  }),
  get_media: ({ kind }) => {
    const media = media_.filter((m) => !kind || m.kind === kind)
    return { media, total: media.length }
  },
}

const media_ = [
  ["yours/1a", "stickers/happy", "image", "you"], ["yours/2b", "stickers/cats/sleepy", "image", "you"], ["yours/3c", "gong", "sound", "you"],
  ["bugcat/angry", "bugcat/angry", "image", "dev"], ["bugcat/bat", "bugcat/bat", "image", "dev"], ["alarm-clock", "alarm-clock", "sound", "dev"],
].map(([key, name, kind, added_by]) => ({ key, name, kind, added_by, file: "" }))

if (import.meta.env.DEV && !("__TAURI_INTERNALS__" in window)) {
  const answer = <T,>(value: T) => Promise.resolve(value as never)
  window.proki = {
    onShow: () => {},
    answer: () => {},
    resize: () => {},
    tasks: () => answer({ ...board, id: 1 }),
    notes: () => answer({ ...notes, id: 1 }),
    fields: (request: { record?: string }) => {
      const at = Math.floor(Date.now() / 60_000), field = (key: string, type: string, desc = "") => ({ key, desc, srcs: [{ from: "user" as const }], type, worked: type, shipped: true, setters: [] })
      return answer(request.record === "work.groups"
        ? { records: ["work.groups", "work.tasks"], fields: [field("name", "string"), field("deadline", "time"), field("open", "boolean")], own: ["id", "created_at", "updated_at"], contexts: { jev: "", llm: "" }, rows: [
            { id: 3, name: "Finish the thesis draft", values: { id: 3, name: "Finish the thesis draft", deadline: at + 7200, open: true, created_at: at - 20_000, updated_at: at - 60 } },
            { id: 4, name: "Renew the visa", values: { id: 4, name: "Renew the visa", deadline: null, open: false, created_at: at - 9_000, updated_at: at - 900 } },
          ] }
        : { records: ["work.groups", "work.tasks"], fields: [field("name", "string", "what it is"), field("estimate", "number", "minutes it takes"), field("done_when", "list[string]")], own: ["id", "created_at", "updated_at", "score", "after"],
            contexts: { jev: "", llm: "" }, rows: [
            { id: 1, name: "Write the intro", values: { id: 1, name: "Write the intro", estimate: 40, done_when: ["2 pages"], score: 0.82, after: [], created_at: at - 3000, updated_at: at - 30 } },
            { id: 2, name: "Ask Anna to proofread", values: { id: 2, name: "Ask Anna to proofread", estimate: 10, done_when: [], score: 0.4, after: [1], created_at: at - 2000, updated_at: at - 200 } },
          ] })
    },
    apps: () => answer({ apps: [], labels: [] }),
    today: () => answer({ ...today, focus: (today.focus = Math.min(0.95, Math.max(0.05, (today.focus ?? 0.5) + (Math.random() - 0.5) * 0.2))) }),
    metrics: () => answer({ metrics: [{ name: "focus", desc: "how focused you were", expr: "focus", pace: 300, persist: true, on: true, keep: null, method: "mean" }],
                            size: 86400, method: "mean", buckets: [0.42, 0.61, 0.55, 0.7, 0.38, 0.66, 0.58].map((v, i) => [new Date(Date.now() - (6 - i) * 86_400_000).toISOString(), v]) }),
    tool: (name, args = {}) => answer(tools[name] ? tools[name](args as Record<string, unknown>) : { error: `no ${name} in the preview` }),
    pickFiles: () => Promise.resolve([]),
    pickFolder: () => Promise.resolve(null),
    onDrop: () => Promise.resolve(() => {}),
    fileUrl: (path) => path,
    note: () => console.log("[preview] new note"),
    link: (to) => console.log("[preview] open", to),
    session: (op) => { today.in_session = op === "start" },
    onNavigate: () => {},
  }
}
