// What the pages share: the bridge to the app (bridge.ts), the engine's rows (proki/serve.py), and page setup.

import "@/lib/bridge"
import "@/lib/preview"
import { createRoot } from "react-dom/client"
import type { ReactNode } from "react"
import "@/index.css"

export type Shown = {
  id: string | number
  text: string
  options: string[] | null  // null: a text to type. []: a poke, nothing to answer
  show: {
    urgent?: boolean
    immediate?: boolean  // to answer now: no "Later"
    text?: string   // what's typed already
    title?: string  // its heading
    media?: string  // a picture's file (the media library's, drawn)
    selected?: number  // the option picked already, in a list
    sound?: string  // a sound's file: it plays while it's shown
  }
}

/** The board (proki/programs/code/work.py): groups, a card each, of tasks. A
 * group's tags, the most relevant first: its first tag's row is where its card is. Times,
 * deadlines too, are ISO text. */
type Status = "open" | "done" | "dropped"

export type TaskGr = {
  id: number
  name: string
  desc: string
  questions: string[]  // open: only you can answer them
  tags: string[]  // "papers", "visa", the most likely first, 3 at most
  estimate: number | null  // minutes, all of it
  deadline: string | null
  status: Status
  created_at: string | null
  updated_at: string | null
}

export type Task = {
  id: number
  group: number
  name: string
  key: string  // its name slugified, one of its group's: how a suggested change says it
  desc: string
  done_when: string[]  // what "done" looks like: checks anyone could make
  after: number[]  // the tasks it needs done first, by their ids
  checkpoint: boolean  // a check it all works together, and what's next
  note: string
  estimate: number  // minutes
  deadline: string | null  // its own (else its group's)
  status: Status
  created_at: string | null
  updated_at: string | null
}

/** A change suggested to a group's tasks, for you to accept or not. */
export type TaskOp = {
  id: number
  group: number
  op: "add" | "change" | "remove"
  task: string | null  // change, remove: the task's key
  fields: Partial<Task>  // the task's fields it gives (add: its key too)
  after: string[] | null  // the tasks it needs done first, by their keys (null: as they are)
}

/** The board's rows, and each one's tags (assets/tags.json). */
export type Rows = Record<string, string[]>

export type Board = { groups: TaskGr[]; tasks: Task[]; ops: TaskOp[]; rows: Rows }

/** A field of yours: where its value comes from, in order, the first with a value giving it.
 * The weight's parts and its score are fields too. */
export type SourceName = "expr" | "jev" | "llm" | "user" | "auto"
/** What a value is: a name (number, integer, boolean, string, time, array, object, any), or a JSON Schema. */
export type Type = string | Record<string, unknown>
export type Source = {
  from: SourceName
  expr?: string                                    // a formula's; an ask's, on its answer as `res`
  type?: "noul" | "choice" | "score"              // jev's: as ask_jev asks
  question?: string                                // jev's
  criteria?: Record<string, string>                // a choice's: each label, and what it means
  context?: string                                 // the LLM's
  schema?: Type                                    // the LLM's: what it answers (none: its field's type)
  initial?: unknown                                // auto's: where a new task starts
  timeout?: number
}
export type Field = {
  key: string
  desc: string
  srcs: Source[]
  type: Type          // what its value is, as it says (any: it says none)
  worked: Type        // and as worked out: its type, else its sources' (an answer's, its formula's)
  shipped: boolean    // one proki came with: removing it brings it back as it came
  setters: string[]   // the programs that set it
}
/** A kind of record's fields (task, note, track), and its records with
 * their values (the task's: the ready ones, the weightiest first). */
export type Weighed = {
  record?: string
  records: string[]
  fields: Field[]
  own: string[]   // the record's own fields
  rows: { id: number | string; name: string; values: Record<string, unknown> }[]
  contexts: { jev: string; llm: string }   // what every question is read under
}

/** A note (notes, in main.json), in its bucket. */
export type Note = { id: number; text: string; at: string; due?: string | null; guess?: string | null; conf?: number | null; sorts_at?: string; link?: string | null }  // the rest: unsorted (sorts_at: when it's sorted); link: where it was dealt with, a page's path
export type Bucket = "Unsorted" | "Todo" | "Idea" | "Thought"

/** An app or a website classify knows (proki/programs/code/classify.py), and its label by
 * its id (null: none yet). source: "usr" (you), "dev" (shipped), "jev". */
export type App = { key: string; track: boolean | null; label: number | null; source: string; set_at: string; conf: number | null }
export type Depth = "deep" | "shallow" | "neutral" | "distraction"
export type Label = { id: number; name: string; desc: string; group: string; depth: Depth }

export type Today = {
  focus: number | null  // 0..1, now
  day: FocusDay
  deep_minutes: number | null  // the last 24 hours
  shallow_minutes: number | null
  active_minutes: number | null
  in_session: boolean
  tasks_open: number | null
  next: { task: Task; group: TaskGr; deadline: string | null } | null
  after: { task: Task; group: TaskGr }[]  // the ones after it, the weightiest first
}

/** Today's focus since midnight: its value each `every` minutes you were active, the lines
 * between its bands (low to high), the minutes focused as the day clock counts them, and the
 * minutes focused you aim for. */
export type FocusDay = {
  samples: number[]; every: number; lines: number[]; goal: number
  focused: number
  week: number | null    // minutes focused this week, from Monday
  streak: number | null  // days in a row the goal was reached, before today
}

/** A global signal, as a metric: persisted (its history saved, `keep` minutes of it), reported
 * or not, and how its buckets are made. */
export type Method = "mean" | "sum" | "min" | "max" | "last"
export type Horizon = "day" | "week" | "month" | "year"
export type Metric = { name: string; desc: string; expr: string; pace: number | null; persist: boolean; on: boolean; keep: number | null; method: Method }
export type Buckets = { size: number; method: Method; buckets: [string, number | null][] }

/** Where a variable or a rule is declared: its full name says (suggest.left: a program's).
 * Special: an object whose fields are variables of their own (track, work). */
export type Scope = "special" | "global" | "program" | "state"

/** What a program can use, with its value now (proki/editor.py: `reference`). Each input,
 * signal, variable, rule and program says what it's for (`desc`, "" if it doesn't); a signal or
 * a variable the app reads says so (`app`): it can't be removed, nor retyped. */
export type Reference = {
  inputs: (InputRow & { used: boolean })[]
  functions: { name: string; call: string; about: string }[]
  actions: { name: string; params: string[]; about: string; example: object | null }[]
  signals: (SignalRow & { scope: Scope; app: boolean })[]
  variables: (VarDetail & { scope: Scope; from: "config" | "code"; app?: boolean })[]  // none on the special ones
  rules: (RuleDetail & { scope: Scope })[]
  programs: { name: string; on: boolean; state: string; states: string[]; kind: "config" | "code"; title: string; desc: string; icon: string; tags: string[] }[]
}

/** A rule, as a branch reads it: its sides, how soft, its level, the chance of firing now. */
type RuleDetail = {
  name: string
  desc: string
  lhs: string
  cmp: "gt" | "ge" | "lt" | "le" | "eq" | "ne"
  rhs: string
  softness: number
  level: number
  chance: number | null
}

/** A variable: `persist`, kept across restarts. */
export type VarDetail = { name: string; desc: string; type?: Type; value: unknown; persist: boolean }

/** A signal: `backfill`, how many minutes of itself it keeps as a table, `persist`, saved. */
type SignalRow = { name: string; desc: string; expr: string; type?: Type; value: unknown; backfill: number | null; persist: boolean }

type InputRow = { name: string; desc: string; type?: Type; value: unknown }

/** What a program depends on (proki/editor.py: `uses`): the rules its ways out vote with,
 * the signals and variables it reads, down to the inputs. `sets`: its actions change it. */
type Uses = { rules: RuleDetail[]; signals: SignalRow[]; variables: (VarDetail & { sets: boolean })[]; inputs: InputRow[] }

/** One way out of a state: no conditions nor rules is the else. */
export type BranchDetail = { goto: string; desc: string; conds: { expr: string; value: unknown }[]; rules: RuleDetail[] }

/** A state, as its diagram shows it. It, its ways out, rules and variables each say what
 * they're for (`desc`, "" if they don't). */
type StateDetail = {
  name: string
  desc: string
  do: unknown[]  // its actions, as written ({"set": {...}}), or as made for a program in code
  every: number  // minutes between tries of `next`
  vars: VarDetail[]
  next: BranchDetail[]
}

/** A program, state by state, as its diagram shows it (proki/editor.py: `detail`). */
export type ProgramDetail = {
  name: string
  kind: "config" | "code"
  on: boolean  // off: the cycles leave it alone
  state: string
  initial: string
  title: string  // what the app calls it (empty: its name)
  desc: string  // what it's for, in a line
  icon: string  // its icon's name (empty: one its tags pick)
  tags: string[]
  waking: string | null  // when it next wakes up
  vars: VarDetail[]
  states: StateDetail[]  // as met from the initial one
  uses: Uses
}

/** The specs, as you write them (proki/model/specs.py). Names are short: found from where they are. */
type Scoped = { name: string; desc: string; scope: Scope; program: string | null; state: string | null }
export type VariableSpec = Scoped & { value: boolean | number | string | null; type?: Type }  // value, a text: an expression
/** A time: minutes, or a phrase ("6s", "5min", "1h", "1d"). */
type Span = number | string
export type SignalSpec = Scoped & { expr: string; backfill: Span | null; persist: boolean; type?: Type }
export type RuleSpec = Scoped & { lhs: string | number; cmp: RuleDetail["cmp"]; rhs: string | number; softness: number; level: number }
type InputSpec = { name: string; backfill: Span | null }
type ProgramSpec = { name: string; title?: string; desc: string; icon?: string; tags: string[]; initial: string }
export type StateSpec = { program: string; name: string; desc: string; every: Span }
export type BranchSpec = { program: string; state: string; goto: string; when: string[]; desc: string }
export type ActionSpec = { id: string; program: string; state: string; name: string; desc: string; kind: string; params: Record<string, unknown> }

/** What a part of your programs holds (proki/editor.py: `specs`): `default`, proki ships one
 * to go back to, `changed`, yours differs from it. */
type Part = { default: boolean; changed: boolean; variables: VariableSpec[]; signals: SignalSpec[]; rules: RuleSpec[] }
export type ProgramSpecs = Part & { program: ProgramSpec; states: StateSpec[]; branches: BranchSpec[]; actions: ActionSpec[] }
export type GlobalSpecs = Part & { inputs: InputSpec[] }

/** A change, as apply_changes takes it. */
export type Change = { op: "add" | "update" | "remove"; kind: string; data: object }

export type View = "today" | "tasks" | "notes" | "apps" | "metrics" | "programs" | "media" | "tables" | "manual" | "settings" | "contribute"

/** A picture or a sound of the media library (proki/services/media.py). `file`: its copy on disk. */
export type MediaItem = { key: string; name: string; kind: "image" | "sound"; file: string; added_by: "dev" | "you" }

type Answer<T> = T & { error?: string }

type Done = { ok: true }

/** The playground (proki/playground.py): its signals, a value a minute from `start` ("09:00"), its
 * variables, and an expression's values, one a minute, if one was given. */
export type Played = {
  start: string
  signals: Record<string, { desc: string; values: (number | null)[] }>
  variables: Record<string, { desc: string; type?: Type; value: unknown }>
  values?: unknown[]
  type?: Type
}

/** Your programs' tools (proki/tools.py), by name, and what each returns. */
type Tools = {
  reference: Reference
  get_program: ProgramDetail
  program_specs: ProgramSpecs & GlobalSpecs  // a program's, or the global scope's (name null)
  apply_changes: unknown[]
  remove_unused: unknown[]  // what nothing decides by, taken out
  reset_program: Done
  switch_program: Done
  set_value: Done  // a variable's value, set now, as an action would
  get_media: { media: MediaItem[]; total: number }
  add_media: { key?: string; keys?: string[] }  // a file's key, a folder's keys
  rename_media: Done  // its name, what you see: its key stays
  remove_media: { removed: string[]; kept: Record<string, string> }
  list_pools: Record<string, MediaItem[]>
  set_pool: Done
  get_picks: { media: MediaItem[] }  // a poke's or a question's pictures and sounds, by its action's id
  set_picks: Done
  playground: Played
  evaluate: { value?: unknown; type?: Type; error?: string }  // an expression's value now, as an action works it out
  get_settings: Services
  set_settings: Services  // a service set, asked from now on
  set_ports: Services  // saved for the next app launch
  test_connection: { ok: true; models?: number }  // else its error says why
  list_models: { models: string[] }  // none: it can't say, so name one
  suggest: { waiting: number }  // how many of yours aren't sent yet
  send_suggestions: { waiting: number }
}

/** A service proki asks: the LLM a program's asks go to, or jev, which answers questions for you. */
export type Service = "llm" | "jev"

/** A service as it's set: who provides it, where it is, and the model asked there. */
type Connection = { provider: string; url: string; model: string }

/** A provider a service can have: its name, its url (custom: yours), whether a key is kept for it, and its models if it can't list them. */
type Provider = { name: string; url: string; key: boolean; models?: string[] }

/** Each service as it's set (null: not set), and the providers each can have, by id. */
export type Services = {
  services: Record<Service, Connection | null>
  providers: Record<Service, Record<string, Provider>>
  ports: Ports
  active_ports: Ports
}

export type Ports = { activitywatch: number; nats: number; tools: number }

declare global {
  interface Window {
    proki: {
      onShow: (callback: (item: Shown | null) => void) => void  // null: nothing shown
      answer: (id: Shown["id"], answer: number | string | null) => void
      resize: (height: number) => void
      tasks: (request: object) => Promise<Answer<Board & { id: number }>>
      notes: (request: object) => Promise<Answer<Record<Bucket, Note[]> & { id: number }>>
      fields: (request: object) => Promise<Answer<Weighed>>
      apps: (request: object) => Promise<Answer<{ apps: App[]; labels: Label[] }>>
      today: () => Promise<Answer<Today>>
      metrics: (request: object) => Promise<Answer<{ metrics: Metric[] } & Buckets>>
      tool: <K extends keyof Tools>(name: K, args?: object) => Promise<Answer<Tools[K]>>
      // files picked and dropped, as paths, and a file's URL
      pickFiles: (extensions: string[]) => Promise<string[]>
      pickFolder: () => Promise<string | null>
      onDrop: (callback: (kind: "over" | "drop" | "leave", paths: string[]) => void) => Promise<() => void>
      fileUrl: (path: string) => string
      note: () => void
      link: (to: "github" | "activitywatch" | "aw-chrome" | "aw-firefox") => void  // a page of proki's, or ActivityWatch's, in your browser
      watching: () => Promise<boolean>  // whether ActivityWatch answers
      session: (op: "start" | "stop") => void
      onNavigate: (callback: (path: string) => void) => void  // a page, by its path: "tasks/12"
    }
  }
}

/** A file on disk (the media library's), as a page loads it. */
export const fileUrl = (path: string) => window.proki.fileUrl(path)

/** Apply the app's dark theme, then show `page`. */
export function mount(page: ReactNode) {
  document.documentElement.classList.add("dark")
  createRoot(document.getElementById("root")!).render(page)
}

/** A deadline (ISO text) as it's said: "overdue", "due today", "due tomorrow", "due Friday", "due Oct 24". */
export function dueText(deadline: string | null): string {
  if (!deadline) return ""
  const day = new Date(deadline)
  day.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = Math.round((day.getTime() - today.getTime()) / 86_400_000)
  if (days < 0) return "overdue"
  if (days === 0) return "due today"
  if (days === 1) return "due tomorrow"
  if (days < 7) return `due ${day.toLocaleDateString(undefined, { weekday: "long" })}`
  return `due ${day.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`
}

/** A deadline (ISO text) as a date input shows it: its day, here. */
export function dayOf(deadline: string | null): string {
  if (!deadline) return ""
  const day = new Date(deadline)
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`
}

/** A date input's day as a deadline: the end of that day, here (null: none). */
export function endOf(day: string): string | null {
  return day ? new Date(`${day}T23:59:00`).toISOString() : null
}

/** "just now", "5 min ago", "3 h ago", or the date. */
export function ago(when: string): string {
  const minutes = Math.round((Date.now() - new Date(when).getTime()) / 60_000)
  if (minutes < 1) return "just now"
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`
  return new Date(when).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}
