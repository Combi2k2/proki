// The forms that edit your programs, one per kind: a variable, a signal, a rule, a program, a
// state, a way out, an action. Save sends the draft; a mistake shows under the form, which
// stays open. A poke's or a question's pictures and sounds are the media library's, set as
// the action is saved.

import { useEffect, useState, type ReactNode } from "react"
import { AppWindow, Bell, Bot, Equal, KeySquare, ListMinus, ListPlus, Loader2, Lock, MessageCircleQuestionMark, Minus, Music, Plus, X, type LucideIcon } from "lucide-react"
import { DynamicIcon, type IconName } from "lucide-react/dynamic"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import type { MediaItem, RuleSpec, Scope, SignalSpec, StateSpec, Type, VariableSpec } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { CodeInput } from "@/views/code"
import { Criteria, TypeField } from "@/views/fields"
import { IconPicker } from "@/views/icon-picker"
import { file, MediaPicker } from "@/views/media"
import { SYMBOL } from "@/views/program-inspect"

export const NAMES = "proki-names"  // the names a field suggests: a <datalist> the page fills
const ASKS = ["ask_usr", "ask_jev", "ask_llm"]
const TIMEOUT: Record<string, number> = { ask_usr: 120, ask_jev: 10, ask_llm: 10 }  // seconds, unless it says
export const ACTIONS: Record<string, [string, LucideIcon, string]> = {  // each action's name, its icon, and the tint behind it
  poke:    ["Poke",   Bell,                      "bg-sky-500/15 text-sky-700 dark:text-sky-300"],
  ask_usr: ["Ask",    MessageCircleQuestionMark, "bg-sky-500/15 text-sky-700 dark:text-sky-300"],
  lock:    ["Lock",   Lock,                      "bg-amber-500/15 text-amber-700 dark:text-amber-300"],
  open:    ["Open",   AppWindow,                 "bg-amber-500/15 text-amber-700 dark:text-amber-300"],
  ask_llm: ["LLM",    Bot,                       "bg-violet-500/15 text-violet-700 dark:text-violet-300"],
  ask_jev: ["Jev",    KeySquare,                 "bg-fuchsia-500/15 text-fuchsia-700 dark:text-fuchsia-300"],
  set:     ["Set",    Equal,                     "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"],
  add:     ["Add",    Plus,                      "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"],
  sub:     ["Sub",    Minus,                     "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"],
  append:  ["Append", ListPlus,                  "bg-orange-500/15 text-orange-700 dark:text-orange-300"],
  remove:  ["Remove", ListMinus,                 "bg-orange-500/15 text-orange-700 dark:text-orange-300"],
}

/** What a save says back: null when it's kept, else the mistake. */
export type Save = (data: Record<string, unknown>) => Promise<string | null>

// --- values, as they're typed ---------------------------------------------------------------

/** A variable's value as it's typed: empty is unknown, true / false, a number, else an expression. */
export function valueText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value)
}

export function parseValue(text: string): boolean | number | string | null {
  const t = text.trim()
  if (t === "") return null
  if (t === "true" || t === "false") return t === "true"
  return /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : t
}

/** A rule's side: a number, else an expression. */
const parseSide = (text: string) => (/^-?\d+(\.\d+)?$/.test(text.trim()) ? Number(text.trim()) : text.trim())
const parseNumber = (text: string) => (text.trim() === "" ? null : Number(text))

/** A time as it's typed: empty is none, a number is minutes, else a phrase ("6s", "1d"). */
const parseSpan = (text: string): number | string | null => (text.trim() === "" ? null : /^\d+(\.\d+)?$/.test(text.trim()) ? Number(text) : text.trim())

// --- the form, and its fields ---------------------------------------------------------------

/** A form: its fields, then Save and Cancel, and the mistake the last save made. */
function Form({ children, onSave, onCancel, saveLabel = "Save", plain }: {
  children: ReactNode
  onSave: () => Promise<string | null>
  onCancel: () => void
  saveLabel?: string
  plain?: boolean  // no box of its own: in a panel already
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const save = async () => {
    setBusy(true)
    const mistake = await onSave()
    setBusy(false)
    setError(mistake ?? "")
  }
  return (
    <form className={cn("flex flex-col gap-3", !plain && "rounded-lg border bg-muted/30 p-3")} onSubmit={(e) => { e.preventDefault(); save() }}>
      {children}
      {error && <p className="text-xs break-words text-destructive">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button type="submit" size="sm" disabled={busy}>{busy && <Loader2 className="animate-spin" />}{saveLabel}</Button>
      </div>
    </form>
  )
}

/** A field: its label, a hint beside it, then what it holds (`group`: several controls of their
 *  own, so a click on one isn't taken as one on the first). */
export function Field({ label, hint, group, children, className }: { label: string; hint?: string; group?: boolean; children: ReactNode; className?: string }) {
  const Box = group ? "div" : "label"
  return (
    <Box role={group ? "group" : undefined} aria-label={group ? label : undefined} className={cn("flex min-w-0 flex-col gap-1", className)}>
      <span className="text-xs font-medium">{label}{hint && <span className="ml-1.5 font-normal text-muted-foreground">{hint}</span>}</span>
      {children}
    </Box>
  )
}

function Text({ value, onChange, code, names, ...props }: {
  value: string
  onChange: (value: string) => void
  code?: boolean
  names?: boolean
} & Omit<React.ComponentProps<"input">, "value" | "onChange">) {
  if (names) return <CodeInput value={value} onChange={(e) => onChange(e.target.value)} list={NAMES} className="h-8 text-xs" {...props} />
  return <Input value={value} onChange={(e) => onChange(e.target.value)} className={cn("h-8 text-sm", code && "font-mono text-xs")} spellCheck={!code} {...props} />
}

export function Choice({ value, onChange, options, className }: {
  value: string
  onChange: (value: string) => void
  options: [string, string][]  // value, label
  className?: string
}) {
  return (
    <NativeSelect value={value} onChange={(e) => onChange(e.target.value)} className={className}>
      {options.map(([v, label]) => <NativeSelectOption key={v} value={v}>{label}</NativeSelectOption>)}
    </NativeSelect>
  )
}

const Row = ({ children }: { children: ReactNode }) => <div className="grid grid-cols-2 gap-3">{children}</div>

// --- a variable, a signal, a rule -----------------------------------------------------------

type Where = { scope: Scope; program: string | null; state: string | null }
/** A name, a description and a type given from outside the form (a panel's title, the line
 *  under it, and the type beside its name). */
export type Named = { name: string; desc: string; type: Type }

/** A variable: where it starts, and its type. */
export function VariableForm({ spec, where, named, onSave, onCancel }: {
  spec?: VariableSpec; where: Where; named?: Named; onSave: Save; onCancel: () => void
}) {
  const [name, setName] = useState(spec?.name ?? "")
  const [desc, setDesc] = useState(spec?.desc ?? "")
  const [value, setValue] = useState(valueText(spec?.value))
  const [type, setType] = useState<Type>(spec?.type ?? "any")
  const scope = spec?.scope ?? where.scope
  const head = named ?? { name, desc }
  return (
    <Form plain={!!named} onCancel={onCancel}
          onSave={() => onSave({ name: head.name.trim(), desc: head.desc, value: parseValue(value), type: named?.type ?? type, scope })}>
      <Row>
        {!named && <Field label="Name"><Text value={name} onChange={setName} code autoFocus placeholder="pokes" /></Field>}
        <Field label="Starts as" hint="number, true/false or expression">
          <Text value={value} onChange={setValue} code names placeholder="0" />
        </Field>
      </Row>
      {!named && <TypeField label="Type" value={type} onChange={(t) => setType(t ?? "any")} />}
      {!named && <Field label="Description"><Text value={desc} onChange={setDesc} placeholder="pokes today" /></Field>}
    </Form>
  )
}

const UNITS: [string, string][] = [["s", "seconds"], ["min", "minutes"], ["h", "hours"], ["d", "days"]]

/** A history's length as its amount and its unit: "7d" is 7 days, a number minutes. */
function spanned(backfill: number | string | null | undefined): [string, string] {
  if (backfill == null) return ["", "d"]
  if (typeof backfill === "number") return [String(backfill), "min"]
  const found = /^(\d+(?:\.\d+)?)\s*(s|min|h|d)$/.exec(backfill.trim())
  return found ? [found[1], found[2]] : [backfill, "min"]
}

/** A signal: its expression, and how much of its history is kept, across restarts. Typing an
 *  amount keeps it; switched off, none is. */
export function SignalForm({ spec, where, named, onSave, onCancel }: { spec?: SignalSpec; where: Where; named?: Named; onSave: Save; onCancel: () => void }) {
  const [name, setName] = useState(spec?.name ?? "")
  const [desc, setDesc] = useState(spec?.desc ?? "")
  const [expr, setExpr] = useState(spec?.expr ?? "")
  const [[amount, unit], setSpan] = useState(spanned(spec?.backfill))
  const [persist, setPersist] = useState(spec?.persist ?? spec?.backfill != null)
  const [type, setType] = useState<Type>(spec?.type ?? "any")
  const scope = spec?.scope ?? where.scope
  const head = named ?? { name, desc }
  const kept = persist && amount.trim() !== ""
  const typed = (v: string) => { setSpan([v, unit]); if (v.trim()) setPersist(true) }
  const keep = (on: boolean) => { setPersist(on); if (!on) setSpan(["", unit]) }
  return (
    <Form plain={!!named} onCancel={onCancel}
          onSave={() => onSave({ name: head.name.trim(), desc: head.desc, expr, backfill: kept ? `${amount.trim()}${unit}` : null, persist: kept,
                                 type: named?.type ?? type, scope })}>
      {!named && <Field label="Name"><Text value={name} onChange={setName} code autoFocus placeholder="focus_5m" /></Field>}
      <Field label="Expression"><Text value={expr} onChange={setExpr} code names placeholder="ts_mean(keys_pressed, 5)" /></Field>
      <Field label="History" hint="kept across restarts">
        <div className="flex items-center gap-2">
          <Text value={amount} onChange={typed} type="number" min={0} step="any" placeholder="–" className="h-8 w-24 text-sm" />
          <Choice value={unit} onChange={(u) => setSpan([amount, u])} options={UNITS} className={cn(!persist && "opacity-50")} />
          <Switch checked={persist} onCheckedChange={keep} aria-label="Keep its history across restarts" />
        </div>
      </Field>
      {!named && <TypeField label="Type" value={type} onChange={(t) => setType(t ?? "any")} />}
      {!named && <Field label="Description"><Text value={desc} onChange={setDesc} placeholder="typing, last 5 min" /></Field>}
    </Form>
  )
}

export function RuleForm({ spec, where, named, onSave, onCancel }: { spec?: RuleSpec; where: Where; named?: Named; onSave: Save; onCancel: () => void }) {
  const [name, setName] = useState(spec?.name ?? "")
  const [desc, setDesc] = useState(spec?.desc ?? "")
  const [lhs, setLhs] = useState(String(spec?.lhs ?? ""))
  const [cmp, setCmp] = useState<string>(spec?.cmp ?? "gt")
  const [rhs, setRhs] = useState(String(spec?.rhs ?? ""))
  const [softness, setSoftness] = useState(String(spec?.softness ?? 0))
  const [level, setLevel] = useState(String(spec?.level ?? 1))
  const scope = spec?.scope ?? where.scope
  const head = named ?? { name, desc }
  return (
    <Form plain={!!named} onCancel={onCancel}
          onSave={() => onSave({ name: head.name.trim(), desc: head.desc, lhs: parseSide(lhs), cmp, rhs: parseSide(rhs),
                                 softness: Number(softness) || 0, level: Math.round(Number(level)) || 1, scope })}>
      {!named && <Field label="Name"><Text value={name} onChange={setName} code autoFocus placeholder="focus_high" /></Field>}
      <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-2">
        <Field label="Left"><Text value={lhs} onChange={setLhs} code names placeholder="focus" /></Field>
        <Choice value={cmp} onChange={setCmp} options={Object.entries(SYMBOL).map(([k, s]) => [k, s])} className="w-16 font-mono" />
        <Field label="Right"><Text value={rhs} onChange={setRhs} code names placeholder="0.6" /></Field>
      </div>
      <Row>
        <Field label="Softness" hint="0 = hard">
          <Text value={softness} onChange={setSoftness} type="number" min={0} step="any" />
        </Field>
        <Field label="Level" hint="higher votes first"><Text value={level} onChange={setLevel} type="number" step={1} /></Field>
      </Row>
      {!named && <Field label="Description"><Text value={desc} onChange={setDesc} placeholder="focus is building" /></Field>}
    </Form>
  )
}

// --- a program, a state, a way out ----------------------------------------------------------

export function ProgramForm({ spec, states, onSave, onCancel, saveLabel }: {
  spec?: { name: string; title?: string; desc: string; icon?: string; tags: string[]; initial: string }
  states?: string[]  // to start in (none: a new program, starting in a new state)
  onSave: Save
  onCancel: () => void
  saveLabel?: string
}) {
  const [name, setName] = useState(spec?.name ?? "")
  const [title, setTitle] = useState(spec?.title ?? "")
  const [desc, setDesc] = useState(spec?.desc ?? "")
  const [icon, setIcon] = useState(spec?.icon ?? "")
  const [tags, setTags] = useState((spec?.tags ?? []).join(", "))
  const [initial, setInitial] = useState(spec?.initial ?? "idle")
  return (
    <Form onCancel={onCancel} saveLabel={saveLabel}
          onSave={() => onSave({ name: name.trim(), title: title.trim(), desc, icon: icon.trim(), initial: initial.trim(),
                                 tags: tags.split(",").map((t) => t.trim()).filter(Boolean) })}>
      <Row>
        <Field label="Name"><Text value={name} onChange={setName} code autoFocus placeholder="stretch" /></Field>
        <Field label="Starts in">
          {states ? <Choice value={initial} onChange={setInitial} options={states.map((s) => [s, s])} />
                  : <Text value={initial} onChange={setInitial} code />}
        </Field>
      </Row>
      <Row>
        <Field label="Title" hint="what the app calls it"><Text value={title} onChange={setTitle} placeholder="Stretch breaks" /></Field>
        <Field label="Icon" hint="its picture, where it's listed">
          <IconPicker value={icon} onPick={setIcon}>
            <Button type="button" variant="outline" className="justify-start font-normal">
              {icon ? <DynamicIcon name={icon as IconName} data-icon="inline-start" /> : null}{icon || "Choose…"}
            </Button>
          </IconPicker>
        </Field>
      </Row>
      <Field label="Description"><Text value={desc} onChange={setDesc} placeholder="Stand up every hour." /></Field>
      <Field label="Tags" hint="comma-separated; the first of focus, day, tasks, notes, background says where it's listed">
        <Text value={tags} onChange={setTags} placeholder="day, health" />
      </Field>
    </Form>
  )
}

export function StateForm({ spec, onSave, onCancel }: { spec?: StateSpec; onSave: Save; onCancel: () => void }) {
  const [name, setName] = useState(spec?.name ?? "")
  const [desc, setDesc] = useState(spec?.desc ?? "")
  const [every, setEvery] = useState(String(spec?.every ?? 1))
  return (
    <Form onCancel={onCancel} onSave={() => onSave({ name: name.trim(), desc, every: parseSpan(every) ?? 1 })}>
      <Row>
        <Field label="Name"><Text value={name} onChange={setName} code autoFocus placeholder="waiting" /></Field>
        <Field label="Check every" hint="6s, 5min, 1h; a number: minutes"><Text value={every} onChange={setEvery} placeholder="6s" /></Field>
      </Row>
      <Field label="Description"><Text value={desc} onChange={setDesc} placeholder="an hour of work" /></Field>
    </Form>
  )
}

/** A transition: where it goes, and when. Each line of `when` is a rule's name or a condition. A
 * state not there yet is made. */
export function BranchForm({ spec, states, onSave, onCancel }: {
  spec?: { goto: string; when: string[]; desc: string }
  states: string[]
  onSave: Save
  onCancel: () => void
}) {
  const [goto, setGoto] = useState(spec?.goto ?? "")
  const [when, setWhen] = useState<string[]>(spec?.when ?? [])
  const [desc, setDesc] = useState(spec?.desc ?? "")
  return (
    <Form onCancel={onCancel} onSave={() => onSave({ goto: goto.trim(), when: when.map((w) => w.trim()).filter(Boolean), desc })}>
      <Row>
        <Field label="Go to" hint={goto.trim() && !states.includes(goto.trim()) ? "a new state" : undefined}>
          <Text value={goto} onChange={setGoto} code autoFocus list="states" placeholder={states[0] ?? "waiting"} />
          <datalist id="states">{states.map((s) => <option key={s} value={s} />)}</datalist>
        </Field>
        <Field label="Description"><Text value={desc} onChange={setDesc} placeholder="you came back" /></Field>
      </Row>
      <Field label="When" hint="all must hold: a condition or a rule; none = else">
        <Lines values={when} onChange={setWhen} placeholder="answer == 0" add="Condition" />
      </Field>
    </Form>
  )
}

/** A list of lines, each its own field: add one, take one out. */
function Lines({ values, onChange, placeholder, add }: { values: string[]; onChange: (values: string[]) => void; placeholder: string; add: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      {values.map((v, i) => (
        <div key={i} className="flex gap-1.5">
          <Text value={v} onChange={(next) => onChange(values.map((w, j) => (j === i ? next : w)))} code names placeholder={placeholder}
                autoFocus={i === values.length - 1 && v === ""} />
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Take it out" onClick={() => onChange(values.filter((_, j) => j !== i))}><X /></Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" className="w-fit" onClick={() => onChange([...values, ""])}><Plus /> {add}</Button>
    </div>
  )
}

// --- an action ------------------------------------------------------------------------------

type Params = Record<string, unknown>
type Picks = { image: string[]; sound: string[] }  // an action's pictures and sounds, by kind

/** An action: its kind (chosen when it's new), its name (its kind's, until you change it) and
 *  what it's for, then its params, as the kind takes them, and a poke's or a question's picks.
 *  Its id is made from where it is and its name as it's added ("bedtime.poking.bedtime"). */
export function ActionForm({ spec, at, about, taken, onSave, onCancel }: {
  spec?: { id: string; name: string; desc: string; kind: string; params: Params }
  at: { program: string; state: string }
  about: { name: string; about: string }[]  // what each kind does
  taken: string[]  // its state's actions' names
  onSave: Save
  onCancel: () => void
}) {
  const [kind, setKind] = useState(spec?.kind ?? "poke")
  const [name, setName] = useState(spec?.name ?? free("poke", taken))
  const [desc, setDesc] = useState(spec?.desc ?? "")
  const [params, setParams] = useState<Params>(spec?.params ?? {})
  const id = spec?.id ?? `${at.program}.${at.state}.${name}`
  const [picks, setPicks] = useState<Picks>({ image: [], sound: [] })
  const [picked, setPicked] = useState(false)  // changed: set them as it's saved
  useEffect(() => {
    if (!spec) return
    window.proki.tool("get_picks", { id }).then((answer) => {
      if (!answer.error) setPicks({ image: answer.media.filter((m) => m.kind === "image").map((m) => m.key),
                                    sound: answer.media.filter((m) => m.kind === "sound").map((m) => m.key) })
    })
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  const set = (key: string, value: unknown) =>
    setParams((p) => { const next = { ...p }; if (value === undefined) delete next[key]; else next[key] = value; return next })
  const pick = (which: keyof Picks, keys: string[]) => { setPicks((p) => ({ ...p, [which]: keys })); setPicked(true) }
  const shown = kind === "poke" || kind === "ask_usr"
  const does = about.find((a) => a.name === kind)?.about
  const save = async () => {
    const mistake = await onSave({ name, desc, kind, params: cleaned(kind, params) })
    if (mistake || !picked || !shown) return mistake
    const answer = await window.proki.tool("set_picks", { id, keys: [...picks.image, ...picks.sound] })
    return answer.error ? `Saved, but its pictures and sounds weren't: ${answer.error}` : null
  }
  return (
    <Form onCancel={onCancel} onSave={save}>
      {!spec && (
        <Field label="Kind">
          <Choice value={kind} onChange={(k) => { if (name === free(kind, taken)) setName(free(k, taken)); setKind(k); setParams({}) }} options={Object.entries(ACTIONS).map(([k, [said]]) => [k, said])} />
          {does && <p className="text-xs text-muted-foreground first-letter:uppercase">{does}.</p>}
        </Field>
      )}
      <Row>
        <Field label="Name"><Text value={name} onChange={setName} code placeholder="bedtime" /></Field>
        <Field label="Description"><Text value={desc} onChange={setDesc} placeholder="asks whether to wind down" /></Field>
      </Row>
      {(kind === "set" || kind === "add" || kind === "sub" || kind === "append" || kind === "remove") && (
        <>
          {kind === "append" ? (
            <>
              <Row>
                <Field label="List" hint="a variable that's a list: notes, work.groups">
                  <Text value={String(params.name ?? "")} onChange={(v) => set("name", v)} code names autoFocus placeholder="note" />
                </Field>
                <Field label="Item">
                  <Choice value={typeof params.expr === "string" ? "value" : "object"} onChange={(v) => set("expr", v === "value" ? "" : { "": "" })}
                          options={[["object", "an object, field by field"], ["value", "a value, an expression"]]} />
                </Field>
              </Row>
              {typeof params.expr === "string" ? (
                <Field label="Value" hint="expression">
                  <Text value={params.expr} onChange={(v) => set("expr", v)} code names placeholder="time + 60" />
                </Field>
              ) : (
                <FieldsField value={(params.expr as Record<string, string> | undefined) ?? { "": "" }} onChange={(v) => set("expr", v)} />
              )}
            </>
          ) : kind === "remove" ? (
            <Row>
              <Field label="List" hint="a variable that's a list of objects, each with an id">
                <Text value={String(params.name ?? "")} onChange={(v) => set("name", v)} code names autoFocus placeholder="note" />
              </Field>
              <Field label="Id" hint="expression: the item's id">
                <Text value={String(params.id ?? "")} onChange={(v) => set("id", v || undefined)} code names placeholder="todo.id" />
              </Field>
            </Row>
          ) : (
            <Row>
              <Field label="Variable" hint="or a place in it: work.tasks[at].status">
                <Text value={String(params.name ?? "")} onChange={(v) => set("name", v)} code names autoFocus placeholder="pokes" />
              </Field>
              <Field label={{ set: "To", add: "By", sub: "By" }[kind]} hint="expression">
                <Text value={valueText(params.expr)} onChange={(v) => set("expr", parseValue(v) ?? undefined)} code names placeholder="pokes + 1" />
              </Field>
            </Row>
          )}
          <Field label="Only when" hint="expression; empty: always">
            <Text value={String(params.when ?? "")} onChange={(v) => set("when", v || undefined)} code names placeholder="answer == 0" />
          </Field>
        </>
      )}
      {kind === "poke" && <Said params={params} set={set} picks={picks} pick={pick} poke />}
      {kind === "ask_jev" && <JevFields params={params} set={set} />}
      {ASKS.includes(kind) && kind !== "ask_jev" && <AskFields kind={kind} params={params} set={set} picks={picks} pick={pick} at={at} />}
      {kind === "open" && (
        <Field label="Page" hint="its path, an expression: a view (today, tasks, notes, ...), then what in it">
          <Text value={String(params.path ?? "")} onChange={(v) => set("path", v || undefined)} code names placeholder="'tasks/' + str(work.group.id)" />
        </Field>
      )}
      {kind === "lock" && <p className="text-xs text-muted-foreground">Locks the screen.</p>}
    </Form>
  )
}

/** A name for a new action of `kind` that none of `taken` has: "ask_usr", else "ask_usr_2", ... */
function free(kind: string, taken: string[]): string {
  for (let n = 1; ; n++) {
    const name = n === 1 ? kind : `${kind}_${n}`
    if (!taken.includes(name)) return name
  }
}

/** The params as the kind takes them: what's empty left out, an open's page always said. */
function cleaned(kind: string, params: Params): Params {
  const kept = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0)))
  if (kind === "open" && !kept.path) kept.path = "'today'"
  if (kind === "ask_llm") delete kept.schema  // it answers as its variable is typed
  if (kept.fields) kept.fields = Object.fromEntries(Object.entries(kept.fields as Record<string, string>).filter(([k]) => k.trim()))
  if ((kind === "set" || kind === "add" || kind === "sub") && !("expr" in kept)) kept.expr = null
  return kept
}

/** A new record's fields, each an expression's value. */
function FieldsField({ value, onChange }: { value: Record<string, string>; onChange: (value: Record<string, string>) => void }) {
  const rows = Object.entries(value)
  const put = (next: [string, string][]) => onChange(Object.fromEntries(next))
  return (
    <Field label="Fields" hint="each an expression">
      {rows.map(([key, expr], i) => (
        <div key={i} className="flex items-center gap-1.5">
          <Input value={key} onChange={(e) => put(rows.map((r, j) => (j === i ? [e.target.value, r[1]] : r)))}
                 className="h-8 w-28 font-mono text-xs" placeholder="content" />
          <span className="text-xs text-muted-foreground">is</span>
          <CodeInput value={expr} onChange={(e) => put(rows.map((r, j) => (j === i ? [r[0], e.target.value] : r)))}
                     list={NAMES} layout="flex-1" className="h-8 text-xs" placeholder="'Todo'" />
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Take it out" onClick={() => put(rows.filter((_, j) => j !== i))}><X /></Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" className="w-fit" onClick={() => put([...rows.filter(([k]) => k !== ""), ["", ""]])}><Plus /> Field</Button>
    </Field>
  )
}

/** What a poke or a question to you says and shows: its text, title (a poke's, if it has one), pictures and sounds. */
function Said({ params, set, picks, pick, poke }: {
  poke?: boolean
  params: Params
  set: (key: string, value: unknown) => void
  picks: Picks
  pick: (which: keyof Picks, keys: string[]) => void
}) {
  return (
    <>
      <ContextField value={params.context} onChange={(v) => set("context", v)} />
      <Field label="Title" hint={poke ? "optional" : undefined}><Text value={String(params.title ?? "")} onChange={(v) => set("title", v || undefined)} placeholder="Bedtime" /></Field>
      <Row>
        <Field label="Pictures" hint="one at random">
          <KeysField kind="image" keys={picks.image} onChange={(keys) => pick("image", keys)} />
        </Field>
        <Field label="Sounds" hint="one at random">
          <KeysField kind="sound" keys={picks.sound} onChange={(keys) => pick("sound", keys)} />
        </Field>
      </Row>
    </>
  )
}

/** What's said: a text, with {name}s filled in from expressions as it's said. */
function ContextField({ value, onChange }: { value: unknown; onChange: (value: unknown) => void }) {
  const context = typeof value === "string" ? { format: value, values: {} } : (value as { format?: string; values?: Record<string, string> }) ?? {}
  const format = context.format ?? ""
  const values = Object.entries(context.values ?? {})
  const put = (nextFormat: string, nextValues: [string, string][]) =>
    onChange(nextValues.length ? { format: nextFormat, values: Object.fromEntries(nextValues) } : nextFormat)
  return (
    <Field label="Text" hint="{name} filled from values below">
      <Textarea value={format} onChange={(e) => put(e.target.value, values)} rows={2} className="min-h-14 text-sm" autoFocus
                placeholder="{h:.1f} h shallow so far. Start a session?" />
      {values.map(([name, expr], i) => (
        <div key={i} className="flex items-center gap-1.5">
          <Input value={name} onChange={(e) => put(format, values.map((v, j) => (j === i ? [e.target.value, v[1]] : v)))}
                 className="h-8 w-24 font-mono text-xs" placeholder="h" />
          <span className="text-xs text-muted-foreground">is</span>
          <Input value={expr} onChange={(e) => put(format, values.map((v, j) => (j === i ? [v[0], e.target.value] : v)))}
                 list={NAMES} className="h-8 font-mono text-xs" placeholder="shallow_today / 60" />
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Take it out" onClick={() => put(format, values.filter((_, j) => j !== i))}><X /></Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" className="w-fit" onClick={() => put(format, [...values, ["", ""]])}><Plus /> Value</Button>
    </Field>
  )
}

type Criteria = Record<string, string | null>  // each label, and what it means
type Question = { type: "noul" | "choice" | "score"; question: string; criteria?: Criteria | string; result: string }
const QUESTION: [string, string][] = [["noul", "Yes or no"], ["choice", "A choice"], ["score", "A score"]]

/** jev's questions, asked at once about what its context says: each a yes or no, a choice of
 *  its criteria, or a score (where it is on a scale, its criteria marks on it), its answer in its own
 *  variable: a yes or no's probability of yes, a choice's .index, .conf and .odds, a score's .score, .conf and .odds. */
function JevFields({ params, set }: { params: Params; set: (key: string, value: unknown) => void }) {
  const questions = (params.questions as Question[] | undefined) ?? []
  useEffect(() => {
    if (params.questions === undefined) set("questions", [{ type: "choice", question: "", criteria: { "": "" }, result: "answer" }])
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  const put = (i: number, change: Partial<Question>) =>
    set("questions", questions.map((q, j) => (j !== i ? q : { ...q, ...change })))
  const typed = (i: number, type: Question["type"]) =>
    put(i, { type, criteria: type === "noul" ? undefined : questions[i].criteria ?? { "": "" } })
  const free = () => { const taken = new Set(questions.map((q) => q.result)); let n = 1; while (taken.has(`answer${n}`)) n++; return `answer${n}` }
  return (
    <>
      <ContextField value={params.context} onChange={(v) => set("context", v)} />
      {questions.map((q, i) => (
        <div key={i} className="flex flex-col gap-2 rounded-md border p-2.5">
          <Row>
            <Field label="Answer"><Choice value={q.type} options={QUESTION} onChange={(t) => typed(i, t as Question["type"])} /></Field>
            <Field label="Save answer to" hint={{ noul: "the probability of yes", choice: ".index .conf .odds", score: ".score .conf .odds" }[q.type]}>
              <Text value={q.result} onChange={(v) => put(i, { result: v })} code />
            </Field>
            <Button type="button" size="icon-sm" variant="ghost" aria-label="Take it out" disabled={questions.length === 1} className="mt-5"
                    onClick={() => set("questions", questions.filter((_, j) => j !== i))}><X /></Button>
          </Row>
          <Field label="Question"><Text value={q.question} onChange={(v) => put(i, { question: v })} placeholder={q.type === "noul" ? "Is it urgent?" : "What is it?"} /></Field>
          {q.type !== "noul" && (
            <Field label={q.type === "score" ? "Marks on its scale" : "Options"}>
              <Choice value={typeof q.criteria === "string" ? "expr" : "list"} options={[["list", "A list"], ["expr", "From an expression"]]}
                      onChange={(v) => put(i, { criteria: v === "expr" ? "" : { "": "" } })} />
            </Field>
          )}
          {q.type !== "noul" && typeof q.criteria === "object" && q.criteria !== null && (
            <Criteria key={`${i}-${q.type}`} criteria={q.criteria} onSet={(criteria) => put(i, { criteria })}
                      {...(q.type === "score" ? { label: "Marks", hint: "a number on its scale, and what it means", placeholder: "1" } : {})} />
          )}
          {typeof q.criteria === "string" && (
            <Field label={q.type === "score" ? "Marks" : "Options"} hint={q.type === "score" ? "an expression: {mark: meaning}" : "an expression: {label: meaning}, or a list of texts or [label, meaning]"}>
              <Text value={q.criteria} onChange={(v) => put(i, { criteria: v })} code names placeholder="track.labels" />
            </Field>
          )}
        </div>
      ))}
      <Row>
        <Button type="button" size="sm" variant="outline" className="w-fit"
                onClick={() => set("questions", [...questions, { type: "noul", question: "", result: free() }])}><Plus /> Question</Button>
        <Field label="Timeout" hint={`s, default ${TIMEOUT.ask_jev}`}>
          <Text value={params.timeout == null ? "" : String(params.timeout)} onChange={(v) => set("timeout", parseNumber(v) ?? undefined)} type="number" min={1} />
        </Field>
      </Row>
    </>
  )
}

/** The type of the variable an answer is saved to, by its name as the state reads it (its
 *  own, its program's, then a global one): what the LLM answers. It's set on the variable. */
function Answered({ name, at }: { name: string; at: { program: string; state: string } }) {
  const [found, setFound] = useState<{ name: string; type: Type } | null>(null)
  useEffect(() => {
    let gone = false
    const names = name.includes(".") ? [name] : [`${at.program}.${at.state}.${name}`, `${at.program}.${name}`, name]
    ;(async () => {
      for (const n of names) {
        const answer = await window.proki.tool("evaluate", { expr: n })
        if (!answer.error) return gone || setFound({ name: n, type: answer.type ?? "any" })
      }
      if (!gone) setFound(null)
    })()
    return () => { gone = true }
  }, [name, at.program, at.state])
  if (!name.trim()) return null
  const text = !found || found.type === "any"
  return (
    <Field label="It answers" group hint={found ? (text ? "text: give the variable a type for more" : `as ${found.name} is typed; change it on the variable`) : "text, until the variable is made"}>
      {found && !text && <TypeField label="" value={found.type} fixed />}
    </Field>
  )
}

/** A question, as its kind takes it: to you (its text, title, pictures, its options), to the
 *  LLM (what it reads; it answers as the variable it's saved to is typed). */
function AskFields({ kind, params, set, picks, pick, at }: {
  kind: string
  at: { program: string; state: string }
  params: Params
  set: (key: string, value: unknown) => void
  picks: Picks
  pick: (which: keyof Picks, keys: string[]) => void
}) {
  const options = params.options as string[] | string | undefined
  const listed = Array.isArray(options)
  const usr = kind === "ask_usr", llm = kind === "ask_llm"
  const answers = llm ? "typed" : options === undefined ? "none" : listed ? "options" : "expr"
  useEffect(() => {
    if (params.result === undefined) set("result", "answer")
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  const answer = (v: string) => {
    set("options", v === "options" ? [""] : v === "expr" ? "" : undefined)
    set("default", undefined)
  }
  const kinds: [string, string][] = [["options", "An option: its number, from 0"], ["expr", "An option, from a list"], ["none", "Text"]]
  return (
    <>
      {usr ? <Said params={params} set={set} picks={picks} pick={pick} /> : <ContextField value={params.context} onChange={(v) => set("context", v)} />}
      {usr && <Field label="Answer"><Choice value={answers} options={kinds} onChange={answer} /></Field>}
      {usr && listed && <OptionsField options={options} onChange={(next) => set("options", next)} />}
      {usr && typeof options === "string" && (
        <Field label="Options" hint="an expression: a list of texts">
          <Text value={options} onChange={(v) => set("options", v)} code names placeholder="track.labels" />
        </Field>
      )}
      <Row>
        <Field label="Save answer to" hint={llm ? "its type is what the LLM answers" : undefined}>
          <Text value={String(params.result ?? "")} onChange={(v) => set("result", v)} code />
        </Field>
      </Row>
      {llm && <Answered name={String(params.result ?? "")} at={at} />}
      <Row>
        {usr && listed && typeof params.default !== "string" && (
          <Field label="Picked already">
            <Choice value={String(params.default ?? -1)} onChange={(v) => set("default", Number(v) === -1 ? undefined : Number(v))}
                    options={[["-1", "none"], ...options.map((o, i): [string, string] => [String(i), `${i}: ${o || "…"}`])]} />
          </Field>
        )}
        {usr && options !== undefined && (!listed || typeof params.default === "string") && (
          <Field label="Picked already" hint="expression: an option or its number"><Text value={String(params.default ?? "")} onChange={(v) => set("default", v || undefined)} code names /></Field>
        )}
        <Field label="Timeout" hint={`s, default ${TIMEOUT[kind]}`}>
          <Text value={params.timeout == null ? "" : String(params.timeout)} onChange={(v) => set("timeout", parseNumber(v) ?? undefined)} type="number" min={1} />
        </Field>
        {usr && (
          <Field label="No “Later”">
            <Switch checked={params.immediate === true} onCheckedChange={(on) => set("immediate", on || undefined)} />
          </Field>
        )}
      </Row>
    </>
  )
}

/** Your question's options, in order: each a text. */
function OptionsField({ options, onChange }: { options: string[]; onChange: (options: string[]) => void }) {
  const put = (i: number, option: string) => onChange(options.map((o, j) => (j !== i ? o : option)))
  return (
    <div className="flex flex-col gap-1.5">
      {options.map((o, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <span className="w-4 text-right text-xs text-muted-foreground tabular-nums">{i}</span>
          <Input value={o} placeholder="Start" className="h-8 text-sm" onChange={(e) => put(i, e.target.value)} />
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Take it out" disabled={options.length === 1}
                  onClick={() => onChange(options.filter((_, j) => j !== i))}><X /></Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" className="w-fit" onClick={() => onChange([...options, ""])}>
        <Plus /> Option
      </Button>
    </div>
  )
}

/** Keys of the media library, shown as they are, and chosen in the library's window. */
function KeysField({ kind, keys, onChange }: { kind: "image" | "sound"; keys: string[]; onChange: (keys: string[]) => void }) {
  const [items, setItems] = useState<MediaItem[]>([])
  const [picking, setPicking] = useState(false)
  useEffect(() => {
    if (!keys.length) return setItems([])
    window.proki.tool("get_media", { keys }).then((answer) => !answer.error && setItems(answer.media))
  }, [keys.join("\n")])  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="flex min-h-8 flex-wrap items-center gap-1.5">
      {items.map((item) => kind === "image" ? (
        <img key={item.key} src={file(item.file)} title={item.name} alt="" className="size-9 rounded-md border bg-muted/50 object-contain" />
      ) : (
        <span key={item.key} className="flex items-center gap-1 rounded-md border px-1.5 py-1 text-[11px]"><Music className="size-3" />{item.name}</span>
      ))}
      <Button type="button" size="sm" variant="outline" onClick={() => setPicking(true)}>{keys.length ? "Change…" : "Choose…"}</Button>
      {picking && <MediaPicker kind={kind} keys={keys} onClose={() => setPicking(false)} onDone={(next) => { onChange(next); setPicking(false) }} />}
    </div>
  )
}
