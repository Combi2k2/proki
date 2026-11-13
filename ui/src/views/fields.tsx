// A record's (a task's, a note's) fields, each with its sources, in order; the first with
// a value wins. A row opens its dialog, changed where it's read, one at a time.

import { useCallback, useEffect, useState, type ReactNode } from "react"
import { Box, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Confirm } from "@/components/confirm"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { TooltipProvider } from "@/components/ui/tooltip"
import type { Field, Source, SourceName, Type, Weighed } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { LABELS, Waiting } from "@/views/ask-actions"
import { TemplateBox } from "@/views/code"
import { ANSWERS, AddRow, Chip, Criteria, Heading, ItemChange, KindTabs, Pill, SOURCES, StagedFields, TypeChange, TypeIcon, kindOf, parsed } from "@/views/field-parts"
import { Editable, type Staged, Staging, Term, typing, useStaged } from "@/views/in-place"
import { Collection, emptyOf } from "@/views/inspect"
import { goToPlace, Places } from "@/views/places"
import { Detail, takeover } from "@/views/scope-shared"

type Change = (request: object) => Promise<string>

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
    <div className="group/row relative border-t">
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
      <DialogContent className={cn("max-h-[85vh] overflow-x-hidden overflow-y-auto", was.from === "expr" ? "sm:max-w-md" : "sm:max-w-lg")} onEscapeKeyDown={typing}>
        <TooltipProvider delayDuration={300}>
          <Staging onSave={save}>
            {(st) => {
              const now = { ...was, ...st.patch } as Source
              const post = (
                <Editable label="Post-processing" code long className="w-full rounded-md bg-muted px-2 py-1.5 text-xs" {...st.field("expr", was.expr || "res")} />
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
                  {was.from === "expr" && (  // as a signal's expression reads: the formula alone, in its shaded box
                    <>
                    <datalist id="record-names">{named.names.map((n) => <option key={n} value={n} />)}</datalist>
                    <Editable label="Formula" code long list="record-names" placeholder="me.estimate > 60" className="w-full rounded-md bg-muted px-2 py-1.5 text-xs" {...st.field("expr", String(was.expr ?? ""))} />
                    </>
                  )}
                  {was.from === "jev" && <JevForm now={now} was={was} st={st} named={named} post={post} />}
                  <dl hidden={was.from !== "auto"} className="spec-rows items-baseline">
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
  const kind = kindOf((st.patch.schema as Type | undefined) ?? was.schema ?? field.worked)
  const cols = { gridTemplateColumns: `${LABELS} minmax(0,1fr)` }
  return (
    <div className="flex flex-col gap-4 border-t pt-4">
      <TemplateBox label="Prompt" value={now.context ?? ""} changed={"context" in st.patch} onChange={(e) => st.put("context", e.target.value, was.context ?? "")} placeholder="How many hours will this take?" className="min-h-24" />
      <Waiting params={{ timeout: now.timeout }} was={{ timeout: was.timeout }} put={(_, v) => st.put("timeout", v, was.timeout)} wait={60} save={false} />
      <div className="flex flex-col gap-3 border-t pt-4 text-xs">
        <div style={cols} className="grid items-center gap-x-3 gap-y-2">
          <Label text="Answer schema" />
          <TypeChange type={field.worked} own={was.schema} editable at="schema" />
          {kind === "list" && <ItemChange type={field.worked} own={was.schema} editable at="schema" />}
        </div>
        <StagedFields flush name={field.key} type={field.worked} own={was.schema} at="schema" />
      </div>
      <div className="flex flex-col gap-1.5 border-t pt-4">
        <Label text="Post-processing" />
        {post}
      </div>
    </div>
  )
}

/** What a jev field's question is laid out as: its kind as tabs, what it's read under, the question, its options, then the answer it gives and what's done with it. */
function JevForm({ now, was, st, named, post }: {
  now: Source; was: Source; st: Staged; named: About; post: ReactNode
}) {
  const kind = now.type ?? "noul"
  return (
    <div className="flex flex-col gap-4">
      <KindTabs kind={kind} kinds={["noul", "choice", "score"]} changed={"type" in st.patch} onPick={(k) => st.put("type", k, was.type ?? "noul")} />
      {named.contexts && <Context text={named.contexts.jev} />}
      <TemplateBox label="Question" value={now.question ?? ""} changed={"question" in st.patch} onChange={(e) => st.put("question", e.target.value, was.question ?? "")} placeholder="Is this for school?" className="min-h-10" />
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
          <div className={cn(GRID, "bg-muted/40 py-1 pr-9 pl-2 text-xs text-muted-foreground")}>
            <span>Name</span><span>What it is</span><span title="the first source with a value wins">Sources, first wins</span>
          </div>
          {weighed.fields.map((field) => (
            <FieldRow key={field.key} field={field} weighed={weighed} onChange={change}
                      open={open?.key === field.key ? open.source : null}
                      onOpen={(source) => setOpen(source === null ? null : { key: field.key, source })}
                      onRenamed={(key) => setOpen((o) => o && { ...o, key })} />
          ))}
          {weighed.code.map((f) => (  // worked out by Proki's code: read here, never changed
            <div key={f.key} className={cn(GRID, "border-t py-1.5 pr-9 pl-2")}>
              <span className="flex min-w-0 items-center gap-1.5">
                <TypeIcon type={f.worked} />
                <code title={f.key} className="truncate text-xs font-semibold">{f.key}</code>
              </span>
              <span title={f.desc} className="truncate text-xs text-muted-foreground">{f.desc || "–"}</span>
              <span><Pill by="proki" means="Worked out by Proki, as it works" /></span>
            </div>
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

      <dl className="spec-rows items-center">
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

/** What every one of a channel's questions is read under: kept with the dialog's Save. */
function Context({ text }: { text: string }) {
  const st = useStaged()!
  return (
    <TemplateBox label="Context" value={(st.patch.shared as string | undefined) ?? text} changed={"shared" in st.patch} onChange={(e) => st.put("shared", e.target.value, text)} className="min-h-16" />
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

