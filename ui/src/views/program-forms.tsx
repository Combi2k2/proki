// The forms that edit your programs, one per kind: a variable, a signal, a rule, a program, a
// state, a way out, an action. Save sends the draft; a mistake shows under the form, which
// stays open. A poke's or a question's pictures and sounds are the media library's, set as
// the action is saved. A form you've changed is marked so (`data-dirty`), so what would close it
// can ask first; Escape cancels one you haven't.

import { useEffect, useRef, useState, type ReactNode } from "react"
import { AppWindow, Bell, Bot, CircleCheck, Equal, KeySquare, ListMinus, ListPlus, Loader2, Lock, MessageCircleQuestionMark, Minus, Music, Play, Plus, Trash2, type LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import type { MediaItem, StateSpec, Type } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { BARE, CodeInput, Template } from "@/views/code"
import { Criteria, TypeField } from "@/views/fields"
import { CHANGED_LINE, Editable, Pick, useStaged } from "@/views/in-place"
import { file, MediaPicker } from "@/views/media"
import { ActionRows, ACTION_ROWS, NAMES, rowField } from "@/views/action-rows"

export { NAMES }


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

/** An action's icon on its tint, as its state shows it. */
export const Tinted = ({ icon: Icon, tint }: { icon: LucideIcon; tint: string }) => (
  <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-md", tint)}><Icon aria-hidden className="size-3" /></span>
)

/** What a save says back: null when it's kept, else the mistake. */
export type Save = (data: Record<string, unknown>) => Promise<string | null>

// --- values, as they're typed ---------------------------------------------------------------

/** A rule's side: a number, else an expression. */
export const parseSide = (text: string) => (/^-?\d+(\.\d+)?$/.test(text.trim()) ? Number(text.trim()) : text.trim())
const parseNumber = (text: string) => (text.trim() === "" ? null : Number(text))

/** A time as it's typed: empty is none, a number is minutes, else a phrase ("6s", "1d"). */
export const parseSpan = (text: string): number | string | null => (text.trim() === "" ? null : /^\d+(\.\d+)?$/.test(text.trim()) ? Number(text) : text.trim())

const SPANS = [["second", 1 / 60, "s"], ["minute", 1, ""], ["hour", 60, "h"], ["day", 1440, "d"], ["month", 43200, ""], ["year", 525600, ""]] as const
type Unit = (typeof SPANS)[number][0]

/** A time as a number and a unit: "" is none, minutes a number, else a phrase ("6s", "1d"). */
const unitOf = (text: string): { n: string; unit: Unit } => {
  const t = text.trim()
  const said = t.match(/^(\d+(?:\.\d+)?)\s*(s|min|h|d)$/)
  if (said) return { n: said[1], unit: ({ s: "second", min: "minute", h: "hour", d: "day" } as const)[said[2] as "s" | "min" | "h" | "d"] }
  if (!/^\d+(\.\d+)?$/.test(t)) return { n: t, unit: "minute" }
  const m = Number(t)
  const whole = [...SPANS].reverse().find(([, size]) => size >= 1 && m % size === 0)
  return whole ? { n: String(m / whole[1]), unit: whole[0] } : { n: String(m * 60), unit: "second" }
}

/** A number and a unit, as the text the engine reads (the longer units as minutes). */
const spanOf = (n: string, unit: Unit) => {
  if (n.trim() === "") return ""
  const [, size, mark] = SPANS.find(([u]) => u === unit)!
  return mark ? `${n.trim()}${mark}` : String(Number(n) * size)
}

/** How long something is kept: a number and a unit to pick, changed where they're read, held with the dialog's Save.
 * `name`: its key in what's held; `was`: the span as kept (the engine's text); `editable`: none, read only. */
export function SpanField({ label, name, was, editable }: { label: string; name: string; was: string; editable: boolean }) {
  const st   = useStaged()
  const kept = (() => { const u = unitOf(was); return spanOf(u.n, u.unit) })()
  const now  = unitOf((st?.patch[name] as string | undefined) ?? was)
  const put  = (text: string) => st?.put(name, text, kept)
  return (
    <span className="flex items-baseline gap-2 whitespace-nowrap">
      <span className="w-11 shrink-0">
        <Editable label={label} placeholder="none" changed={!!st?.lit(name)} value={now.n} className="block w-full rounded-md bg-muted px-1 py-0.5 text-center"
                  onSave={editable ? async (t) => /^(\d+(\.\d+)?)?$/.test(t.trim()) ? (put(spanOf(t, now.n === "" ? "minute" : now.unit)), null) : "A number" : undefined} />
      </span>
      {now.n !== "" && (
        <Pick label="Unit" value={now.unit} changed={!!st?.lit(name)} arrow={editable} options={SPANS.map(([u]) => [u, u])}
              onPick={editable ? (u) => put(spanOf(now.n, u as Unit)) : undefined}>
          {now.unit}{now.n === "1" ? "" : "s"}
        </Pick>
      )}
    </span>
  )
}

// --- the form, and its fields ---------------------------------------------------------------

/** A form: its fields, then Save and Cancel, and the mistake the last save made. */
function Form({ children, onSave, onCancel, saveLabel = "Save", plain, onDirty }: {
  children: ReactNode
  onSave: () => Promise<string | null>
  onCancel: () => void
  saveLabel?: string
  plain?: boolean  // no box of its own: in a panel already
  onDirty?: () => void  // as it's first changed
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const form = useRef<HTMLFormElement>(null)
  const save = async () => {
    const was = form.current!.dataset.dirty
    delete form.current!.dataset.dirty  // what a save moves on to needn't ask
    setBusy(true)
    const mistake = await onSave()
    setBusy(false)
    setError(mistake ?? "")
    if (mistake && was && form.current) form.current.dataset.dirty = was
  }
  return (
    <form ref={form} className={cn("flex flex-col", plain ? "gap-4" : "gap-3", !plain && "rounded-lg border bg-muted/30 p-3")} onSubmit={(e) => { e.preventDefault(); save() }}
          onChange={(e) => (e.currentTarget.dataset.dirty = "yes", onDirty?.())}
          onKeyDown={(e) => e.key === "Escape" && !e.defaultPrevented && (e.preventDefault(), !e.currentTarget.dataset.dirty && onCancel())}>
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
function Field({ label, hint, group, children, className }: { label: string; hint?: string; group?: boolean; children: ReactNode; className?: string }) {
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
  if (names || code) return <CodeInput value={value} onChange={(e) => onChange(e.target.value)} list={names ? NAMES : undefined} className="h-8 text-xs" {...props} />
  return <Input value={value} onChange={(e) => onChange(e.target.value)} className={cn("h-8 text-sm", code && "font-mono text-xs")} spellCheck={!code} {...props} />
}

function Choice({ value, onChange, options, className }: {
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

// --- a program, a state, a way out ----------------------------------------------------------

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
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Take it out" onClick={() => onChange(values.filter((_, j) => j !== i))}><Trash2 /></Button>
        </div>
      ))}
      <Button type="button" size="sm" variant="outline" className="w-fit" onClick={() => onChange([...values, ""])}><Plus /> {add}</Button>
    </div>
  )
}

// --- an action ------------------------------------------------------------------------------

type Params = Record<string, unknown>
export type Picks = { image: string[]; sound: string[] }  // an action's pictures and sounds, by kind

/** An action: its kind (chosen when it's new), its name (its kind's, until you change it) and
 *  what it's for, then its params, as the kind takes them, and a poke's or a question's picks.
 *  Its id is made from where it is and its name as it's added ("bedtime.poking.bedtime"). */
export function ActionForm({ spec, at, taken, onSave, onCancel, onDirty }: {
  spec?: { id: string; name: string; desc: string; kind: string; params: Params }
  at: { program: string; state: string }
  taken: string[]  // its state's actions' names
  onSave: Save
  onCancel: () => void
  onDirty?: () => void
}) {
  const [kind, setKind] = useState(spec?.kind ?? "poke")
  const [name, setName] = useState(spec?.name ?? free("poke", taken))  // never shown: only the engine's key for it
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
  const save = async () => {
    const mistake = await onSave({ name, desc: spec ? spec.desc : desc, kind, params: cleaned(kind, params) })  // yours, in its dialog, is changed there
    if (mistake || !picked || !shown) return mistake
    const answer = await window.proki.tool("set_picks", { id, keys: [...picks.image, ...picks.sound] })
    return answer.error ? `Saved, but its pictures and sounds weren't: ${answer.error}` : null
  }
  return (
    <Form onCancel={onCancel} onSave={save} plain onDirty={onDirty}>
      {!spec && (
        <DialogHeader>
          <DialogTitle>
            <Pick label="Kind" value={kind} arrow className="gap-2 text-base"
                  options={Object.entries(ACTIONS).map(([k, [said, Icon, tint]]) => [k, <><Tinted icon={Icon} tint={tint} />{said}</>])}
                  onPick={(k) => { if (name === free(kind, taken)) setName(free(k, taken)); setKind(k); setParams({}) }} />
          </DialogTitle>
          <DialogDescription asChild><div><Editable label="Description" value={desc} long placeholder="No description" onSave={async (t) => (setDesc(t), null)} className="text-sm text-muted-foreground" /></div></DialogDescription>
        </DialogHeader>
      )}
      {kind in ACTION_ROWS && <ActionRows kind={kind} field={rowField(params, set)} />}
      {kind === "poke" && <PopupFields kind={kind} params={params} commit={async (patch) => (Object.entries(patch).forEach(([k, v]) => set(k, v)), null)} picks={picks} pick={pick} />}
      {kind === "ask_jev" && <JevFields params={params} set={set} />}
      {ASKS.includes(kind) && kind !== "ask_jev" && <AskFields kind={kind} params={params} set={set} picks={picks} pick={pick} at={at} />}
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
export function cleaned(kind: string, params: Params): Params {
  const kept = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== "" && !(Array.isArray(v) && v.length === 0)))
  if (kind === "open" && !kept.path) kept.path = "'today'"
  if (kind === "ask_llm") delete kept.schema  // it answers as its variable is typed
  if (kept.context && typeof kept.context === "object") {  // what fills its text: a name each, one with no name left out
    const { format, values } = contextOf(kept.context)
    const filled = values.filter(([name]) => name.trim())
    if (filled.length) kept.context = { format, values: Object.fromEntries(filled) }
    else if (format) kept.context = format
    else delete kept.context
  }
  if (kept.fields) kept.fields = Object.fromEntries(Object.entries(kept.fields as Record<string, string>).filter(([k]) => k.trim()))
  if ((kind === "set" || kind === "add" || kind === "sub") && !("expr" in kept)) kept.expr = null
  return kept
}

export type Pair = [string, string]

/** What's said, as the popup shows it: its text with {name}s filled from expressions. */
export const contextOf = (value: unknown) => {
  const context = typeof value === "string" ? { format: value, values: {} } : (value as { format?: string; values?: Record<string, string> | Pair[] }) ?? {}
  return { format: context.format ?? "", values: (Array.isArray(context.values) ? context.values : Object.entries(context.values ?? {})) as Pair[] }
}

/** What's new in `now` (a flag each), and where something of `was` isn't any more (the place among `now` it was at). */
function compared(was: string[], now: string[]) {
  const left  = [...was]
  const added = now.map((n) => { const j = left.indexOf(n); return j < 0 || !left.splice(j, 1) })
  const kept  = [...now]
  const gone: { at: number; label: string }[] = []
  let at = 0
  for (const w of was) {
    const j = kept.indexOf(w)
    if (j < 0) gone.push({ at, label: w })
    else (kept[j] = "\u0000", at++)
  }
  return { added, gone }
}

/** A red arrow in a table's margin, where what's listed was taken out. */
const Gone = ({ labels, className }: { labels: string[]; className: string }) => (
  <span title={`Taken out: ${labels.join(", ") || "an empty row"}`} className={cn("absolute -left-[5px] z-10 text-removed", className)}><Play aria-hidden className="size-2.5 fill-current" /></span>
)

/** A table's row trash, there as you point at the row. */
const Out = ({ label, onClick, className }: { label: string; onClick: () => void; className?: string }) => (
  <Button type="button" size="icon-xs" variant="ghost" aria-label={label} title="Take it out" onClick={onClick}
          className={cn("text-destructive opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100", className)}><Trash2 /></Button>
)

/** What's said, a text with {name}s, read as it's typed: the slots coloured as Python reads a format string. */
function TemplateField({ value, onChange, placeholder, changed }: { value: string; onChange: (text: string) => void; placeholder: string; changed?: boolean }) {
  return <Template value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label="Text" className={cn(changed && CHANGED_LINE)} />
}

/** An expression, typed where it's read, coloured as Python is. */
function ExprField({ label, value, placeholder, onChange, changed }: { label: string; value: string; placeholder: string; onChange: (text: string) => void; changed?: boolean }) {
  return <CodeInput aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} list={NAMES} layout="min-w-40 flex-1" placeholder={placeholder} className={cn(BARE, changed && CHANGED_LINE)} />
}

/** What fills a text's {name}s, as a table like the resource dialog's: a name, then the expression it stands for, a row
 * each, typed where they're read; a row's trash is there as you point at it. `was`: what it was, to mark what's changed. */
export function Placeholders({ pairs, was, onChange }: { pairs: Pair[]; was?: Pair[]; onChange: (pairs: Pair[]) => void }) {
  const diff = was && compared(was.map(([k]) => k), pairs.map(([k]) => k))
  const put  = (i: number, at: 0 | 1, text: string) => onChange(pairs.map((p, j) => (j !== i ? p : at ? [p[0], text] : [text, p[1]]) as Pair))
  const lost = (at: number) => diff?.gone.filter((g) => g.at === at).map((g) => g.label) ?? []
  const ROW  = "grid grid-cols-[8rem_minmax(0,1fr)] items-center gap-3 px-2 py-2.5 pr-9"
  return (
    <section className="flex flex-col gap-1.5 border-t pt-4 text-xs">
      <div className="flex items-center justify-between">
        <span className="font-medium">Placeholders</span>
        <Button type="button" size="xs" variant="ghost" className="-mr-2 text-muted-foreground" onClick={() => onChange([...pairs, ["", ""]])}><Plus /> Add</Button>
      </div>
      {pairs.length === 0 ? <span className="text-muted-foreground">None.</span> : (
        <div className="relative rounded-md border">
          {pairs.map(([key, expr], i) => {
            const old = was?.find(([k]) => k === key)
            return (
              <div key={i} className={cn("group/row relative border-b last:border-b-0", diff?.added[i] && "bg-added/10")}>
                {lost(i).length > 0 && <Gone labels={lost(i)} className="-top-[5px]" />}
                <div className={ROW}>
                  <CodeInput aria-label="Placeholder name" value={key} placeholder="name" layout="w-full" className={BARE} render={(t) => <span className="text-code-slot">{t}</span>} onChange={(e) => put(i, 0, e.target.value)} />
                  <CodeInput aria-label="Placeholder expression" value={expr} list={NAMES} placeholder="shallow_today / 60" layout="w-full" className={cn(BARE, old && old[1] !== expr && CHANGED_LINE)} onChange={(e) => put(i, 1, e.target.value)} />
                </div>
                <Out label={`Take out ${key || "the placeholder"}`} className="absolute top-1/2 right-1.5 -translate-y-1/2" onClick={() => onChange(pairs.filter((_, j) => j !== i))} />
              </div>
            )
          })}
          {lost(pairs.length).length > 0 && <Gone labels={lost(pairs.length)} className="-bottom-[5px]" />}
        </div>
      )}
    </section>
  )
}

/** A choice's options, as a table like the placeholders': its number, then its label, typed where it's read; the one
 * `preselected` has a mark at its end, and clicking another's moves it. `was`: what it was, to mark what's changed. */
function OptionsTable({ options, was, preselected, preselectChanged, onChange }: {
  options: string[]
  was?: string[]
  preselected?: number
  preselectChanged?: boolean
  onChange: (options: string[], preselected: number | undefined) => void
}) {
  const diff = was && compared(was, options)
  const lost = (at: number) => diff?.gone.filter((g) => g.at === at).map((g) => g.label) ?? []
  const take = (i: number) => onChange(options.filter((_, j) => j !== i), preselected === undefined || preselected === i ? undefined : preselected > i ? preselected - 1 : preselected)
  return (
    <div className="relative rounded-md border text-xs">
      {options.map((label, i) => (
        <div key={i} className={cn("group/row relative border-b last:border-b-0", preselected === i && "bg-muted/50", diff?.added[i] && "bg-added/10")}>
          {lost(i).length > 0 && <Gone labels={lost(i)} className="-top-[5px]" />}
          <div className="grid grid-cols-[2rem_minmax(0,1fr)] items-center gap-3 px-2 py-2.5 pr-16">
            <span className="text-muted-foreground tabular-nums">{i}</span>
            <Input aria-label={`Option ${i}`} value={label} placeholder="Label" className={BARE} onChange={(e) => onChange(options.map((o, j) => (j === i ? e.target.value : o)), preselected)} />
          </div>
          <span className="absolute top-1/2 right-1.5 flex -translate-y-1/2 items-center">
            <Out label={`Take out option ${i}`} onClick={() => take(i)} />
            <Button type="button" size="icon-xs" variant="ghost" aria-label={preselected === i ? "Preselected: click to clear" : `Preselect option ${i}`} title={preselected === i ? "Preselected" : "Preselect"}
                    onClick={() => onChange(options, preselected === i ? undefined : i)}
                    className={cn(preselected === i ? cn("text-primary", preselectChanged && "shadow-[0_2px_0_0_var(--color-changed)]") : "text-muted-foreground opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100")}>
              <CircleCheck />
            </Button>
          </span>
        </div>
      ))}
      {options.length === 0 && <span className="block px-2 py-1.5 text-muted-foreground">None.</span>}
      {lost(options.length).length > 0 && <Gone labels={lost(options.length)} className="-bottom-[5px]" />}
    </div>
  )
}

/** What a jev's or an LLM's question reads: its text and what fills it. */
function ContextField({ value, onChange }: { value: unknown; onChange: (value: unknown) => void }) {
  const { format, values } = contextOf(value)
  return (
    <div className="flex flex-col gap-3">
      <TemplateField value={format} onChange={(t) => onChange({ format: t, values })} placeholder="{h:.1f} h shallow so far. Start a session?" />
      <Placeholders pairs={values} onChange={(next) => onChange({ format, values: next })} />
    </div>
  )
}

/** A poke or a question to you, laid out as the popup is, each part changed where it's read: pictures and a
 * sound beside its title and text, what fills its text, and (`ask`) the question's settings and options.
 * `commit`: the params changed (a key's value undefined: taken out), the mistake if any. Under a dialog's
 * `Staging`, every change waits there, marked, for its Save; a kind of question left is remembered, to come back to. */
export function PopupFields({ ask, kind, params, commit, picks, pick }: {
  ask?: boolean
  kind: string
  params: Params
  commit: (patch: Params) => Promise<string | null>
  picks: Picks
  pick: (which: keyof Picks, keys: string[]) => void
}) {
  const staged  = useStaged()  // in a dialog that keeps what's changed with its Save; else it's kept as it's changed
  const shown   = staged ? { ...params, ...staged.patch } : params
  const was     = contextOf(params.context)
  const { format, values } = contextOf(shown.context)
  const options = shown.options as string[] | string | undefined
  type Source = "static" | "dynamic"
  type Left = { options: string[] | string; default: unknown }
  const left   = useRef<{ static?: Left; dynamic?: Left }>({})  // each kind's options and pick, from when it was left
  const kindOf = (o: unknown): Source | null => (o === undefined ? null : Array.isArray(o) ? "static" : "dynamic")
  const source = kindOf(options)
  const lit    = (key: string) => !!staged?.lit(key)
  const choose = (patch: Params): Promise<string | null> => {
    if (!staged) return commit(patch)
    Object.entries(patch).forEach(([key, value]) => staged.put(key, value, key === "context" ? { format: was.format, values: was.values } : params[key]))
    return Promise.resolve(null)
  }
  const put = (nextFormat: string, nextValues: Pair[]) => void choose({ context: { format: nextFormat, values: nextValues } })
  const to = (next: Source | null) => {  // text (null), or a choice from a list of either kind
    if (source) left.current[source] = { options: options as Left["options"], default: shown.default }
    const back = next && (left.current[next] ?? { options: next === "static" ? [""] : "", default: undefined })
    void choose({ options: back?.options, default: back?.default })
  }
  const saved = kindOf(params.options)
  return (
    <>
      <section className="flex gap-4 border-t pt-4">
        <div className="flex w-36 shrink-0 flex-col gap-2">
          <Pictures keys={picks.image} onChange={(keys) => pick("image", keys)} />
          <Sounds keys={picks.sound} onChange={(keys) => pick("sound", keys)} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <Editable label="Title" value={String(shown.title ?? "")} placeholder="Title" changed={lit("title")} className="pb-1 text-lg font-medium"
                    onSave={(t) => choose({ title: t.trim() || undefined })} />
          <TemplateField value={format} changed={lit("context") && format !== was.format} onChange={(t) => put(t, values)} placeholder={ask ? "What do you want to ask?" : "Nothing said"} />
        </div>
      </section>
      <Placeholders pairs={values} was={staged ? was.values : undefined} onChange={(next) => put(format, next)} />
      {ask && (
        <>
          <section className="grid grid-cols-2 gap-x-6 border-t pt-4">
            <Line label="Answer">
              <Pick label="Answer" value={source ? "choice" : "text"} changed={!!staged && !!source !== !!saved} options={[["choice", "Choice"], ["text", "Text"]]}
                    onPick={(v) => to(v === "text" ? null : left.current.static ? "static" : left.current.dynamic ? "dynamic" : "static")} />
            </Line>
            <Line label="Save to"><ExprField label="Save to" value={String(shown.result ?? "")} placeholder="answer" changed={lit("result")} onChange={(t) => void choose({ result: t.trim() ? t : undefined })} /></Line>
            <Line label="Timeout">
              <Editable label="Timeout" value={shown.timeout == null ? "" : String(shown.timeout)} placeholder={String(TIMEOUT[kind])} changed={lit("timeout")}
                        onSave={async (t) => (await choose({ timeout: parseNumber(t) ?? undefined }))} /> s
            </Line>
            <Line label="Deferrable">
              <Checkbox checked={shown.immediate !== true} onCheckedChange={(on) => void choose({ immediate: on === true ? undefined : true })} className={cn(lit("immediate") && "border-changed")} />
            </Line>
          </section>
          {source && (
            <section className="flex flex-col gap-1.5 border-t pt-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="font-medium">Options</span>
                  <Pick label="Options from" value={source} changed={!!staged && source !== saved} options={[["static", "Static list"], ["dynamic", "Dynamic list"]]} onPick={(v) => to(v as Source)} />
                </span>
                {source === "static" && <Button type="button" size="xs" variant="ghost" className="-mr-2 text-muted-foreground" onClick={() => void choose({ options: [...(options as string[]), ""] })}><Plus /> Add</Button>}
              </div>
              {source === "static" ? (
                <>
                  <OptionsTable options={options as string[]} was={staged && saved === "static" ? (params.options as string[]) : undefined}
                                preselected={typeof shown.default === "number" ? shown.default : undefined} preselectChanged={lit("default")}
                                onChange={(next, preselected) => void choose({ options: next, default: preselected })} />
                  {typeof shown.default === "string" && (
                    <Line label="Preselect"><ExprField label="Preselect" value={shown.default} placeholder="an option or its number" changed={lit("default")} onChange={(t) => void choose({ default: t.trim() ? t : undefined })} /></Line>
                  )}
                </>
              ) : (
                <>
                  <Line label="From"><ExprField label="Options" value={String(options ?? "")} placeholder="track.labels" changed={lit("options") && saved === "dynamic"} onChange={(t) => void choose({ options: t })} /></Line>
                  <Line label="Preselect"><ExprField label="Preselect" value={String(shown.default ?? "")} placeholder="an option or its number" changed={lit("default")} onChange={(t) => void choose({ default: t.trim() ? t : undefined })} /></Line>
                </>
              )}
            </section>
          )}
        </>
      )}
    </>
  )
}

/** A label and what it sets, on a line. */
const Line = ({ label, children }: { label: string; children: ReactNode }) => (
  <label className="flex min-h-8 items-center gap-2 text-sm"><span className="w-20 shrink-0 text-muted-foreground">{label}</span>{children}</label>
)

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
                    onClick={() => set("questions", questions.filter((_, j) => j !== i))}><Trash2 /></Button>
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

/** A question, as its kind takes it: to you (laid out as the popup is, its settings and options under
 *  it), to the LLM (what it reads; it answers as the variable it's saved to is typed). */
function AskFields({ kind, params, set, picks, pick, at }: {
  kind: string
  at: { program: string; state: string }
  params: Params
  set: (key: string, value: unknown) => void
  picks: Picks
  pick: (which: keyof Picks, keys: string[]) => void
}) {
  useEffect(() => {
    if (params.result === undefined) set("result", "answer")
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  if (kind === "ask_usr") return <PopupFields ask kind={kind} params={params} commit={async (patch) => (Object.entries(patch).forEach(([k, v]) => set(k, v)), null)} picks={picks} pick={pick} />
  return (
    <>
      <ContextField value={params.context} onChange={(v) => set("context", v)} />
      <div className="grid grid-cols-2 gap-x-8 border-t pt-4">
        <Line label="Target"><CodeInput value={String(params.result ?? "")} onChange={(e) => set("result", e.target.value)} list={NAMES} layout="flex-1" className="h-7 text-xs" placeholder="answer" /></Line>
        <Line label="Timeout">
          <Input value={params.timeout == null ? "" : String(params.timeout)} onChange={(e) => set("timeout", parseNumber(e.target.value) ?? undefined)}
                 type="number" min={1} placeholder={String(TIMEOUT[kind])} className="h-7 w-16 text-xs" /> s
        </Line>
      </div>
      <Answered name={String(params.result ?? "")} at={at} />
    </>
  )
}

/** Keys of the media library, found for what's shown of them. */
function useItems(keys: string[]) {
  const [items, setItems] = useState<MediaItem[]>([])
  useEffect(() => {
    if (!keys.length) return setItems([])
    window.proki.tool("get_media", { keys }).then((answer) => !answer.error && setItems(answer.media))
  }, [keys.join("\n")])  // eslint-disable-line react-hooks/exhaustive-deps
  return items
}

/** A poke's pictures: every one in the pool as a thumbnail in a box of one size, scrolling, with Add under them (a big
 * plus when there are none); a click chooses in the library's window. */
function Pictures({ keys, onChange }: { keys: string[]; onChange: (keys: string[]) => void }) {
  const [picking, setPicking] = useState(false)
  const items = useItems(keys)
  return (
    <>
      {items.length === 0 ? (
        <button type="button" onClick={() => setPicking(true)} title="Add pictures"
                className="flex h-40 w-full flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed bg-muted/40 text-xs text-muted-foreground hover:bg-muted">
          <Plus className="size-6" />Add pictures
        </button>
      ) : (
        <div className="flex h-40 w-full flex-col overflow-hidden rounded-xl border bg-muted/40">
          <div className="grid min-h-0 flex-1 grid-cols-4 content-start gap-1.5 overflow-y-auto p-1.5">
            {items.map((item) => (
              <button key={item.key} type="button" onClick={() => setPicking(true)} title={item.name} className="aspect-square rounded-md hover:bg-muted">
                <img src={file(item.file)} alt={item.name} className="size-full object-contain" />
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setPicking(true)} className="flex shrink-0 items-center justify-center gap-1 border-t py-1.5 text-xs text-muted-foreground hover:bg-muted">
            <Plus className="size-3.5" />Add pictures
          </button>
        </div>
      )}
      {picking && <MediaPicker kind="image" keys={keys} onClose={() => setPicking(false)} onDone={(next) => { onChange(next); setPicking(false) }} />}
    </>
  )
}

/** A poke's sounds: one button, saying how many there are. */
function Sounds({ keys, onChange }: { keys: string[]; onChange: (keys: string[]) => void }) {
  const [picking, setPicking] = useState(false)
  return (
    <>
      <Button type="button" size="sm" variant="outline" className="w-full text-muted-foreground" onClick={() => setPicking(true)}>
        <Music /> {keys.length ? (keys.length === 1 ? "1 sound" : `${keys.length} sounds`) : "Add sound"}
      </Button>
      {picking && <MediaPicker kind="sound" keys={keys} onClose={() => setPicking(false)} onDone={(next) => { onChange(next); setPicking(false) }} />}
    </>
  )
}
