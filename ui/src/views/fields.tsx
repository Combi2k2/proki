// A record's (a task's, a note's) fields, each with its sources, in order; the first with
// a value wins. A row opens its dialog, changed where it's read, one at a time.

import { useCallback, useEffect, useState, type KeyboardEvent, type ReactNode } from "react"
import {
  Bot, Box, Brackets, CircleHelp, Clock, Hash, KeySquare, Plus, Radical, Sigma, ToggleRight, Trash2, Type as TextIcon, User, Workflow, X,
  type LucideIcon,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { Field, Source, SourceName, Type, Weighed } from "@/lib/proki"
import { Confirm } from "@/components/confirm"
import { CHANGED, Editable, Pick, type Staged, Staging, Term, typing, useStaged } from "@/views/in-place"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { BARE, CodeInput, Template } from "@/views/code"
import { Collection, emptyOf } from "@/views/inspect"
import { goToPlace, Places } from "@/views/places"
import { AddButton, Detail, takeover } from "@/views/scope-shared"

type Change = (request: object) => Promise<string>

const SOURCES: Record<SourceName, { means: string; icon: LucideIcon; chip: string; fresh: Source }> = {
  expr:    { means: "Computed from other fields", icon: Sigma,     chip: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
             fresh: { from: "expr", expr: "" } },
  jev:     { means: "Asked to jev", icon: KeySquare, chip: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
             fresh: { from: "jev", type: "noul", question: "" } },
  llm:     { means: "Asked to the LLM",           icon: Bot,       chip: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
             fresh: { from: "llm", context: "" } },
  user:    { means: "Set by you, per record",     icon: User,      chip: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", fresh: { from: "user" } },
  auto:    { means: "Set by a program",           icon: Workflow,  chip: "bg-zinc-500/15 text-zinc-700 dark:text-zinc-300", fresh: { from: "auto" } },
}
export const AUTO = SOURCES.auto.chip  // the automations' tint, as a chip of theirs
const PLAIN = { autoCapitalize: "off", autoCorrect: "off", spellCheck: false } as const  // names and formulas, as typed
const NAMES = Object.keys(SOURCES) as SourceName[]
const GRID  = "grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_10.5rem] items-center gap-3"  // a table: room for three sources, what it is takes the rest

/** A field: its name, what it is and its sources; open, its dialog. */
function FieldRow({ field, weighed, open, onOpen, onRenamed, onChange }: {
  field: Field
  weighed: Weighed
  open: number | null
  onOpen: (source: number | null) => void
  onRenamed: (key: string) => void
  onChange: Change
}) {
  const [chip, setChip] = useState<number | null>(null)  // the source whose own dialog is open
  return (
    <div className="group/row relative border-b last:border-b-0">
      <div role="button" tabIndex={0} onClick={() => onOpen(0)}
           onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onOpen(0)}
           className={cn(GRID, "cursor-pointer py-1.5 pr-9 pl-2 hover:bg-muted/60")}>
        <span className="flex min-w-0 items-center gap-1.5">
          <TypeIcon type={field.worked} />
          <code title={field.key} className="truncate text-xs font-semibold">{field.key}</code>
        </span>
        <span title={field.desc} className="truncate text-xs text-muted-foreground">{field.desc || "–"}</span>
        <span className="flex flex-wrap gap-1">
          {field.srcs.map((s, i) => (
            <Chip key={s.from} name={s.from} onClick={(e) => (e.stopPropagation(), setChip(i))} />
          ))}
          {field.srcs.length === 0 && <span className="text-xs text-muted-foreground">none</span>}
        </span>
      </div>
      <DeleteField field={field} weighed={weighed} onDelete={() => onChange({ op: "remove", key: field.key })} size="icon-xs"
                   className="absolute top-1/2 right-1.5 -translate-y-1/2 opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100" />
      {chip !== null && field.srcs[chip] && <SourceDialog field={field} weighed={weighed} index={chip} onChange={onChange} onClose={() => setChip(null)} />}
      {open !== null && (
        <Dialog open onOpenChange={(to) => !to && onOpen(null)}>
          <DialogContent className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-2xl"
                         onEscapeKeyDown={typing}>
            <TooltipProvider delayDuration={300}>
              <Editor field={field} weighed={weighed} onRenamed={onRenamed} onChange={onChange} />
            </TooltipProvider>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

/** A field with its sources as `srcs` (the mistake, if any, else null). */
const withSources = async (field: Field, srcs: Source[], onChange: Change) => (await onChange({ op: "define", field: { key: field.key, desc: field.desc, type: field.type, srcs } })) || null

/** A field's trash, asked first: a field the app came with goes back as it came (`size`, `className`: how the button sits). */
function DeleteField({ field, weighed, onDelete, size, className }: { field: Field; weighed: Weighed; onDelete: () => unknown; size: "icon-xs" | "icon-sm"; className?: string }) {
  const reads   = (text?: string) => !!text && new RegExp(`\\bme\\.${field.key}\\b`).test(text)
  const readers = field.shipped ? [] : [  // yours, read by another field's formula or question, or a channel's context: kept until that's changed
    ...weighed.fields.filter((f) => f.key !== field.key && f.srcs.some((s) => reads(s.expr) || reads(s.question) || reads(s.context))).map((f) => f.key),
    ...Object.entries(weighed.contexts).filter(([, text]) => reads(text)).map(([channel]) => `the ${channel} context`),
  ]
  if (readers.length) return (
    <span title={`Read by ${readers.join(", ")}: take that out first`} className={className}>
      <Button type="button" size={size} variant="ghost" aria-label={`Delete ${field.key}`} disabled><Trash2 /></Button>
    </span>
  )
  return (
    <Confirm title={field.shipped ? `Reset the field “${field.key}”?` : `Delete the field “${field.key}”?`}
             description={field.shipped ? "Its sources go back to the app's." : "Every record loses its value. This can't be undone."}
             action={field.shipped ? "Reset" : "Delete field"} onConfirm={onDelete}>
      <Button type="button" size={size} variant="ghost" aria-label={`Delete ${field.key}`} title="Delete" className={cn("text-destructive", className)}><Trash2 /></Button>
    </Confirm>
  )
}

/** One source of a field, over its table, as a spec dialog says what writes it: its chip and the field's name, then its parts, each
 * changed where it's read and kept with Save. */
function SourceDialog({ field, weighed, index, fresh, onChange, onClose }: { field: Field; weighed: Weighed; index: number; fresh?: Source; onChange: Change; onClose: () => void }) {
  const was   = field.srcs[index] ?? fresh!
  const named = about(field, weighed, onChange)
  const save  = async ({ shared, ...patch }: Record<string, unknown>) => {
    if (typeof shared === "string") {
      const mistake = await onChange({ op: "context", channel: was.from, text: shared })
      if (mistake) return mistake
    }
    const next = cleaned({ ...was, ...patch, ...(typeof patch.initial === "string" ? { initial: parsed(patch.initial) } : {}) } as Source)
    const srcs = index < field.srcs.length ? field.srcs.map((s, i) => (i === index ? next : s)) : [...field.srcs, next]
    const mistake = await withSources(field, srcs, onChange)
    if (!mistake && fresh) onClose()
    return mistake
  }
  const out = async () => {
    if (!(await withSources(field, field.srcs.filter((_, i) => i !== index), onChange))) onClose()
  }
  if (was.from === "user") return (  // as a spec's Written by chip says it: nothing to change here, where it's changed
    <TooltipProvider delayDuration={300}>
      <Detail title={<><Chip name="user" /> Set by you</>} about="Open the table from Now above, and change the rows' values there." onClose={onClose} />
    </TooltipProvider>
  )
  return (
    <Dialog open onOpenChange={(to) => !to && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg" onEscapeKeyDown={typing}>
        <TooltipProvider delayDuration={300}>
          <Staging onSave={save}>
            {(st) => {
              const now = { ...was, ...st.patch } as Source
              const text = (key: keyof Source, placeholder: string, code?: boolean) => (
                <Editable label={String(key)} long code={code} placeholder={placeholder} {...st.field(key, String(was[key] ?? ""))} />
              )
              const post = (
                <CodeInput aria-label="Post-processing" value={"expr" in st.patch ? String(st.patch.expr) : was.expr || "res"}
                           onChange={(e) => st.put("expr", e.target.value, was.expr || "res")} />
              )
              return (
                <>
                  <DialogHeader>
                    <DialogTitle className="flex min-w-0 items-center gap-2 pr-8 text-sm">
                      <Chip name={was.from} />
                      {was.from === "expr" ? "Worked out" : was.from === "auto" ? "Written by the automations" : <span className="truncate font-mono">{`${weighed.record ?? "work.tasks"}[i].${field.key}`}</span>}
                    </DialogTitle>
                    <DialogDescription>{{ expr: "From the other fields, each time.", auto: "Click one to go there." }[was.from as string] ?? SOURCES[was.from].means}</DialogDescription>
                  </DialogHeader>
                  {!fresh && (
                    <Button type="button" size="icon-sm" variant="ghost" aria-label="Take this source out" title="Take it out" onClick={out} className="absolute top-2 right-10 text-destructive"><Trash2 /></Button>
                  )}
                  {was.from === "auto" && (
                    field.places.length
                      ? <Places places={field.places} onVisit={(p) => (takeover(), goToPlace(p))} />
                      : <p className="text-xs text-muted-foreground">No automation yet.</p>
                  )}
                  {was.from === "jev" && <JevForm now={now} was={was} st={st} named={named} post={post} />}
                  <dl hidden={was.from === "jev" || was.from === "llm"} className="grid grid-cols-[6rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-2 border-t pt-4 text-xs">
                    {was.from === "expr" && <><Term>Formula</Term><dd>{text("expr", "me.estimate > 60", true)}</dd></>}
                    {was.from === "auto" && (
                      <>
                        <Term hint="empty: the next source">Starts as</Term>
                        <dd>
                          {emptyOf(field.worked) !== undefined
                            ? <Collection value={"initial" in st.patch ? st.patch.initial : was.initial} type={field.worked} title={field.key} onPut={async (v) => (st.put("initial", v, was.initial), null)} />
                            : <Editable label="Starts as" code placeholder="–" {...st.field("initial", was.initial === undefined ? "" : JSON.stringify(was.initial))} />}
                        </dd>
                      </>
                    )}
                  </dl>
                  {was.from === "llm" && <LlmForm field={field} now={now} was={was} st={st} post={post} />}
                </>
              )
            }}
          </Staging>
        </TooltipProvider>
      </DialogContent>
    </Dialog>
  )
}

/** What an LLM field's prompt is laid out as: the prompt, the type of its answer (a table of fields for an object), then what's done with it. */
function LlmForm({ field, now, was, st, post }: { field: Field; now: Source; was: Source; st: Staged; post: ReactNode }) {
  return (
    <div className="flex flex-col gap-4 [&>section]:border-t-0 [&>section]:pt-0">
      <div className="flex flex-col gap-1.5">
        <Label text="Prompt" />
        <div className="rounded-md border px-2 py-1 text-xs focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50">
          <Template strings value={now.context ?? ""} onChange={(e) => st.put("context", e.target.value, was.context ?? "")} placeholder="How many hours will this take?" aria-label="Prompt" className="min-h-24" />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label text="Type" />
        <dl className="grid grid-cols-[6rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 text-xs">
          <dd className="col-span-2"><TypeChange type={field.worked} own={was.schema} editable at="schema" /></dd>
          <ItemChange type={field.worked} own={was.schema} editable at="schema" />
        </dl>
      </div>
      <StagedFields name={field.key} type={field.worked} own={was.schema} at="schema" />
      <div className="flex flex-col gap-1.5">
        <Label text="Post-processing" />
        {post}
      </div>
    </div>
  )
}

const ANSWERS: Record<string, [string, string][]> = {
  noul:   [["res", "number"]],
  choice: [["res.index", "integer"], ["res.conf", "number"], ["res.odds", "list"]],
  score:  [["res.score", "number"], ["res.conf", "number"], ["res.odds", "list"]],
}

/** What a jev field's question is laid out as: its kind as tabs, what it's read under, the question, its options, then the answer it gives and what's done with it. */
function JevForm({ now, was, st, named, post }: {
  now: Source; was: Source; st: Staged; named: About; post: ReactNode
}) {
  const kind = now.type ?? "noul"
  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" className="grid grid-cols-3 gap-1 rounded-lg border bg-muted/40 p-1 text-xs">
        {["noul", "choice", "score"].map((k) => (
          <button key={k} type="button" role="tab" aria-selected={kind === k} onClick={() => k !== kind && st.put("type", k, was.type ?? "noul")}
                  className={cn("rounded-md py-1 font-mono", kind === k ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground", "type" in st.patch && kind === k && CHANGED)}>
            {k}
          </button>
        ))}
      </div>
      {named.contexts && <Context text={named.contexts.jev} />}
      <div className="flex flex-col gap-1.5">
        <Label text="Question" />
        <div className="rounded-md border px-2 py-1 text-xs focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50">
          <Template strings value={now.question ?? ""} onChange={(e) => st.put("question", e.target.value, was.question ?? "")} placeholder="Is this for school?" aria-label="Question" className="min-h-10" />
        </div>
      </div>
      <Criteria key={kind} criteria={now.criteria ?? {}} onSet={(c) => st.put("criteria", c, was.criteria ?? {})}
                {...(kind === "noul" ? { fixed: ["True", "False"] } : kind === "score" ? { label: "Marks", placeholder: "1" } : {})} />
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-3">
        <div className="flex flex-col gap-1.5">
          <span className="flex items-center gap-1.5 text-xs font-medium"><Box aria-hidden className="size-3.5" style={{ color: "var(--type-object)" }} />Answer schema</span>
          <div className="flex flex-col gap-0.5 rounded-md border p-2 font-mono text-xs">
            {ANSWERS[kind].map(([key, type]) => <span key={key} className="flex items-center gap-2"><TypeIcon type={type} />{key}</span>)}
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label text="Post-processing" />
          {post}
        </div>
      </div>
    </div>
  )
}

/** A record's fields, if `record` is one: a table of each one's name, what it is and its
 * sources, each opened to change it; a new one added under them. `children` for a variable that
 * isn't a record (nothing while it's asked). */
export function RecordFields({ record, children }: { record: string; children?: ReactNode }) {
  const [weighed, setWeighed] = useState<Weighed | null | undefined>(undefined)
  const [open, setOpen]       = useState<{ key: string; source: number } | null>(null)
  const [adding, setAdding]   = useState(false)
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
      <section data-record className="flex flex-col gap-1.5 border-t pt-4">
        <Heading text="Fields" onAdd={adding ? undefined : () => setAdding(true)} />
        <div className="rounded-md border">
          <div className={cn(GRID, "border-b bg-muted/40 py-1 pr-9 pl-2 text-xs text-muted-foreground")}>
            <span>Name</span><span>What it is</span><span title="the first source with a value wins">Sources, first wins</span>
          </div>
          {weighed.fields.map((field) => (
            <FieldRow key={field.key} field={field} weighed={weighed} onChange={change}
                      open={open?.key === field.key ? open.source : null}
                      onOpen={(source) => setOpen(source === null ? null : { key: field.key, source })}
                      onRenamed={(key) => setOpen((o) => o && { ...o, key })} />
          ))}
          {adding && <AddRow grid={GRID} onClose={() => setAdding(false)} onAdd={async (key, desc) => {  // set by you, until it's given other sources
            const said = await change({ op: "define", field: { key, desc, srcs: [{ from: "user" }] } })
            if (!said) setOpen({ key, source: 0 })
            return said
          }} />}
        </div>
      </section>
    </TooltipProvider>
  )
}

/** A source as a chip, its icon before its name: what it means as you hover it (under a
 * TooltipProvider). */
export function Chip({ name, active, onClick, onRemove, ...drag }: {
  name: SourceName
  active?: boolean
  onClick?: (e: React.MouseEvent) => void
  onRemove?: () => void
} & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span {...drag} onClick={onClick}
              className={cn(TAG, "cursor-pointer", SOURCES[name].chip, active && "ring-2 ring-ring/60", drag.draggable && "cursor-grab")}>
          <Mark icon={SOURCES[name].icon} />
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

/** A chip's look, and its icon: a source's, or what reads a name. */
export const TAG = "inline-flex h-5 items-center gap-1 rounded-full px-2 font-mono text-xs font-medium whitespace-nowrap select-none"
export const Mark = ({ icon: Icon }: { icon: LucideIcon }) => <Icon aria-hidden className="size-3 shrink-0" strokeWidth={2.25} />

/** An open field, as a variable's dialog shows one: its name and what it is, changed where they
 * are; its type; its sources in order (a chip each, clicked to open it, dragged to reorder, a new one added
 * from the list); Reset or Delete by the close button. */
function Editor({ field, weighed, onRenamed, onChange }: {
  field: Field
  weighed: Weighed
  onRenamed: (key: string) => void
  onChange: Change
}) {
  const [dragged, setDragged] = useState<number | null>(null)
  const [viewing, setViewing] = useState<number | null>(null)  // the source whose dialog is open (one past the last: a new one)
  const [fresh, setFresh]     = useState<Source | null>(null)  // the new one being made
  const [error, setError]     = useState("")
  const [adding, setAdding]   = useState(false)
  const missing = NAMES.filter((n) => !field.srcs.some((s) => s.from === n))
  const define  = async (f: Partial<Field>) => (await onChange({ op: "define", field: { key: field.key, desc: field.desc, type: field.type, srcs: field.srcs, ...f } })) || null
  const rename  = async (text: string) => {
    const to      = text.trim()
    const mistake = await onChange({ op: "rename", key: field.key, to })
    if (!mistake) onRenamed(to)
    return mistake || null
  }
  const move = async (from: number, to: number) => {
    const next = [...field.srcs]
    next.splice(to, 0, ...next.splice(from, 1))
    setError((await define({ srcs: next })) ?? "")
  }
  const gone = async () => {
    const mistake = await onChange({ op: "remove", key: field.key })
    setError(mistake)
  }
  const add = async (name: SourceName) => {
    const made = SOURCES[name].fresh
    if (name === "user" || name === "auto") return setError((await define({ srcs: [...field.srcs, made] })) ?? "")  // nothing to fill in
    setFresh(made)
    setViewing(field.srcs.length)
  }
  const record = weighed.record ?? "work.tasks"

  return (
    <Staging onSave={async (patch) => (await define(patch as Partial<Field>)) || null}>
      <DialogHeader>
        <DialogTitle className="flex min-w-0 items-center gap-2 pr-16 font-mono">
          <TypeIcon type={field.worked} className="size-4" />
          <span className="flex min-w-0 items-baseline">
            <span className="shrink-0">{record}[i].</span>
            <Editable label="Name" value={field.key} onSave={field.shipped ? undefined : rename} title={field.shipped ? "Built-in fields keep their name" : undefined} className="-mb-1 truncate pb-1 text-foreground" />
          </span>
        </DialogTitle>
        <DialogDescription asChild>
          <div><Editable label="Description" value={field.desc} long placeholder="No description" onSave={(t) => define({ desc: t })} /></div>
        </DialogDescription>
      </DialogHeader>
      <div className="absolute top-2 right-10">
        <DeleteField field={field} weighed={weighed} onDelete={gone} size="icon-sm" />
      </div>

      <dl className="grid grid-cols-[6rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 border-t pt-4 text-xs">
        <Term>Type</Term>
        <dd><TypeChange type={field.worked} own={field.type === "any" ? undefined : field.type} editable /></dd>
        <ItemChange type={field.worked} own={field.type === "any" ? undefined : field.type} editable />
        <Term hint="the first source with a value wins">Written by</Term>
        <dd className="flex flex-wrap items-center gap-1.5">
          {field.srcs.map((s, i) => (
            <Chip key={s.from} name={s.from} onClick={() => setViewing(i)}
                  onRemove={async () => setError((await define({ srcs: field.srcs.filter((_, j) => j !== i) })) ?? "")}
                  draggable onDragStart={() => setDragged(i)} onDragOver={(e) => e.preventDefault()}
                  onDrop={() => dragged !== null && dragged !== i && move(dragged, i)} onDragEnd={() => setDragged(null)} />
          ))}
          {missing.length > 0 && (
            <Popover open={adding} onOpenChange={setAdding}>
              <PopoverTrigger asChild>
                <button type="button" aria-label="add a source" className="h-5 cursor-pointer rounded-full border border-dashed px-2 text-xs text-muted-foreground hover:bg-muted">+ source</button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-auto min-w-36 gap-0 p-1">
                {missing.map((n) => (
                  <button key={n} type="button" onClick={() => (setAdding(false), add(n))} className="flex w-full rounded-sm px-2 py-1 text-left hover:bg-muted">
                    <Chip name={n} />
                  </button>
                ))}
              </PopoverContent>
            </Popover>
          )}
          {field.srcs.length === 0 && <span className="text-muted-foreground">none: always empty</span>}
        </dd>
      </dl>

      <StagedFields name={field.key} type={field.worked} own={field.type === "any" ? undefined : field.type} />
      {error && <p className="text-xs text-destructive">{error}</p>}
      {viewing !== null && (field.srcs[viewing] || fresh) && (
        <SourceDialog field={field} weighed={weighed} index={viewing} fresh={viewing === field.srcs.length ? fresh ?? undefined : undefined} onChange={onChange}
                      onClose={() => (setViewing(null), setFresh(null))} />
      )}
    </Staging>
  )
}

/** A type, said; where the dialog stages (`editable`), its kind picked from a list as you point at it, and
 * what's inside it changed under it, both kept with the dialog's Save. `own`: the one you gave (none:
 * worked out). */
export function TypeChange({ type, own, editable, kinds = TYPES, at = "type" }: { type?: Type; own?: Type; editable?: boolean; kinds?: string[]; at?: string }) {
  const staged = useStaged()
  const was    = own ?? type ?? "any"
  const draft  = staged?.patch[at] as Type | undefined
  const now    = draft ?? was
  const name   = (t: Type | undefined) => <span style={{ color: `var(--type-${kindOf(t ?? "any")})` }}>{t && t !== "any" ? said(t) : "any"}</span>
  if (!editable || !staged) return name(type)
  return (
    <div className="flex flex-col gap-2">
      <span className="flex items-center gap-1.5">
        <Pick label="Type" value={kindOf(now)} changed={draft !== undefined} options={kinds.map((t) => [t, <><TypeIcon type={t} />{t}</>])}
              onPick={(k) => staged.put(at, typed(picked(k, schemaOf(now))), was)}>{name(now)}</Pick>
        {!own && type && type !== "any" && draft === undefined && <span className="text-muted-foreground">(worked out)</span>}
      </span>
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
        <div className="grid grid-cols-[8rem_minmax(0,1fr)_2rem] items-center gap-3 border-b bg-muted/40 py-1 pr-1 pl-2 text-xs text-muted-foreground">
          <span>{fixed ? "Label" : label}</span><span>Meaning</span><span />
        </div>
        {rows.map(([name, means], i) => (
          <div key={i} className="grid grid-cols-[8rem_minmax(0,1fr)_2rem] items-center gap-3 border-b py-1 pr-1 pl-2 last:border-b-0">
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
const schemaOf = (t: Type): Schema => (typeof t === "string" ? SCHEMAS[t === "array" ? "list" : t] ?? {} : t)

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
export function TypeField({ label, value, inherit, fixed, alone, kinds, onChange }: {
  label: string; value: Type | undefined; inherit?: boolean; fixed?: boolean; alone?: boolean; kinds?: string[]; onChange?: (type: Type | undefined) => void
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        {label && <Label text={label} />}
        <Kind value={kindOf(value)} inherit={inherit} fixed={fixed} kinds={kinds}
              onChange={(k) => onChange?.(k === "inherit" ? undefined : typed(picked(k, value === undefined ? {} : schemaOf(value))))} />
        {value !== undefined && !alone && <OneOf value={schemaOf(value)} />}
      </div>
      {value !== undefined && !alone && <Inside value={schemaOf(value)} fixed={fixed} onChange={(s) => onChange?.(typed(s))} />}
    </div>
  )
}

/** The names of an object type's fields (none: not an object). */
export const fieldKeys = (type?: Type): string[] => (kindOf(type) === "object" && type ? Object.keys(((schemaOf(type).properties ?? {}) as object)) : [])

/** An object variable's fields (or those of each item of a list of objects), held in the dialog's type and kept with its Save: `SchemaFields`, as the dialog's own. */
export function StagedFields({ name, type, own, at = "type" }: { name: string; type?: Type; own?: Type; at?: string }) {
  const st  = useStaged()
  const was = own ?? type ?? "any"
  return st ? <SchemaFields name={name} type={(st.patch[at] as Type | undefined) ?? was} onChange={(t) => st.put(at, t, was)} /> : null
}

/** The fields of an object type (or of each item of a list of objects), as a table like a record's: a row each, its name and what it
 * is, the row's trash as you point at it, a click opening the field; a new one added under them with its description. */
export function SchemaFields({ name, type, onChange }: { name: string; type: Type; onChange: (type: Type) => void }) {
  const [open, setOpen]     = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const schema = schemaOf(type)
  const list   = kindOf(type) === "list"
  const holder = list ? ((schema.items ?? {}) as Schema) : schema
  if (kindOf(holder) !== "object") return null
  const props  = Object.entries((holder.properties ?? {}) as Record<string, Schema>)
  const put    = (next: [string, Schema][]) => {
    const inner = { ...holder, properties: Object.fromEntries(next) }
    onChange(typed(list ? { ...schema, items: inner } : inner))
  }
  const at     = (key: string, to: string, s: Schema) => put(props.map(([k, old]) => (k === key ? [to, s] : [k, old])))
  const add    = async (key: string, desc: string) => props.some(([k]) => k === key) ? `${key} is already there`
                                                     : (put([...props, [key, { type: "string", ...(desc ? { description: desc } : {}) }]]), "")
  const row    = "grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] items-center gap-3"
  const spec   = props.find(([k]) => k === open)
  return (
    <section className="flex flex-col gap-1.5 border-t pt-4">
      <Heading text="Fields" onAdd={adding ? undefined : () => setAdding(true)} />
      <div className="rounded-md border">
        <div className={cn(row, "border-b bg-muted/40 py-1 pr-9 pl-2 text-xs text-muted-foreground")}><span>Name</span><span>What it is</span></div>
        {props.map(([key, s]) => (
          <div key={key} className="group/row relative border-b last:border-b-0">
            <div role="button" tabIndex={0} onClick={() => setOpen(key)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setOpen(key)}
                 className={cn(row, "cursor-pointer py-1.5 pr-9 pl-2 text-xs hover:bg-muted/60")}>
              <span className="flex min-w-0 items-center gap-1.5"><TypeIcon type={s as Type} /><code className="truncate font-semibold">{key}</code></span>
              <span className="truncate text-muted-foreground">{String(s.description ?? "") || "–"}</span>
            </div>
            <Button type="button" size="icon-xs" variant="ghost" aria-label={`Delete ${key}`} title="Delete" onClick={() => put(props.filter(([k]) => k !== key))}
                    className="absolute top-1/2 right-1.5 -translate-y-1/2 text-destructive opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100"><Trash2 /></Button>
          </div>
        ))}
        {props.length === 0 && !adding && <p className="px-2 py-1.5 text-xs text-muted-foreground">None.</p>}
        {adding && <AddRow grid={row} onAdd={add} onClose={() => setAdding(false)} />}
      </div>
      {open && spec && (
        <Dialog open onOpenChange={(to) => !to && setOpen(null)}>
          <DialogContent className="sm:max-w-lg" onEscapeKeyDown={typing}>
            <DialogHeader>
              <DialogTitle className="flex min-w-0 items-center gap-2 pr-8 font-mono text-sm">
                <TypeIcon type={spec[1] as Type} className="size-4" />
                <span className="flex min-w-0 items-baseline">
                  <span className="shrink-0">{`${name}${list ? "[i]" : ""}.`}</span>
                  <Editable label="Name" value={spec[0]} className="truncate text-foreground" onSave={async (t) => {
                    const to = t.trim()
                    if (!to || (to !== spec[0] && props.some(([k]) => k === to))) return `${to || "A field"} is already there`
                    at(spec[0], to, spec[1])
                    setOpen(to)
                    return null
                  }} />
                </span>
              </DialogTitle>
              <DialogDescription asChild>
                <div><Editable label="Description" long placeholder="No description" value={String(spec[1].description ?? "")} onSave={async (t) => (at(spec[0], spec[0], { ...spec[1], description: t }), null)} /></div>
              </DialogDescription>
            </DialogHeader>
            <dl className="grid grid-cols-[6rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 border-t pt-4 text-xs">
              <dt className="text-muted-foreground">Type</dt>
              <dd>
                <Pick label="Type" value={kindOf(spec[1])} options={TYPES.map((t) => [t, <><TypeIcon type={t} />{t}</>])}
                      onPick={(k) => at(spec[0], spec[0], { ...picked(k, spec[1]), ...(spec[1].description ? { description: spec[1].description } : {}) })}>
                  <span style={{ color: `var(--type-${kindOf(spec[1])})` }}>{kindOf(spec[1])}</span>
                </Pick>
              </dd>
              {kindOf(spec[1]) === "list" && (
                <>
                  <dt className="text-muted-foreground">Item</dt>
                  <dd>
                    <Pick label="Item" value={kindOf((spec[1].items ?? {}) as Type)} options={TYPES.filter((t) => t !== "list").map((t) => [t, <><TypeIcon type={t} />{t}</>])}
                          onPick={(k) => at(spec[0], spec[0], { ...spec[1], items: picked(k, (spec[1].items ?? {}) as Schema) })}>
                      <span style={{ color: `var(--type-${kindOf((spec[1].items ?? {}) as Type)})` }}>{kindOf((spec[1].items ?? {}) as Type)}</span>
                    </Pick>
                  </dd>
                </>
              )}
            </dl>
            <SchemaFields name={`${name}${list ? "[i]" : ""}.${spec[0]}`} type={spec[1] as Type}
                          onChange={(t) => at(spec[0], spec[0], { ...schemaOf(t), ...(spec[1].description ? { description: spec[1].description } : {}) })} />
          </DialogContent>
        </Dialog>
      )}
    </section>
  )
}

/** What's inside a type, a section of its own: an object's fields, a list's items' type (nothing
 *  for a type with nothing inside). */
export function TypeInside({ value, onChange }: { value: Type; onChange: (type: Type) => void }) {
  const kind = kindOf(value)
  if (kind !== "object" && kind !== "list") return null
  return (
    <section className="flex flex-col gap-2 border-t pt-4">
      {kind === "object" && <Label text="Fields" />}
      <Inside value={schemaOf(value)} flat onChange={(s) => onChange(typed(s))} />
    </section>
  )
}

/** A type's kind, picked from them all, each with its icon. */
function Kind({ value, inherit, fixed, kinds = TYPES, onChange }: { value: string; inherit?: boolean; fixed?: boolean; kinds?: string[]; onChange: (kind: string) => void }) {
  if (fixed) return <span className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground"><TypeIcon type={value} />{value}</span>
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" aria-label="type" className="min-w-28 font-mono text-xs"><SelectValue /></SelectTrigger>
      <SelectContent position="popper" className="font-mono">
        {inherit && <SelectItem value="inherit" className="text-xs">its type</SelectItem>}
        {kinds.map((t) => <SelectItem key={t} value={t} className="text-xs"><TypeIcon type={t} />{t}</SelectItem>)}
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
            {!fixed && <Button variant="ghost" size="icon-xs" aria-label={`remove ${key}`} onClick={() => put(props.filter((_, j) => j !== i))}><Trash2 /></Button>}
          </div>
          <Inside value={s} fixed={fixed} onChange={(s) => at(i, key, s)} />
        </div>
      ))}
      {!props.length && fixed && <p className="text-xs text-muted-foreground">No fields.</p>}
      {!fixed && <Button variant="ghost" size="sm" className="w-fit text-xs" onClick={() => put([...props, [fresh, {}]])}><Plus /> Field</Button>}
    </div>
  )
}

/** What every one of a channel's questions is read under: kept with the dialog's Save. */
function Context({ text }: { text: string }) {
  const st = useStaged()!
  return (
    <div className="flex flex-col gap-1.5">
      <Label text="Context" />
      <div className="rounded-md border px-2 py-1 text-xs focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50">
        <Template strings value={(st.patch.shared as string | undefined) ?? text} onChange={(e) => st.put("shared", e.target.value, text)} aria-label="Context" className="min-h-16" />
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

/** A section's name, and its `+ Add` at the end of the line (none: nothing to add now). */
function Heading({ text, onAdd }: { text: string; onAdd?: () => void }) {
  return (
    <div className="flex h-6 items-center justify-between gap-2">
      <Label text={text} />
      {onAdd && <AddButton onClick={onAdd} />}
    </div>
  )
}

/** A new row at a table's end, its name and description typed where they'll be: added on Enter (the mistake, if any, under
 * it); Escape, or leaving it empty, takes it away. `grid`: the table's columns. */
function AddRow({ grid, onAdd, onClose }: { grid: string; onAdd: (key: string, desc: string) => Promise<string>; onClose: () => void }) {
  const [key, setKey]     = useState("")
  const [desc, setDesc]   = useState("")
  const [error, setError] = useState("")
  const keys = async (e: KeyboardEvent) => {
    if (e.key === "Escape") return onClose()
    if (e.key !== "Enter" || !key.trim()) return
    const said = await onAdd(key.trim(), desc.trim())
    setError(said)
    if (!said) onClose()
  }
  return (
    <div className="border-b py-1 pr-9 pl-2 last:border-b-0" onBlur={(e) => !e.currentTarget.contains(e.relatedTarget) && !key.trim() && onClose()}>
      <div className={grid}>
        <Input {...PLAIN} autoFocus value={key} onChange={(e) => setKey(e.target.value)} onKeyDown={keys} placeholder="new_field" aria-label="Name" className={cn(BARE, "font-mono")} />
        <Input value={desc} onChange={(e) => setDesc(e.target.value)} onKeyDown={keys} placeholder="Description" aria-label="Description" className={BARE} />
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
    ...(expr?.trim() && expr.trim() !== "res" ? { expr: expr.trim() } : {}),
    ...(s.from === "jev" && s.type !== "noul" ? { criteria } : {}),
    ...(s.from === "llm" && schema !== undefined ? { schema } : {}),
  }
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

