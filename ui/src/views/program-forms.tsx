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
import type { MediaItem, StateSpec } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { BARE, CodeInput } from "@/views/code"
import { KindTabs, OptionsFrom } from "@/views/fields"
import { CHANGED_LINE, Editable, Pick, useStaged } from "@/views/in-place"
import { file, MediaPicker } from "@/views/media"
import { ActionRows, ACTION_ROWS, NAMES, RowFields, rowField } from "@/views/action-rows"
import { AskJev, AskLlm, LABELS, PromptBox, PromptRows, START, Waiting } from "@/views/ask-actions"

export { NAMES }


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

// --- a program, a state, a way out ----------------------------------------------------------

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
  const save = () => onSave({ name, desc: spec ? spec.desc : desc, kind, params: cleaned(kind, params), ...(picked && shown ? { picks } : {}) })  // yours, in its dialog, is changed there; the picks are kept with the rest
  return (
    <Form onCancel={onCancel} onSave={save} plain onDirty={onDirty}>
      {!spec && (
        <DialogHeader>
          <DialogTitle>
            <Pick label="Kind" value={kind} arrow className="gap-2 text-base"
                  options={Object.entries(ACTIONS).map(([k, [said, Icon, tint]]) => [k, <><Tinted icon={Icon} tint={tint} />{said}</>])}
                  onPick={(k) => { if (name === free(kind, taken)) setName(free(k, taken)); setKind(k); setParams(START[k] ?? {}) }} />
          </DialogTitle>
          <DialogDescription asChild><div><Editable label="Description" value={desc} long placeholder="No description" onSave={async (t) => (setDesc(t), null)} className="text-sm text-muted-foreground" /></div></DialogDescription>
        </DialogHeader>
      )}
      {kind in ACTION_ROWS && <ActionRows kind={kind} field={rowField(params, set)} />}
      {kind === "poke" && <PopupFields kind={kind} params={params} commit={async (patch) => (Object.entries(patch).forEach(([k, v]) => set(k, v)), null)} picks={picks} pick={pick} />}
      {kind === "ask_usr" && <PopupFields ask kind={kind} params={params} commit={async (patch) => (Object.entries(patch).forEach(([k, v]) => set(k, v)), null)} picks={picks} pick={pick} />}
      {kind === "ask_llm" && <AskLlm params={params} put={set} at={at} />}
      {kind === "ask_jev" && <AskJev params={params} put={set} />}
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

/** A choice's options, as a table: its number (Index), then its label, typed where it's read; the one
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
      <div className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3 border-b bg-muted/40 py-1 pr-16 pl-2 text-muted-foreground"><span>Index</span><span>Label</span></div>
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

/** A poke or a question to you, laid out as the popup is, each part changed where it's read: pictures and a
 * sound beside its title and text, what fills its text, and (`ask`) the question's settings and options.
 * `commit`: the params changed (a key's value undefined: taken out), the mistake if any. Under a dialog's
 * `Staging`, every change waits there, marked, for its Save; a kind of question left is remembered, to come back to. */
export function PopupFields({ ask, kind, params, commit, picks, saved: savedPicks, pick }: {
  ask?: boolean
  saved?: Picks  // the pictures and sounds as kept, to mark a change
  kind: string
  params: Params
  commit: (patch: Params) => Promise<string | null>
  picks: Picks
  pick: (which: keyof Picks, keys: string[]) => void
}) {
  const staged  = useStaged()  // in a dialog that keeps what's changed with its Save; else it's kept as it's changed
  const shown   = staged ? { ...params, ...staged.patch } : params
  const was     = contextOf(params.context)
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
  const to = (next: Source | null) => {  // text (null), or a choice from a list of either kind
    if (source) left.current[source] = { options: options as Left["options"], default: shown.default }
    const back = next && (left.current[next] ?? { options: next === "static" ? [""] : "", default: undefined })
    void choose({ options: back?.options, default: back?.default })
  }
  const saved = kindOf(params.options)
  const text  = (key: string) => ({ value: String(shown[key] ?? ""), changed: lit(key), onSave: async (t: string) => (void choose({ [key]: t.trim() || undefined }), null), onType: (t: string) => void choose({ [key]: t.trim() || undefined }) })
  return (
    <>
      <section className="flex gap-4 border-t pt-4">
        <div className="flex w-32 shrink-0 flex-col gap-2">
          <Pictures keys={picks.image} changed={!!savedPicks && JSON.stringify(picks.image) !== JSON.stringify(savedPicks.image)} onChange={(keys) => pick("image", keys)} />
          <Sounds keys={picks.sound} changed={!!savedPicks && JSON.stringify(picks.sound) !== JSON.stringify(savedPicks.sound)} onChange={(keys) => pick("sound", keys)} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium">Title</span>
            <Input aria-label="Title" value={String(shown.title ?? "")} placeholder="Title" className={cn("h-8 text-sm", lit("title") && CHANGED_LINE)} onChange={(e) => void choose({ title: e.target.value || undefined })} />
          </div>
          <PromptBox label="Content" params={{ context: shown.context }} was={staged ? { context: params.context } : undefined} put={(_, v) => void choose({ context: v })} placeholder={ask ? "What do you want to ask?" : "Nothing said"} min="min-h-16" />
        </div>
      </section>
      <PromptRows params={{ context: shown.context }} was={staged ? { context: params.context } : undefined} put={(_, v) => void choose({ context: v })} />
      {ask && (
        <div className="flex flex-col gap-4 border-t pt-4">
          <KindTabs kind={source ? "choice" : "text"} kinds={["text", "choice"]} changed={!!staged && !!source !== !!saved}
                    onPick={(v) => to(v === "text" ? null : left.current.static ? "static" : left.current.dynamic ? "dynamic" : "static")} />
          {source && (
            <section className="flex flex-col gap-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <span className="font-medium">Options</span>
                  <OptionsFrom value={source === "static" ? "user" : "expr"} changed={!!staged && source !== saved} onPick={(v) => to(v === "user" ? "static" : "dynamic")} />
                </span>
                {source === "static" && <Button type="button" size="xs" variant="ghost" className="-mr-2 text-muted-foreground" onClick={() => void choose({ options: [...(options as string[]), ""] })}><Plus /> Add</Button>}
              </div>
              {source === "static" ? (
                <>
                  <OptionsTable options={options as string[]} was={staged && saved === "static" ? (params.options as string[]) : undefined}
                                preselected={typeof shown.default === "number" ? shown.default : undefined} preselectChanged={lit("default")}
                                onChange={(next, preselected) => void choose({ options: next, default: preselected })} />
                  {typeof shown.default === "string" && <RowFields rows={[["Preselect", "default", "text"]]} hints={{ default: "an option or its number" }} label={LABELS} field={(k) => text(k)} />}
                </>
              ) : (
                <RowFields rows={[["From", "options", "text"], ["Preselect", "default", "text"]]} hints={{ options: "track.labels", default: "an option or its number" }} label={LABELS} field={(k) => text(k)} />
              )}
            </section>
          )}
          <Waiting params={shown} put={(k, v) => void choose({ [k]: v })} wait={TIMEOUT[kind]} was={staged ? params : undefined} />
          <div style={{ gridTemplateColumns: `${LABELS} minmax(0,1fr)` }} className="grid items-center gap-x-3 text-xs">
            <span className="pl-0 text-muted-foreground">Deferrable</span>
            <Checkbox checked={shown.immediate !== true} onCheckedChange={(on) => void choose({ immediate: on === true ? undefined : true })} className={cn(lit("immediate") && "border-changed")} />
          </div>
        </div>
      )}
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

/** A poke's pictures: the pool as a box of one size holding nine, a click on it chooses in the library's window (a big plus when there are none;
 * past nine, the ninth cell says there are more). */
function Pictures({ keys, changed, onChange }: { keys: string[]; changed?: boolean; onChange: (keys: string[]) => void }) {
  const [picking, setPicking] = useState(false)
  const items = useItems(keys)
  const more  = items.length > 9
  return (
    <>
      <button type="button" onClick={() => setPicking(true)} title={items.length ? "Choose pictures" : "Add pictures"} aria-label="Pictures"
              className={cn("size-32 shrink-0 overflow-hidden rounded-xl border bg-muted/40 hover:bg-muted", changed && "border-solid border-changed", items.length === 0 && "flex flex-col items-center justify-center gap-1.5 border-dashed text-xs text-muted-foreground")}>
        {items.length === 0 ? <><Plus className="size-6" />Add pictures</> : (
          <span className="grid size-full grid-cols-3 grid-rows-3 gap-1 p-1.5">
            {items.slice(0, more ? 8 : 9).map((item) => <img key={item.key} src={file(item.file)} alt={item.name} className="size-full rounded-sm object-contain" />)}
            {more && <span className="flex items-center justify-center text-sm text-muted-foreground">…</span>}
          </span>
        )}
      </button>
      {picking && <MediaPicker kind="image" keys={keys} onClose={() => setPicking(false)} onDone={(next) => { onChange(next); setPicking(false) }} />}
    </>
  )
}

/** A poke's sounds: a bar as wide as the pictures' box, saying how many there are. */
function Sounds({ keys, changed, onChange }: { keys: string[]; changed?: boolean; onChange: (keys: string[]) => void }) {
  const [picking, setPicking] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setPicking(true)} aria-label="Sounds"
              className={cn("flex h-8 w-32 shrink-0 items-center justify-center gap-1.5 overflow-hidden rounded-xl border bg-muted/40 text-xs whitespace-nowrap text-muted-foreground hover:bg-muted", changed && "border-changed")}>
        <Music className="size-3.5 shrink-0" /><span className="truncate">{keys.length ? (keys.length === 1 ? "1 sound" : `${keys.length} sounds`) : "Add sound"}</span>
      </button>
      {picking && <MediaPicker kind="sound" keys={keys} onClose={() => setPicking(false)} onDone={(next) => { onChange(next); setPicking(false) }} />}
    </>
  )
}
