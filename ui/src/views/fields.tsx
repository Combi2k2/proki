// A record's (a task's, a note's) fields, each with its sources, in order; the first with
// a value wins. A row opens to edit it, one at a time.

import { useCallback, useEffect, useState, type ReactNode } from "react"
import { Box, Brackets, CircleHelp, Clock, GripVertical, Hash, Plus, Radical, RotateCcw, ToggleRight, Trash2, TriangleAlert, Type as TextIcon, X, type LucideIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { Field, Source, SourceName, Type, Weighed } from "@/lib/proki"
import { CodeArea, CodeInput } from "@/views/code"

type Change = (request: object) => Promise<string>

const SOURCES: Record<SourceName, { means: string; chip: string; fresh: Source }> = {
  expr:    { means: "Computed from other fields", chip: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
             fresh: { from: "expr", expr: "" } },
  jev:     { means: "Asked to jev (local, fast)", chip: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
             fresh: { from: "jev", type: "noul", question: "" } },
  llm:     { means: "Asked to the LLM", chip: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
             fresh: { from: "llm", context: "" } },
  user:    { means: "Set by you, per record", chip: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", fresh: { from: "user" } },
  auto:    { means: "Set by a program", chip: "bg-zinc-500/15 text-zinc-700 dark:text-zinc-300", fresh: { from: "auto" } },
}
const PLAIN = { autoCapitalize: "off", autoCorrect: "off", spellCheck: false } as const  // names and formulas, as typed
const NAMES = Object.keys(SOURCES) as SourceName[]
const GRID  = "grid grid-cols-[11rem_minmax(0,1fr)_15rem] items-center gap-3"

/** A field: its name, what it is and its sources; open, its editor. */
function FieldRow({ field, weighed, open, onOpen, onRenamed, onChange }: {
  field: Field
  weighed: Weighed
  open: number | null
  onOpen: (source: number | null) => void
  onRenamed: (key: string) => void
  onChange: Change
}) {
  return (
    <div className={cn("border-b", open !== null && "rounded-lg border bg-muted/30 my-1")}>
      <div role="button" tabIndex={0} onClick={() => onOpen(open === null ? 0 : null)}
           onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpen(open === null ? 0 : null)}
           className={cn(GRID, "cursor-pointer px-3 py-2 hover:bg-muted/60", open !== null && "hover:bg-transparent")}>
        <span className="flex min-w-0 items-center gap-1.5">
          <TypeIcon type={field.worked} />
          <code title={field.key} className="truncate text-sm font-semibold">{field.key}</code>
        </span>
        <span className="truncate text-xs text-muted-foreground">{field.desc || "–"}</span>
        <span className="flex flex-wrap gap-1">
          {field.srcs.map((s, i) => (
            <Chip key={s.from} name={s.from} onClick={(e) => (e.stopPropagation(), onOpen(i))} />
          ))}
          {field.srcs.length === 0 && <span className="text-xs text-muted-foreground">none</span>}
        </span>
      </div>
      {open !== null && <Editor field={field} weighed={weighed} source={open} onSource={onOpen} onRenamed={onRenamed} onChange={onChange} />}
    </div>
  )
}

/** A record's fields, if `record` is one: each with its type, what it is and its sources, each
 *  opened to change how it's worked out; a new one added under them. `children` for a variable
 *  that isn't a record (nothing while it's asked). */
export function RecordFields({ record, children }: { record: string; children?: ReactNode }) {
  const [weighed, setWeighed] = useState<Weighed | null | undefined>(undefined)
  const [open, setOpen]       = useState<{ key: string; source: number } | null>(null)
  const load = useCallback(async () => {
    const read = await window.proki.fields({ op: "read", record })
    setWeighed(!read.error && read.records.includes(record) ? { ...read, record } : null)
  }, [record])
  useEffect(() => {
    load()
  }, [load])
  const change: Change = async (request) => {
    const answer = await window.proki.fields({ ...request, record })
    if (!answer.error) await load()
    return answer.error ?? ""
  }
  if (weighed === undefined) return null
  if (weighed === null)      return <>{children}</>
  return (
    <TooltipProvider delayDuration={300}>
      <section className="flex flex-col border-t pt-3">
        <span className="mb-1.5"><Label text="Fields" hint="click one to change how it's worked out: the first source with a value wins" /></span>
        {weighed.fields.map((field) => (
          <FieldRow key={field.key} field={field} weighed={weighed} onChange={change}
                    open={open?.key === field.key ? open.source : null}
                    onOpen={(source) => setOpen(source === null ? null : { key: field.key, source })}
                    onRenamed={(key) => setOpen((o) => o && { ...o, key })} />
        ))}
        <NewField onChange={change} onMade={(key) => setOpen({ key, source: 0 })} />
      </section>
    </TooltipProvider>
  )
}

/** A source as a chip: what it means as you hover it. */
function Chip({ name, active, onClick, onRemove, ...drag }: {
  name: SourceName
  active?: boolean
  onClick?: (e: React.MouseEvent) => void
  onRemove?: () => void
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span {...drag} onClick={onClick}
              className={cn("inline-flex h-5 cursor-pointer items-center gap-0.5 rounded-full px-2 font-mono text-[11px] font-medium select-none",
                            SOURCES[name].chip, active && "ring-2 ring-ring/60", drag.draggable && "cursor-grab pl-1")}>
          {drag.draggable && <GripVertical className="size-3 opacity-50" />}
          {name}
          {onRemove && (
            <button type="button" aria-label={`remove ${name}`} onClick={(e) => (e.stopPropagation(), onRemove())}
                    className="-mr-1 rounded-full p-0.5 opacity-60 hover:opacity-100"><X className="size-2.5" /></button>
          )}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top">{SOURCES[name].means}</TooltipContent>
    </Tooltip>
  )
}

/** An open field: what it is, its sources in order (dragged to reorder), the one picked to
 * edit, and saving it all. */
function Editor({ field, weighed, source, onSource, onRenamed, onChange }: {
  field: Field
  weighed: Weighed
  source: number
  onSource: (source: number | null) => void
  onRenamed: (key: string) => void
  onChange: Change
}) {
  const [key, setKey] = useState(field.key)
  const [desc, setDesc] = useState(field.desc)
  const [sources, setSources] = useState<Source[]>(field.srcs)
  const [type, setType] = useState<Type>(field.type)
  const [dragged, setDragged] = useState<number | null>(null)
  const [error, setError] = useState("")
  useEffect(() => (setKey(field.key), setDesc(field.desc), setSources(field.srcs), setType(field.type)), [field])

  const picked  = sources[Math.min(source, sources.length - 1)]
  const edited  = desc !== field.desc || JSON.stringify(sources) !== JSON.stringify(field.srcs) || JSON.stringify(type) !== JSON.stringify(field.type)
  const changed = edited || key.trim() !== field.key
  const missing = NAMES.filter((n) => !sources.some((s) => s.from === n))
  const put     = (i: number, s: Source) => setSources(sources.map((old, j) => (j === i ? s : old)))
  const move    = (from: number, to: number) => {
    const next = [...sources]
    next.splice(to, 0, ...next.splice(from, 1))
    setSources(next)
    onSource(to)
  }
  const save = async () => {
    const to = key.trim()
    if (to !== field.key) {
      const mistake = await onChange({ op: "rename", key: field.key, to })
      if (mistake) return setError(mistake)
      onRenamed(to)
    }
    setError(edited ? await onChange({ op: "define", field: { key: to, desc, type, srcs: sources.map(cleaned) } }) : "")
  }

  return (
    <div className="flex flex-col gap-3 border-t px-3 pt-3 pb-3">
      <div className="grid grid-cols-[11rem_minmax(0,1fr)] gap-2">
        <Input {...PLAIN} value={key} onChange={(e) => setKey(e.target.value)} disabled={field.shipped} aria-label="name"
               title={field.shipped ? "Built-in fields keep their name" : undefined} className="h-8 font-mono text-xs" />
        <Input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Description" className="h-8 text-xs" />
      </div>
      <TypeField label="Type" value={type} onChange={(t) => setType(t ?? "any")} />
      {type === "any" && field.worked !== "any" && <p className="-mt-2 text-xs text-muted-foreground">Worked out: {said(field.worked)}</p>}

      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-xs text-muted-foreground">Sources</span>
        {sources.map((s, i) => (
          <span key={s.from} className="flex items-center gap-1.5">
            {i > 0 && <span className="text-xs text-muted-foreground">→</span>}
            <Chip name={s.from} active={s === picked} onClick={() => onSource(i)}
                  onRemove={() => (setSources(sources.filter((_, j) => j !== i)), onSource(Math.max(0, i - 1)))}
                  draggable onDragStart={() => setDragged(i)} onDragOver={(e) => e.preventDefault()}
                  onDrop={() => dragged !== null && dragged !== i && move(dragged, i)} onDragEnd={() => setDragged(null)} />
          </span>
        ))}
        {missing.length > 0 && (
          <select value="" aria-label="add a source"
                  onChange={(e) => (setSources([...sources, SOURCES[e.target.value as SourceName].fresh]), onSource(sources.length))}
                  className="h-6 rounded-full border border-dashed bg-transparent px-2 text-xs text-muted-foreground outline-none hover:bg-muted">
            <option value="" disabled>+ source</option>
            {missing.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        )}
      </div>

      {picked ? (
        <div className="rounded-md border bg-background p-3">
          <SourceEditor key={picked.from} about={about(field, weighed, onChange)} source={picked} onPut={(s) => put(sources.indexOf(picked), s)} />
        </div>
      ) : <p className="text-xs text-muted-foreground">No sources: always empty.</p>}

      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={save} disabled={!changed}>Save</Button>
        <Button size="sm" variant="ghost" disabled={!changed} onClick={() => (setKey(field.key), setDesc(field.desc), setSources(field.srcs), setType(field.type), setError(""))}>
          Discard
        </Button>
        <Button size="sm" variant="ghost" className="ml-auto text-muted-foreground hover:text-destructive"
                onClick={async () => setError(await onChange({ op: "remove", key: field.key }))}>
          {field.shipped ? <><RotateCcw /> Reset</> : <><Trash2 /> Delete</>}
        </Button>
      </div>
    </div>
  )
}

/** What a source is edited for: a record's field. */
type About = {
  name: string                     // its name as a record reads it: me.official
  names: string[]                  // what a formula reads, besides time
  hint: string                     // what a question fills in
  per?: string                     // a record's: a value of yours is set per record ("work.tasks")
  setters: string[]                // the programs that set it
  contexts?: { jev: string; llm: string }   // a record's: what every question is read under
  onChange?: Change
}

/** One source, edited as its kind is. */
function SourceEditor({ about, source, onPut }: { about: About; source: Source; onPut: (s: Source) => void }) {
  const set = (changed: Partial<Source>) => onPut({ ...source, ...changed })
  const { names, hint, per } = about

  switch (source.from) {
    case "expr":
      return (
        <div className="flex flex-col gap-2">
          <Label text="Formula" />
          <CodeArea value={source.expr ?? ""} onChange={(e) => set({ expr: e.target.value })} placeholder="me.estimate > 60"
                    className="field-sizing-content min-h-0 resize-none text-xs" />
          <Collapsible className="text-xs text-muted-foreground">
            <CollapsibleTrigger className="cursor-pointer hover:text-foreground">Names ›</CollapsibleTrigger>
            <CollapsibleContent><p className="mt-1 font-mono">time, {names.join(", ")}</p></CollapsibleContent>
          </Collapsible>
        </div>
      )

    case "jev":
      return (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Label text="Answer" />
            <NativeSelect size="sm" value={source.type} onChange={(e) => set({ type: e.target.value as Source["type"], criteria: e.target.value === "noul" ? undefined : source.criteria ?? { "": "" } })}>
              <NativeSelectOption value="noul">Yes/no (0–1)</NativeSelectOption>
              <NativeSelectOption value="choice">Choice (.index .conf .odds)</NativeSelectOption>
              <NativeSelectOption value="score">Score (.score .conf .odds)</NativeSelectOption>
            </NativeSelect>
          </div>
          <Label text="Question" hint={hint} />
          <Textarea value={source.question ?? ""} onChange={(e) => set({ question: e.target.value })} placeholder="Is this for school?"
                    className="field-sizing-content min-h-0 resize-none text-xs" />
          {source.type !== "noul" && <Criteria key={source.type} criteria={source.criteria ?? {}} onSet={(criteria) => set({ criteria })}
                                               {...(source.type === "score" ? { label: "Marks", hint: "a number on its scale, and what it means", placeholder: "1" } : {})} />}
          <Then source={source} hint={{ noul: "res >= 0.5", choice: "res.index == 1", score: "res.score >= 5" }[source.type ?? "noul"]} onSet={set} />
          {about.contexts && about.onChange && <Context channel="jev" text={about.contexts.jev} onChange={about.onChange}
                                                       warning={`Shared by every jev question, for every ${per}.`} />}
        </div>
      )

    case "llm":
      return (
        <div className="flex flex-col gap-2">
          <Label text="Prompt" hint={hint} />
          <Textarea value={source.context ?? ""} onChange={(e) => set({ context: e.target.value })} placeholder="How many hours will this take?"
                    className="field-sizing-content min-h-0 resize-none text-xs" />
          <TypeField label="Answer" value={source.schema} inherit onChange={(schema) => set({ schema })} />
          <Then source={source} hint={isObject(source.schema) ? "res.hours * 60" : "res * 60"} onSet={set} />
          {about.contexts && about.onChange && <Context channel="llm" text={about.contexts.llm} onChange={about.onChange}
                                                       warning={`Shared by every LLM prompt, for every ${per}.`} />}
        </div>
      )

    case "user":
      return (
        <p className="text-xs text-muted-foreground">Set per {per}. Unset: the next source.</p>
      )

    case "auto":
      return (
        <div className="flex flex-col gap-2">
          <Label text="Set by" />
          {about.setters.length ? (
            <span className="flex flex-wrap gap-1">
              {about.setters.map((p) => <code key={p} className="rounded bg-muted px-1.5 py-0.5 text-xs">{p}</code>)}
            </span>
          ) : <p className="text-xs text-muted-foreground">No program yet.</p>}
          <Label text="Initial value" hint="empty: the next source" />
          <Input {...PLAIN} defaultValue={source.initial === undefined ? "" : JSON.stringify(source.initial)}
                 onBlur={(e) => set({ initial: parsed(e.target.value) })} placeholder="0" className="h-8 w-40 font-mono text-xs" />
          <p className="text-xs text-muted-foreground">
            Updates are written in a program: <code>set</code>, <code>add</code> or <code>sub</code> on <code>{about.name}</code>.
          </p>
        </div>
      )
  }
}

/** jev's criteria, in order: each key (a choice's option, a score's mark on its scale) and what it means. */
export function Criteria({ criteria, label = "Options", hint = "label, and what it means", placeholder = "high", onSet }: {
  criteria: Record<string, string | null>
  label?: string
  hint?: string
  placeholder?: string
  onSet: (criteria: Record<string, string>) => void
}) {
  const [rows, setRows] = useState(Object.entries(criteria).map(([l, means]): [string, string] => [l, means ?? ""]))
  const put = (next: [string, string][]) => (setRows(next), onSet(Object.fromEntries(next)))
  return (
    <div className="flex flex-col gap-1.5">
      <Label text={label} hint={hint} />
      {rows.map(([label, means], i) => (
        <div key={i} className="grid grid-cols-[10rem_minmax(0,1fr)_auto] gap-1.5">
          <Input {...PLAIN} value={label} onChange={(e) => put(rows.map((r, j) => (j === i ? [e.target.value, r[1]] : r)))} placeholder={placeholder}
                 className="h-7 font-mono text-xs" />
          <Input value={means} onChange={(e) => put(rows.map((r, j) => (j === i ? [r[0], e.target.value] : r)))} placeholder="it takes all of you"
                 className="h-7 text-xs" />
          <Button variant="ghost" size="icon-xs" aria-label="remove" onClick={() => put(rows.filter((_, j) => j !== i))}><X /></Button>
        </div>
      ))}
      <Button variant="ghost" size="sm" className="w-fit text-xs" onClick={() => put([...rows, ["", ""]])}><Plus /> Option</Button>
    </div>
  )
}

export const TYPES = ["any", "number", "integer", "boolean", "string", "time", "object", "list"]
type Schema = Record<string, unknown>
const SCHEMAS: Record<string, Schema> = {
  any: {}, number: { type: "number" }, integer: { type: "integer" }, boolean: { type: "boolean" }, string: { type: "string" },
  time: { type: "number", format: "time" }, object: { type: "object", properties: {} }, list: { type: "array", items: {} },
}
const isObject = (t: Type | undefined) => typeof t === "object" && t.type === "object"

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

/** A type: a name, an object of named fields, or a list of one type, each field a type of its
 *  own. `inherit`: none is the field's own (an ask's answer). `fixed`: shown, not changed.
 *  `alone`: its kind only, what's inside it shown by TypeInside where there's room. */
export function TypeField({ label, value, inherit, fixed, alone, onChange }: {
  label: string; value: Type | undefined; inherit?: boolean; fixed?: boolean; alone?: boolean; onChange?: (type: Type | undefined) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        {label && <Label text={label} />}
        <Kind value={kindOf(value)} inherit={inherit} fixed={fixed}
              onChange={(k) => onChange?.(k === "inherit" ? undefined : typed(picked(k, value === undefined ? {} : schemaOf(value))))} />
        {value !== undefined && !alone && <OneOf value={schemaOf(value)} />}
      </div>
      {value !== undefined && !alone && <Inside value={schemaOf(value)} fixed={fixed} onChange={(s) => onChange?.(typed(s))} />}
    </div>
  )
}

/** What's inside a type, a section of its own: an object's fields, a list's items' type (nothing
 *  for a type with nothing inside). */
export function TypeInside({ value, onChange }: { value: Type; onChange: (type: Type) => void }) {
  const kind = kindOf(value)
  if (kind !== "object" && kind !== "list") return null
  return (
    <section className="flex flex-col gap-2 border-t pt-3">
      {kind === "object" && <Label text="Fields" />}
      <Inside value={schemaOf(value)} flat onChange={(s) => onChange(typed(s))} />
    </section>
  )
}

/** A type's kind, picked from them all, each with its icon. */
function Kind({ value, inherit, fixed, onChange }: { value: string; inherit?: boolean; fixed?: boolean; onChange: (kind: string) => void }) {
  if (fixed) return <span className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground"><TypeIcon type={value} />{value}</span>
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" aria-label="type" className="min-w-28 font-mono text-xs"><SelectValue /></SelectTrigger>
      <SelectContent position="popper" className="font-mono">
        {inherit && <SelectItem value="inherit" className="text-xs">its type</SelectItem>}
        {TYPES.map((t) => <SelectItem key={t} value={t} className="text-xs"><TypeIcon type={t} />{t}</SelectItem>)}
      </SelectContent>
    </Select>
  )
}

/** The options a type is one of, said beside it (nothing for a type that has none). */
function OneOf({ value }: { value: Schema }) {
  const options = Array.isArray(value.enum) ? `one of ${value.enum.map(String).join(", ")}` : ""
  return <span title={options || undefined} className="min-w-0 flex-1 truncate text-xs text-muted-foreground">{options}</span>
}

/** What's inside a type: an object's fields, each a name and a type, or a list's items' type;
 *  what's inside those set in under them. */
function Inside({ value, fixed, flat, onChange }: { value: Schema; fixed?: boolean; flat?: boolean; onChange: (s: Schema) => void }) {
  const kind = kindOf(value)
  const box  = cn("flex flex-col gap-1.5", !flat && "mt-1 mb-1.5 ml-2 border-l pt-1 pl-4")
  if (kind === "list") {
    const items = (value.items ?? {}) as Schema
    return (
      <div className={box}>
        <div className="flex items-center gap-2">
          <span className="w-32 shrink-0 text-xs text-muted-foreground">Item's type</span>
          <Kind value={kindOf(items)} fixed={fixed} onChange={(k) => onChange({ ...value, items: picked(k, items) })} />
          <OneOf value={items} />
        </div>
        <Inside value={items} fixed={fixed} onChange={(items) => onChange({ ...value, items })} />
      </div>
    )
  }
  if (kind !== "object") return null
  const props = Object.entries((value.properties ?? {}) as Record<string, Schema>)
  const put   = (next: [string, Schema][]) => onChange({ ...value, properties: Object.fromEntries(next) })
  const at    = (i: number, key: string, s: Schema) => put(props.map((p, j) => (j === i ? [key, s] : p)))
  const fresh = Array.from({ length: props.length + 1 }, (_, n) => `field_${n + 1}`).find((k) => !props.some(([p]) => p === k))!
  return (
    <div className={box}>
      {props.map(([key, s], i) => (
        <div key={i} className="flex flex-col">
          <div className="flex items-center gap-2">
            <Input {...PLAIN} value={key} disabled={fixed} aria-label="field name" className="h-7 w-32 shrink-0 font-mono text-xs md:text-xs"
                   onChange={(e) => !props.some(([k], j) => j !== i && k === e.target.value) && at(i, e.target.value, s)} />
            <Kind value={kindOf(s)} fixed={fixed} onChange={(k) => at(i, key, picked(k, s))} />
            <OneOf value={s} />
            {!fixed && <Button variant="ghost" size="icon-xs" aria-label={`remove ${key}`} onClick={() => put(props.filter((_, j) => j !== i))}><X /></Button>}
          </div>
          <Inside value={s} fixed={fixed} onChange={(s) => at(i, key, s)} />
        </div>
      ))}
      {!props.length && fixed && <p className="text-xs text-muted-foreground">No fields.</p>}
      {!fixed && <Button variant="ghost" size="sm" className="w-fit text-xs" onClick={() => put([...props, [fresh, {}]])}><Plus /> Field</Button>}
    </div>
  )
}

/** An ask's formula on its answer (none: the answer as it is). */
function Then({ source, hint, onSet }: { source: Source; hint: string; onSet: (s: Partial<Source>) => void }) {
  return (
    <>
      <Label text="Then" hint="optional formula on answer" />
      <CodeInput value={source.expr ?? ""} onChange={(e) => onSet({ expr: e.target.value })} placeholder={hint} className="h-8 text-xs" />
    </>
  )
}

/** What every one of a channel's questions is read under, saved on its own. */
function Context({ channel, text, warning, onChange }: { channel: "jev" | "llm"; text: string; warning: string; onChange: Change }) {
  const [draft, setDraft] = useState(text)
  const [error, setError] = useState("")
  useEffect(() => setDraft(text), [text])
  return (
    <div className="mt-1 flex flex-col gap-1.5 border-t pt-3">
      <Label text="Context" hint="lines with an empty {field} are dropped" />
      <Textarea {...PLAIN} value={draft} onChange={(e) => setDraft(e.target.value)} className="field-sizing-content min-h-0 resize-none font-mono text-xs" />
      <p className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400"><TriangleAlert className="mt-px size-3.5 shrink-0" /> {warning}</p>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button size="sm" variant="outline" disabled={draft === text}
                onClick={async () => setError(await onChange({ op: "context", channel, text: draft }))}>Save context</Button>
        <Button size="sm" variant="ghost" onClick={async () => setError(await onChange({ op: "context", channel, text: "" }))}>
          Reset
        </Button>
      </div>
    </div>
  )
}

function Label({ text, hint }: { text: string; hint?: string }) {
  return (
    <span className="text-xs font-medium">
      {text}
      {hint && <span className="ml-1.5 font-normal text-muted-foreground">{hint}</span>}
    </span>
  )
}

/** A new field: set by you, until you give it other sources. */
function NewField({ onChange, onMade }: { onChange: Change; onMade: (key: string) => void }) {
  const [key, setKey] = useState("")
  const [desc, setDesc] = useState("")
  const [error, setError] = useState("")

  const add = async () => {
    const made = key.trim()
    const said = await onChange({ op: "define", field: { key: made, desc: desc.trim(), srcs: [{ from: "user" }] } })
    setError(said)
    if (!said) setKey(""), setDesc(""), onMade(made)
  }

  return (
    <div className="mt-3 flex flex-col gap-1">
      <div className={GRID}>
        <Input {...PLAIN} value={key} onChange={(e) => setKey(e.target.value)} placeholder="new_field" className="h-8 font-mono text-xs" />
        <Input value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="Description"
               onKeyDown={(e) => e.key === "Enter" && key.trim() && add()} className="h-8 text-xs" />
        <Button size="sm" onClick={add} disabled={!key.trim()}><Plus /> Add</Button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

/** A source as it's kept: what its kind doesn't take, and an empty formula on an answer, left out. */
function cleaned(s: Source): Source {
  const { expr, criteria, schema, kind: _, ...rest } = s as Source & { kind?: string }
  return {
    ...rest,
    ...(expr?.trim() ? { expr: expr.trim() } : {}),
    ...(s.from === "jev" && s.type !== "noul" ? { criteria } : {}),
    ...(s.from === "llm" && schema !== undefined ? { schema } : {}),
  }
}

/** What's typed in as a value: a number, true or false, null, or else the text. */
function parsed(text: string): unknown {
  if (!text.trim()) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

/** What a record's field's sources are edited for. */
function about(field: Field, weighed: Weighed, onChange: Change): About {
  const record = weighed.record ?? "work.tasks"
  return {
    name: `me.${field.key}`,
    names: [...weighed.own, ...weighed.fields.map((f) => f.key)].map((k) => `me.${k}`),
    hint: "{me.<key>}",
    per: record, setters: field.setters, contexts: weighed.contexts, onChange,
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

