// Shared source chips, schema controls, and field rows.

import { useState, type KeyboardEvent } from "react"
import { Bot, Box, Brackets, ChartLine, CircleHelp, Clock, Hash, KeySquare, PawPrint, Radical, Scale, Sigma, ToggleRight, Trash2, Type as TextIcon, User, Variable, Workflow, X, type LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import type { Source, SourceName, Type } from "@/lib/proki"
import { CHANGED, Drafted, Editable, Pick, PLAIN, Term, typing, useStaged } from "@/views/in-place"
import { BARE } from "@/views/code"
import { AddButton } from "@/views/scope-shared"


export const SOURCES: Record<SourceName, { means: string; icon: LucideIcon; chip: string; fresh: Source }> = {
  expr:    { means: "Computed from other fields", icon: Sigma,     chip: "tint-sky",
             fresh: { from: "expr", expr: "" } },
  jev:     { means: "Asked to jev", icon: KeySquare, chip: "tint-violet",
             fresh: { from: "jev", type: "noul", question: "" } },
  llm:     { means: "Asked to the LLM",           icon: Bot,       chip: "tint-amber",
             fresh: { from: "llm", context: "" } },
  user:    { means: "Set by you, per record",     icon: User,      chip: "tint-emerald", fresh: { from: "user" } },
  auto:    { means: "Set by a program",           icon: Workflow,  chip: "tint-zinc", fresh: { from: "auto" } },
}

/** A question's kind as tabs, the one chosen raised. */
export function KindTabs({ kind, kinds, changed, onPick }: { kind: string; kinds: string[]; changed?: boolean; onPick: (kind: string) => void }) {
  return (
    <div role="tablist" className="grid gap-1 rounded-lg border bg-muted/40 p-1 text-xs" style={{ gridTemplateColumns: `repeat(${kinds.length}, minmax(0, 1fr))` }}>
      {kinds.map((k) => (
        <button key={k} type="button" role="tab" aria-selected={kind === k} onClick={() => k !== kind && onPick(k)}
                className={cn("rounded-md py-1 font-mono", kind === k ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground", changed && kind === k && CHANGED)}>
          {k}
        </button>
      ))}
    </div>
  )
}

export const ANSWERS: Record<string, [string, string][]> = {
  noul:   [["res", "number"]],
  choice: [["res.index", "integer"], ["res.conf", "number"], ["res.odds", "list"]],
  score:  [["res.score", "number"], ["res.conf", "number"], ["res.odds", "list"]],
}

/** Where a choice's options come from, picked from a menu as a field's sources are named: the chip `user` (you give a list) or `expr` (an expression
 * works it out). `changed`: not kept yet. */
export function OptionsFrom({ value, changed, onPick }: { value: "user" | "expr"; changed?: boolean; onPick: (value: "user" | "expr") => void }) {
  const tag = (n: "user" | "expr", means?: string) => (
    <span className="inline-flex items-center gap-2">
      <span className={cn(TAG, SOURCES[n].chip)}><Mark icon={SOURCES[n].icon} />{n}</span>
      {means && <span className="text-muted-foreground">{means}</span>}
    </span>
  )
  return (
    <Pick label="Options from" value={value} arrow changed={changed} onPick={(v) => onPick(v as "user" | "expr")}
          options={[["user", tag("user", "You give the list")], ["expr", tag("expr", "An expression works it out")]]}>
      {tag(value)}
    </Pick>
  )
}

/** A source as a chip, its icon before its name: what it means as you hover it (under a
 * TooltipProvider). */
export function Chip({ name, active, means, onClick, onRemove, ...drag }: {
  name: SourceName
  means?: string  // what it says as you hover it, where it isn't what the source is for a field
  active?: boolean
  onClick?: (e: React.MouseEvent) => void
  onRemove?: () => void
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span {...drag}
              className={cn(TAG, "cursor-pointer", SOURCES[name].chip, active && "ring-2 ring-ring/60", drag.draggable && "cursor-grab")}>
          {onClick ? <button type="button" onClick={onClick} onKeyDown={(e) => e.stopPropagation()} className="inline-flex items-center gap-1 rounded-sm">
            <Mark icon={SOURCES[name].icon} />{name}
          </button> : <><Mark icon={SOURCES[name].icon} />{name}</>}
          {onRemove && (
            <button type="button" aria-label={`remove ${name}`} onClick={(e) => (e.stopPropagation(), onRemove())}
                    className="-mr-1 rounded-full p-0.5 opacity-60 hover:opacity-100"><X className="size-2.5" /></button>
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top">{means ?? SOURCES[name].means}</TooltipContent>
    </Tooltip>
  )
}

/** A chip's look, and its icon: a source's, or what reads a name. */
export const TAG = "inline-flex h-5 items-center gap-1 rounded-full px-2 font-mono text-xs font-medium whitespace-nowrap select-none"

export const Mark = ({ icon: Icon }: { icon: LucideIcon }) => <Icon aria-hidden className="size-3 shrink-0" strokeWidth={2.25} />

export type Reader = keyof typeof READERS

const READERS = {  // what reads a name: its icon, its tint, what it means
  auto:     [Workflow,  SOURCES.auto.chip,                                      "Read by an automation: a transition's condition, or an action"],
  rule:     [Scale,     "tint-rose",       "Read by a rule, to work out its chance"],
  signal:   [ChartLine, "tint-cyan",       "Read by a signal, to work out its value"],
  variable: [Variable,  "tint-indigo", "Read by a variable, to start from"],
  proki:    [PawPrint,  "tint-violet", "Read by the app itself"],
} satisfies Record<string, [LucideIcon, string, string]>

/** A type, said; where the dialog stages (`editable`), its kind picked from a list as you point at it, and
 * what's inside it changed under it, both kept with the dialog's Save. `own`: the one you gave, if any. */
export function TypeChange({ type, own, editable, kinds = TYPES, at = "type" }: { type?: Type; own?: Type; editable?: boolean; kinds?: string[]; at?: string }) {
  const staged = useStaged()
  const was    = own ?? type ?? "any"
  const draft  = staged?.patch[at] as Type | undefined
  const now    = draft ?? was
  const name   = (t: Type | undefined) => <span style={{ color: `var(--type-${kindOf(t ?? "any")})` }}>{t && t !== "any" ? said(t) : "any"}</span>
  if (!editable || !staged) return name(type)
  return (
    <div className="flex flex-col gap-2">
      <Pick label="Type" value={kindOf(now)} changed={draft !== undefined} options={kinds.map((t) => [t, <><TypeIcon type={t} />{t}</>])}
            onPick={(k) => staged.put(at, typed(picked(k, schemaOf(now))), was)}>{name(now)}</Pick>
    </div>
  )
}

/** A list's item type, in a row of its own under Type (none for another type): picked like the type is, kept with the dialog's Save. */
export function ItemChange({ type, own, editable, at = "type" }: { type?: Type; own?: Type; editable?: boolean; at?: string }) {
  const staged = useStaged()
  const was    = own ?? type ?? "any"
  const now    = (staged?.patch[at] as Type | undefined) ?? was
  if (kindOf(now) !== "list") return null
  const schema = schemaOf(now)
  const items  = (schema.items ?? {}) as Schema
  const kind   = kindOf(items as Type)
  const name   = <span style={{ color: `var(--type-${kind})` }}>{kind}</span>
  return (
    <>
      <Term>Item</Term>
      <dd>
        <Pick label="Item" value={kind} changed={staged?.lit(at)} onPick={editable && staged ? (k) => staged.put(at, typed({ ...schema, items: picked(k, items) }), was) : undefined}
              options={TYPES.filter((t) => t !== "list").map((t) => [t, <><TypeIcon type={t} />{t}</>])}>{name}</Pick>
      </dd>
    </>
  )
}

/** jev's criteria as a table, in order: each label (a choice's option, a score's mark on its scale) and what it means. `fixed`: labels that are
 * given (a yes or no's), their meanings left as they are. */
export function Criteria({ criteria, label = "Options", placeholder = "high", fixed, onSet }: {
  criteria: Record<string, string | null>
  label?: string
  placeholder?: string
  fixed?: string[]
  onSet: (criteria: Record<string, string>) => void
}) {
  const [rows, setRows] = useState(fixed ? fixed.map((l): [string, string] => [l, ""]) : Object.entries(criteria).map(([l, means]): [string, string] => [l, means ?? ""]))
  const put = (next: [string, string][]) => (setRows(next), onSet(Object.fromEntries(next)))
  return (
    <div className="flex flex-col gap-1.5">
      <Heading text="Criteria" onAdd={fixed ? undefined : () => put([...rows, ["", ""]])} />
      <div className="rounded-md border">
        <div className="grid grid-cols-[8rem_minmax(0,1fr)_2rem] items-center gap-3 bg-muted/40 py-1 pr-1 pl-2 text-xs text-muted-foreground">
          <span>{fixed ? "Label" : label}</span><span>Meaning</span><span />
        </div>
        {rows.map(([name, means], i) => (
          <div key={i} className="grid grid-cols-[8rem_minmax(0,1fr)_2rem] items-center gap-3 border-t py-1 pr-1 pl-2">
            {fixed ? <span className="font-mono text-xs">{name}</span>
                   : <Input {...PLAIN} value={name} onChange={(e) => put(rows.map((r, j) => (j === i ? [e.target.value, r[1]] : r)))} placeholder={placeholder} className={cn(BARE, "font-mono")} />}
            {fixed ? <span className="text-xs text-muted-foreground">–</span>
                   : <Input value={means} onChange={(e) => put(rows.map((r, j) => (j === i ? [r[0], e.target.value] : r)))} placeholder="–" className={BARE} />}
            {!fixed && <Button variant="ghost" size="icon-xs" aria-label="remove" onClick={() => put(rows.filter((_, j) => j !== i))}><Trash2 /></Button>}
          </div>
        ))}
        {rows.length === 0 && <p className="px-2 py-1.5 text-xs text-muted-foreground">None.</p>}
      </div>
    </div>
  )
}

const TYPES = ["any", "number", "integer", "boolean", "string", "time", "object", "list"]

export const SCALARS = TYPES.slice(0, 6)  // the kinds that fit one value (a signal is one of them)

type Schema = Record<string, unknown>

const SCHEMAS: Record<string, Schema> = {
  any: {}, number: { type: "number" }, integer: { type: "integer" }, boolean: { type: "boolean" }, string: { type: "string" },
  time: { type: "number", format: "time" }, object: { type: "object", properties: {} }, list: { type: "array", items: {} },
}

/** A type's kind, as it's picked: its name, an object or a list (inherit: none, its own). */
export function kindOf(t: Type | undefined): string {
  if (t === undefined) return "inherit"
  if (typeof t === "string") return t === "array" || t.startsWith("list[") ? "list" : t in SCHEMAS ? t : "any"
  if (t.type === "array") return "list"
  if (t.type === "number" && t.format === "time") return "time"
  return typeof t.type === "string" && t.type in SCHEMAS ? t.type : "any"
}

/** A type as a schema, a short name as the one it stands for. */
export const schemaOf = (t: Type): Schema => (typeof t === "string" ? SCHEMAS[t === "array" ? "list" : t] ?? {} : t)

/** A schema of a kind, from the one it was: the same kind, as it was (its options, what's
 *  proki's); another, a fresh one, what it means kept. */
function picked(kind: string, old: Schema): Schema {
  if (kind === kindOf(old)) return old
  return { ...SCHEMAS[kind], ...(old.description ? { description: old.description } : {}) }
}

/** A schema as a type: a short name for the ones that have one. */
function typed(s: Schema): Type {
  const short = Object.entries(SCHEMAS).find(([k, v]) => k !== "object" && k !== "list" && JSON.stringify(v) === JSON.stringify(s))
  return short ? short[0] : s
}

/** The names of an object type's fields (none: not an object). */
export const fieldKeys = (type?: Type): string[] => (kindOf(type) === "object" && type ? Object.keys(((schemaOf(type).properties ?? {}) as object)) : [])

/** An object variable's fields (or those of each item of a list of objects), held in the dialog's type and kept with its Save: `SchemaFields`, as the dialog's own. */
export function StagedFields({ name, type, own, at = "type", flush }: { name: string; type?: Type; own?: Type; at?: string; flush?: boolean }) {
  const st  = useStaged()
  const was = own ?? type ?? "any"
  return st ? <SchemaFields flush={flush} name={name} type={(st.patch[at] as Type | undefined) ?? was} was={was} onChange={(t) => st.put(at, t, was)} /> : null
}

/** The fields of an object type (or of each item of a list of objects), as a table like a record's: a row each, its name and what it
 * is, the row's trash as you point at it, a click opening the field; a new one added under them with its description. No `onChange`:
 * read only. `onOpen`: what a field's click opens instead (the app's own objects: the field's own dialog). `was`: the type as kept, to mark a field new
 * or changed (nothing marked without it). `flush`: no line over it, it's under a section's own. */
export function SchemaFields({ name, type, was, flush, onChange, onOpen }: { name: string; type: Type; was?: Type; flush?: boolean; onChange?: (type: Type) => void; onOpen?: (key: string) => void }) {
  const [open, setOpen]     = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const schema = schemaOf(type)
  const list   = kindOf(type) === "list"
  const holder = list ? ((schema.items ?? {}) as Schema) : schema
  if (kindOf(holder) !== "object") return null
  const props  = Object.entries((holder.properties ?? {}) as Record<string, Schema>)
  const put    = (next: [string, Schema][]) => {
    const inner = { ...holder, properties: Object.fromEntries(next) }
    onChange?.(typed(list ? { ...schema, items: inner } : inner))
  }
  const at     = (key: string, to: string, s: Schema) => put(props.map(([k, old]) => (k === key ? [to, s] : [k, old])))
  const add    = async (key: string, desc: string) => props.some(([k]) => k === key) ? `${key} is already there`
                                                     : (put([...props, [key, { type: "string", ...(desc ? { description: desc } : {}) }]]), "")
  const row    = "grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] items-center gap-3"
  const spec   = props.find(([k]) => k === open)
  const kept   = was === undefined ? undefined : (((kindOf(was) === "list" ? schemaOf(was).items : schemaOf(was)) ?? {}) as Schema).properties as Record<string, Schema> | undefined ?? {}
  const mark   = (key: string, s: Schema) => (!kept ? undefined : !(key in kept) ? "bg-added/10" : JSON.stringify(kept[key]) !== JSON.stringify(s) ? "bg-changed/10" : undefined)
  return (
    <section className={cn("flex flex-col gap-1.5", !flush && "border-t pt-4")}>
      <Heading text="Fields" onAdd={adding || !onChange ? undefined : () => setAdding(true)} />
      <div className="rounded-md border">
        <div className={cn(row, "bg-muted/40 py-1 pr-9 pl-2 text-xs text-muted-foreground")}><span>Name</span><span>What it is</span></div>
        {props.map(([key, s]) => (
          <div key={key} className={cn("group/row relative border-t", mark(key, s))}>
            <div role="button" tabIndex={0} onClick={() => (onOpen ?? setOpen)(key)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (onOpen ?? setOpen)(key)}
                 className={cn(row, "cursor-pointer py-1.5 pr-9 pl-2 text-xs hover:bg-muted/60")}>
              <span className="flex min-w-0 items-center gap-1.5"><TypeIcon type={s as Type} /><code className="truncate font-semibold">{key}</code></span>
              <span className="truncate text-muted-foreground">{[String(s.description ?? ""), Array.isArray(s.enum) ? `one of ${s.enum.map(String).join(", ")}` : ""].filter(Boolean).join(" · ") || "–"}</span>
            </div>
            {onChange && <Button type="button" size="icon-xs" variant="ghost" aria-label={`Delete ${key}`} title="Delete" onClick={() => put(props.filter(([k]) => k !== key))}
                    className="absolute top-1/2 right-1.5 -translate-y-1/2 text-destructive opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100"><Trash2 /></Button>}
          </div>
        ))}
        {props.length === 0 && !adding && <p className="px-2 py-1.5 text-xs text-muted-foreground">None.</p>}
        {adding && <AddRow grid={row} onAdd={add} onClose={() => setAdding(false)} />}
      </div>
      {open && spec && (
        <Dialog open onOpenChange={(to) => !to && setOpen(null)}>
          <DialogContent className="sm:max-w-lg" onEscapeKeyDown={typing}>
            <Drafted<[string, Schema]> value={spec} onClose={() => setOpen(null)} onSave={([to, s]) => {
              if (!to.trim() || (to !== spec[0] && props.some(([k]) => k === to))) return `${to.trim() || "A field"} is already there`
              at(spec[0], to, s)
              setOpen(null)
            }}>
              {(d, update) => {
                const kind = kindOf(d[1])
                const own  = (change: Partial<Schema> | ((s: Schema) => Schema)) => update(([k, s]) => [k, typeof change === "function" ? change(s) : { ...s, ...change }])
                const keep = (s: Schema, next: Schema): Schema => ({ ...next, ...(s.description ? { description: s.description } : {}) })  // a type picked keeps what it's for
                return (
                  <>
                    <DialogHeader>
                      <DialogTitle className="flex min-w-0 items-center gap-2 pr-8 font-mono text-sm">
                        <TypeIcon type={d[1] as Type} className="size-4" />
                        <span className="flex min-w-0 items-baseline">
                          <span className="shrink-0">{`${name}${list ? "[i]" : ""}.`}</span>
                          <Editable label="Name" value={d[0]} changed={d[0] !== spec[0]} className="truncate text-foreground" onSave={onChange && (async (t) => (update(([, s]) => [t.trim(), s]), null))} />
                        </span>
                      </DialogTitle>
                      <DialogDescription asChild>
                        <div><Editable label="Description" long placeholder="No description" value={String(d[1].description ?? "")} changed={(d[1].description ?? "") !== (spec[1].description ?? "")}
                                       onSave={onChange && (async (t) => (own({ description: t }), null))} /></div>
                      </DialogDescription>
                    </DialogHeader>
                    <dl className="spec-rows items-center">
                      <dt className="text-muted-foreground">Type</dt>
                      <dd>
                        <Pick label="Type" value={kind} changed={kind !== kindOf(spec[1])} options={TYPES.map((t) => [t, <><TypeIcon type={t} />{t}</>])}
                              onPick={onChange && ((k) => own((s) => keep(s, picked(k, s))))}>
                          <span style={{ color: `var(--type-${kind})` }}>{kind}</span>
                        </Pick>
                      </dd>
                      {kind === "list" && (
                        <>
                          <dt className="text-muted-foreground">Item</dt>
                          <dd>
                            <Pick label="Item" value={kindOf((d[1].items ?? {}) as Type)} changed={kindOf((d[1].items ?? {}) as Type) !== kindOf((spec[1].items ?? {}) as Type)}
                                  options={TYPES.filter((t) => t !== "list").map((t) => [t, <><TypeIcon type={t} />{t}</>])}
                                  onPick={onChange && ((k) => own((s) => ({ ...s, items: picked(k, (s.items ?? {}) as Schema) })))}>
                              <span style={{ color: `var(--type-${kindOf((d[1].items ?? {}) as Type)})` }}>{kindOf((d[1].items ?? {}) as Type)}</span>
                            </Pick>
                          </dd>
                        </>
                      )}
                    </dl>
                    <SchemaFields name={`${name}${list ? "[i]" : ""}.${d[0]}`} type={d[1] as Type} was={spec[1] as Type}
                                  onChange={onChange && ((t) => own((s) => keep(s, schemaOf(t))))} />
                  </>
                )
              }}
            </Drafted>
          </DialogContent>
        </Dialog>
      )}
    </section>
  )
}

/** A section's name, and its `+ Add` at the end of the line (none: nothing to add now). */
export function Heading({ text, onAdd }: { text: string; onAdd?: () => void }) {
  return (
    <div className="flex h-6 items-center justify-between gap-2">
      <span className="text-xs font-medium">{text}</span>
      {onAdd && <AddButton onClick={onAdd} />}
    </div>
  )
}

/** A new row at a table's end, its name and description typed where they'll be: added on Enter (the mistake, if any, under
 * it); Escape, or leaving it empty, takes it away. `grid`: the table's columns. */
export function AddRow({ grid, onAdd, onClose }: { grid: string; onAdd: (key: string, desc: string) => Promise<string>; onClose: () => void }) {
  const [key, setKey]     = useState("")
  const [desc, setDesc]   = useState("")
  const [error, setError] = useState("")
  const add = async () => {  // Enter, or leaving the row: a name makes the field, none drops the row
    if (!key.trim()) return onClose()
    const said = await onAdd(key.trim(), desc.trim())
    setError(said)
    if (!said) onClose()
  }
  const keys = (e: KeyboardEvent) => (e.key === "Escape" ? onClose() : e.key === "Enter" && (e.preventDefault(), void add()))
  return (
    <div className="border-t py-1 pr-9 pl-2" onBlur={(e) => !e.currentTarget.contains(e.relatedTarget) && void add()}>
      <div className={grid}>
        <Input {...PLAIN} autoFocus value={key} onChange={(e) => setKey(e.target.value)} onKeyDown={keys} placeholder="new_field" aria-label="Name" className={cn(BARE, "font-mono font-semibold")} />
        <Input value={desc} onChange={(e) => setDesc(e.target.value)} onKeyDown={keys} placeholder="Description" aria-label="Description" className={cn(BARE, "text-muted-foreground")} />
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

/** What's typed in as a value: a number, true or false, null, or else the text. */
export function parsed(text: string): unknown {
  if (!text.trim()) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

/** A type, said short: its name, else what kind of schema. */
export function said(type: Type | undefined): string {
  return typeof type === "string" ? type : typeof type?.type === "string" ? type.type : "schema"
}

const ICONS: Record<string, LucideIcon> = {
  any: CircleHelp, string: TextIcon, integer: Hash, number: Radical, boolean: ToggleRight, time: Clock, list: Brackets, object: Box,
}

/** A type as its icon, in its kind's colour, its name on hover (any, for one it can't tell). */
export function TypeIcon({ type, className }: { type: Type | undefined; className?: string }) {
  const name = kindOf(type ?? "any")
  const Icon = ICONS[name]
  return <Icon aria-label={name} style={{ color: `var(--type-${name})` }} className={cn("size-3 shrink-0", className)} strokeWidth={2.25} />
}

/** What reads it (or writes it), as a chip like a source's: its icon and its kind; `means` for its hover, else what the kind means. */
export function Pill({ by, means }: { by: Reader; means?: string }) {
  const [icon, tint, said] = READERS[by]
  return <span title={means ?? said} className={cn(TAG, tint)}><Mark icon={icon} />{by}</span>
}

