// A value too big for a line, as a table over the window: a list of records a row each and a column
// a field, a list of plain values a row each, a record a row a field. A cell too big for itself
// (a list, a record) says what it holds, and opens in the table's place; the trail above goes back.
// Given `edit`, each plain value is changed where it's read; a list's rows are carried by their grips
// (to move them, or to the bin), added with +, and taken out with the bin; what's changed is marked
// and kept with Save.

import { useEffect, useMemo, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { DndContext, DragOverlay, PointerSensor, closestCenter, pointerWithin, useDroppable, useSensor, useSensors, type CollisionDetection, type DragEndEvent } from "@dnd-kit/core"
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { ChevronRight, Eye, EyeOff, GripVertical, Plus, RotateCcw, Trash2 } from "lucide-react"
import { Discard } from "@/components/discard"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { recallJson, rememberJson } from "@/lib/remember"
import type { Type } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { BARE, Expr } from "@/views/code"
import { kindOf, parsed, said, TypeIcon } from "@/views/fields"
import { at, same, useDraft, type Path } from "@/views/value-draft"
import { atomic, collection, holds, isRecord, Opens, plain, Scalar, WRAP } from "@/views/value-parts"

type Step = { label: string; path: Path }

const STAMPS = ["id", "created_at", "updated_at"]  // every record's own: hidden until asked for

export const APPS = "track.all"  // the apps seen: a list the app keeps, of which you change each one's track and label

/** Sends the pointer's own place first (the bin, a row), else the nearest row. */
const nearest: CollisionDetection = (args) => {
  const within = pointerWithin(args)
  return within.length ? within : closestCenter(args)
}

/** A value as a table, opened over the window (the panels too). `type`: what it is, for its icon. `edit`: keeps a changed
 * whole (the mistake, if any), and every plain value in it is changed where it's read (none: read only). `record`: the
 * variable's name, to know what a new row's fields take. */
export function Inspect({ title, type, value, open, onOpenChange, edit, record }: {
  title: string
  type?: Type
  value: unknown
  open: boolean
  onOpenChange: (open: boolean) => void
  edit?: (value: unknown) => Promise<string | null>
  record?: string
}) {
  const [trail, setTrail]       = useState<Step[]>([])
  const [error, setError]       = useState("")
  const [leaving, setLeaving]   = useState(false)
  const [adding, setAdding]     = useState(false)   // a plain value being typed for a new row
  const [making, setMaking]     = useState(false)   // a new record row being filled in
  const [numbers, setNumbers]   = useState(false)   // each row's place shown
  const [showHid, setShowHid]   = useState(false)
  const [hid, setHid]           = useState<string[]>(() => recallJson<string[] | null>(`value.hid.${title}`, null) ?? STAMPS)
  const [dragging, setDragging] = useState<number | null>(null)
  const [overBin, setOverBin]   = useState(false)
  const [yours, setYours] = useState<string[] | null>(null)  // a table of records: the fields set by you, the only ones changed here (none: any)
  useEffect(() => {
    if (!open || !edit || !record) return
    if (record === APPS) return setYours(["track", "label"])
    let live = true
    window.proki.fields({ op: "read", record }).then((read) => live && setYours(read.error || !read.records.includes(record) ? null : read.fields.filter((f) => f.srcs.some((s) => s.from === "user")).map((f) => f.key)))
    return () => void (live = false)
  }, [open, edit, record])
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }))
  const { base, draft, list, final, dirty, picked, reset, was, put, take, back, move, push, choose } =
    useDraft(value, !!edit, open, () => (setError(""), setAdding(false), setMaking(false)))

  const path  = trail.length ? trail[trail.length - 1].path : []
  const here  = at(draft, path)
  const root  = path.length === 0
  const rows  = Array.isArray(here) && record !== APPS ? (root && list ? list : null) : null  // the apps seen aren't added, taken out or moved
  const items = Array.isArray(here) ? (root && list ? here.filter((_, i) => !list[i]?.gone) : here) : null

  const into  = (label: string, p: Path) => setTrail([...trail, { label, path: p }])
  const cell = (label: string, inner: unknown, p: Path, kind?: Type): ReactNode => {
    if (collection(inner)) return <Opens value={inner} onOpen={() => into(label, p)} />
    const empty = emptyOf(kind)  // a list or a record not given yet opens as an empty one, to be filled in the table
    const theirs = yours && p.length > 1 && typeof p[0] === "number" && !yours.includes(String(p[1]))  // a field of a record that isn't set by you
    if (edit && inner == null && empty && !theirs) return <Opens value={empty} onOpen={() => (put(p, empty), into(label, p))} />
    if (!edit || theirs) return <Expr className={cn("whitespace-pre-wrap", WRAP)}>{plain(inner)}</Expr>
    const old = was(p)
    return <Scalar value={inner} string={typeof inner === "string"} flag={said(kind) === "boolean"} onPut={(v) => put(p, v)} changed={old.found && !same(old.value, inner)} />
  }

  const doomed = (key: number) => (picked.includes(key) ? picked : [key])  // what a row dragged to the bin takes with it
  const drop = (e: DragEndEvent) => {
    setDragging(null)
    setOverBin(false)
    if (!list || !e.over) return
    const from = Number(e.active.id)
    return e.over.id === "bin" ? take(doomed(list[from].key)) : move(from, Number(e.over.id))
  }
  const append = (to: unknown) => (push(to), setAdding(false), setMaking(false))
  const kind = elementKind(type, items ?? [])
  const grow = () => kind === "boolean" ? append(false) : kind === "object" ? setMaking(true) : setAdding(true)
  const taken = (list ?? []).filter((m) => m.gone).length  // what the bin holds: the rows taken out, kept until Save
  const dying = taken + (overBin && dragging !== null && list ? doomed(list[dragging].key).filter((k) => !list.find((m) => m.key === k)?.gone).length : picked.length)

  const keep = async () => {
    const mistake = await edit?.(final)
    if (mistake) return setError(mistake)
    reset(final)
  }
  const close = (to: boolean) => (!to && dirty ? setLeaving(true) : (setTrail([]), onOpenChange(to)))

  const records = Array.isArray(here) && (here.length > 0 ? here.every(isRecord) : !!propsOf(type))
  const columns = useMemo(() => (records ? [...new Set([...(here as Record<string, unknown>[]).flatMap((r) => Object.keys(r)), ...Object.keys(propsOf(type) ?? {})])] : []), [here, records, type])
  const kept   = columns.filter((c) => showHid || !hid.includes(c))
  const veiled = (c: string) => hid.includes(c)
  const veil   = (c: string) => {
    const next = veiled(c) ? hid.filter((h) => h !== c) : [...hid, c]
    setHid(next)
    rememberJson(`value.hid.${title}`, next)
  }
  const count  = hid.filter((c) => columns.includes(c)).length
  const crumbs = [{ label: title, path: [] as Path }, ...trail]
  const icon   = type ?? (Array.isArray(draft) ? "list" : "object")
  const lost   = (i: number) => !!list?.[i]?.gone
  const alive  = (list ?? []).map((m, i) => (m.was !== null && !m.gone ? i : -1)).filter((i) => i >= 0)  // the rows that were, as they stand
  const lowest = [...alive].sort((a, b) => list![a].was! - list![b].was!)
  const moved  = (i: number) => alive.indexOf(i) !== lowest.indexOf(i)
  const sayRow = (i: number) => {
    const r = (draft as unknown[])[i]
    return isRecord(r) ? Object.entries(r).filter(([k, v]) => kept.includes(k) && atomic(v)).map(([, v]) => plain(v)).join("  ") : plain(r)
  }
  const ghost  = dragging !== null && list ? doomed(list[dragging].key).length : 0
  const ANCHOR = "sticky left-0 z-10 w-8 px-1 text-right"

  return (
    <>
    <Dialog open={open} onOpenChange={close}>
      <DialogContent over className={cn("flex max-h-[80vh] flex-col", Array.isArray(here) ? (records ? "sm:max-w-3xl" : "sm:max-w-lg") : "sm:max-w-md")} onEscapeKeyDown={(e) => dirty && (e.preventDefault(), setLeaving(true))}>
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-x-1.5 gap-y-1 pr-8 font-mono text-sm">
            <TypeIcon type={icon} className="size-4" />
            {crumbs.map((step, i) => i < crumbs.length - 1 ? (
              <span key={i} className="inline-flex items-center gap-1">
                <button className="text-muted-foreground hover:text-foreground" onClick={() => setTrail(trail.slice(0, i))}>{step.label}</button>
                <ChevronRight className="size-3 text-muted-foreground" />
              </span>
            ) : <span key={i}>{step.label}</span>)}
            <span className="ml-1 font-sans text-xs font-normal text-muted-foreground">{here !== null && typeof here === "object" ? holds(items ?? here) : ""}</span>
          </DialogTitle>
          <DialogDescription className="sr-only">{title}</DialogDescription>
        </DialogHeader>
        <DndContext sensors={sensors} collisionDetection={nearest} onDragStart={(e) => setDragging(Number(e.active.id))} onDragOver={(e) => setOverBin(e.over?.id === "bin")}
                    onDragEnd={drop} onDragCancel={() => (setDragging(null), setOverBin(false))}>
          <div className="min-h-0 overflow-hidden rounded-lg border [&>[data-slot=table-container]]:max-h-[55vh] [&>[data-slot=table-container]]:overflow-auto">
            {!collection(here) ? <p className="p-3 text-sm">{cell(title, here, path)}</p> : (
              <Table className="text-xs">
                <TableHeader className="sticky top-0 z-20 bg-background shadow-[inset_0_-1px_0_var(--border)]">
                  <TableRow className="hover:bg-transparent">
                    {Array.isArray(here) ? <TableHead className={cn(ANCHOR, "z-30 bg-background text-muted-foreground")}>{numbers ? "#" : ""}</TableHead> : <TableHead />}
                    {Array.isArray(here) && records ? kept.map((c) => (
                      <TableHead key={c} className={cn("group/head font-mono", veiled(c) && "text-muted-foreground/60")}>
                        <span className="inline-flex items-center gap-1">
                          {c}
                          <button type="button" aria-label={`${veiled(c) ? "Show" : "Hide"} ${c}`} title={veiled(c) ? "Show it" : "Hide it"} onClick={() => veil(c)}
                                  className={cn("rounded text-muted-foreground hover:text-foreground", !veiled(c) && "opacity-0 group-hover/head:opacity-100")}>
                            {veiled(c) ? <Eye className="size-3" /> : <EyeOff className="size-3" />}
                          </button>
                        </span>
                      </TableHead>
                    )) : <TableHead className="font-mono">value</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <SortableContext items={(Array.isArray(here) ? here : []).map((_, i) => i)} strategy={verticalListSortingStrategy} disabled={!rows}>
                    {Array.isArray(here) ? here.map((r, i) => {
                      const number = list ? (here as unknown[]).slice(0, i).filter((_, j) => !list[j]?.gone).length : i
                      if (lost(i)) return (
                        <TableRow key={rows?.[i]?.key ?? i} className="bg-removed/10 text-muted-foreground">
                          <TableCell className={cn(ANCHOR, "bg-[color-mix(in_oklab,var(--removed)_10%,var(--popover))] align-top")}>
                            <button type="button" aria-label="Put it back" title="Put it back" onClick={() => back(i)} className="hover:text-foreground"><RotateCcw className="size-3.5" /></button>
                          </TableCell>
                          {records ? kept.map((c) => (
                            <TableCell key={c} className="max-w-64 align-top font-mono tabular-nums"><Expr className={cn("whitespace-pre-wrap", WRAP)}>{plain((r as Record<string, unknown>)[c])}</Expr></TableCell>
                          )) : <TableCell className="align-top font-mono"><Expr className={cn("whitespace-pre-wrap", WRAP)}>{plain(r)}</Expr></TableCell>}
                        </TableRow>
                      )
                      const added = !!list && list[i]?.was === null
                      return (
                        <Row key={rows?.[i]?.key ?? i} id={i} sortable={!!rows} added={added} number={numbers ? number : null} anchor={ANCHOR}
                             picked={!!rows && picked.includes(rows[i].key)} onPick={rows ? () => choose(rows[i].key) : undefined}
                             moved={!!rows && !added && moved(i)}>
                          {records ? kept.map((c) => (
                            <TableCell key={c} className={cn("max-w-64 align-top font-mono tabular-nums", veiled(c) && "text-muted-foreground/60")}>
                              {c in (r as object) ? cell(`[${number}].${c}`, (r as Record<string, unknown>)[c], [...path, i, c], propsOf(type)?.[c] as Type | undefined) : ""}
                            </TableCell>
                          )) : (
                            <TableCell className="align-top font-mono tabular-nums">{cell(`[${number}]`, r, [...path, i])}</TableCell>
                          )}
                        </Row>
                      )
                    }) : fieldsOf(here as Record<string, unknown>, root ? type : undefined).map(([k, v, kind]) => (
                      <TableRow key={k}>
                        <TableCell className="w-px text-right align-top font-mono whitespace-nowrap text-muted-foreground">{k}</TableCell>
                        <TableCell className="align-top font-mono tabular-nums">{cell(k, v, [...path, k], kind)}</TableCell>
                      </TableRow>
                    ))}
                    {adding && (
                      <TableRow>
                        <TableCell className={cn(ANCHOR, "bg-popover")} />
                        <TableCell colSpan={Math.max(1, records ? kept.length : 1)}>
                          <Fresh string={kind === "string"} onDone={(v) => (v === undefined ? setAdding(false) : append(v))} />
                        </TableCell>
                      </TableRow>
                    )}
                  </SortableContext>
                </TableBody>
              </Table>
            )}
          </div>
          {(Array.isArray(here) || records) && (
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {Array.isArray(here) && <label className="flex items-center gap-2"><Switch size="sm" aria-label="Show id" checked={numbers} onCheckedChange={setNumbers} />Show id</label>}
              {records && <label className="flex items-center gap-2"><Switch size="sm" aria-label="Show hidden" checked={showHid} onCheckedChange={setShowHid} />Show hidden {count > 0 && <span className="tabular-nums">{count}</span>}</label>}
              {rows && (
                <span className="ml-auto flex items-center gap-1">
                  <Button type="button" size="xs" variant="ghost" className="text-muted-foreground" aria-label="Append a row" onClick={grow}><Plus /> Append</Button>
                  <Bin count={dying} onClick={() => picked.length > 0 && take(picked)} />
                </span>
              )}
            </div>
          )}
          {createPortal(
            <DragOverlay zIndex={100} dropAnimation={null}>
              {ghost > 0 && dragging !== null && (
                <div className="flex max-w-md cursor-grabbing items-center gap-2 rounded-md border bg-popover px-3 py-1.5 font-mono text-xs shadow-lg ring-1 ring-foreground/10">
                  <GripVertical className="size-3.5 shrink-0 text-muted-foreground" />
                  <span className="truncate">{ghost > 1 ? `${ghost} rows` : sayRow(dragging)}</span>
                </div>
              )}
            </DragOverlay>, document.body)}
        </DndContext>
        {edit && (
          <div className={cn("flex shrink-0 flex-col gap-1.5 bg-popover", !dirty && "invisible")}>
            {error && <span className="text-xs break-words text-destructive">{error}</span>}
            <div className="flex justify-end gap-2">
              <Button type="button" size="sm" variant="ghost" onClick={() => reset(base)}>Cancel</Button>
              <Button type="button" size="sm" onClick={keep}>Save</Button>
            </div>
          </div>
        )}
        {making && <Making record={record} type={type} sample={items ?? []} onAdd={append} onClose={() => setMaking(false)} />}
      </DialogContent>
    </Dialog>
    <Discard open={leaving} onOpenChange={setLeaving} title="Drop the changes?" description="They aren't saved yet." action="Drop them"
             onDrop={() => (reset(base), setTrail([]), setTimeout(() => onOpenChange(false)))} />
  </>
  )
}

/** A record's fields: those it has, and those its type gives it that it has no value for yet (empty, to be filled in where they are read). */
function fieldsOf(value: Record<string, unknown>, type?: Type): [string, unknown, Type | undefined][] {
  const given = objectProps(type) ?? {}
  const keys  = [...new Set([...Object.keys(value), ...Object.keys(given)])]
  return keys.map((k) => [k, k in value ? value[k] : null, given[k] as Type | undefined])
}

const objectProps = (type?: Type) => (typeof type === "object" ? (type as { type?: string; properties?: Record<string, unknown> }) : undefined)?.properties
const propsOf = (type?: Type) => {
  const schema = typeof type === "object" ? (type as { items?: { properties?: Record<string, unknown> } }) : undefined
  return schema?.items?.properties
}

/** An empty list or record for a type that is one (none: a type that isn't). */
export const emptyOf = (type?: Type) => ({ list: [] as unknown, object: {} as unknown })[kindOf(type) as "list" | "object"]

/** A list or a record held where it's read, as `[…]` / `{…}` that opens its table; `onPut` keeps a changed whole (the mistake, if any). */
export function Collection({ value, type, title, onPut }: { value: unknown; type?: Type; title: string; onPut: (value: unknown) => Promise<string | null> }) {
  const [open, setOpen] = useState(false)
  const held = value ?? emptyOf(type) ?? []
  return (
    <>
      <Opens value={held} onOpen={() => setOpen(true)} />
      <Inspect title={title} type={type} value={held} open={open} onOpenChange={setOpen} edit={onPut} />
    </>
  )
}

/** What a list holds, by its type, else by what it already holds: yes or no, a record, else text or a number. */
function elementKind(type: Type | undefined, items: unknown[]): "boolean" | "object" | "string" | "number" {
  const schema = typeof type === "object" ? (type as { items?: { type?: string } }).items : undefined
  const said   = schema?.type ?? (items.length ? (items.every(isRecord) ? "object" : typeof items[0]) : "string")
  return said === "boolean" ? "boolean" : said === "object" ? "object" : said === "number" || said === "integer" ? "number" : "string"
}

/** One row of a list: its grip (carried to move it; clicked to choose it for the bin) and, when asked, its number; green when added,
 * a blue number when moved. */
function Row({ id, sortable, added, moved, number, anchor, picked, onPick, children }: {
  id: number; sortable: boolean; added: boolean; moved: boolean; number: number | null; anchor: string; picked: boolean; onPick?: () => void; children: ReactNode
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id, disabled: !sortable })
  return (
    <TableRow ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }}
              className={cn(added && "bg-added/10", picked && "bg-muted", isDragging && "opacity-40")}>
      <TableCell className={cn(anchor, "align-top text-muted-foreground tabular-nums", picked ? "bg-muted" : added ? "bg-[color-mix(in_oklab,var(--added)_10%,var(--popover))]" : "bg-popover")}>
        <span className="inline-flex items-center justify-end gap-0.5">
          {sortable && (
            <button type="button" {...attributes} {...listeners} onClick={onPick} aria-label={`Move or choose row ${number ?? id + 1}`} title="Drag to move, click to choose"
                    className={cn("cursor-grab touch-none hover:text-foreground", moved && "text-changed")}><GripVertical className="size-3.5" /></button>
          )}
          {number !== null && <span className={cn(moved && "underline decoration-changed decoration-2 underline-offset-4")}>{number}</span>}
        </span>
      </TableCell>
      {children}
    </TableRow>
  )
}

/** Where rows go to be deleted: the ones chosen, or the one dragged here, counted; red while there are some. */
function Bin({ count, onClick }: { count: number; onClick: () => void }) {
  const { setNodeRef } = useDroppable({ id: "bin" })
  return (
    <Button ref={setNodeRef} type="button" size="xs" variant="ghost" onClick={onClick} aria-label="Delete the chosen rows" title="Choose rows, or drop them here"
            className={cn("text-muted-foreground", count > 0 && "bg-destructive/15 text-destructive hover:bg-destructive/20 hover:text-destructive")}>
      <Trash2 /> {count > 0 ? `Delete ${count}` : "Delete"}
    </Button>
  )
}

/** A new plain value, typed in its row: Enter keeps it, leaving it empty drops it. */
function Fresh({ string, onDone }: { string: boolean; onDone: (value?: unknown) => void }) {
  const [text, setText] = useState("")
  const done = () => {
    if (text.trim() === "") return onDone(undefined)
    const v = parsed(text)
    onDone(string && typeof v !== "string" ? text : v)
  }
  return (
    <Input autoFocus aria-label="New value" value={text} spellCheck={false} placeholder="value" className={cn(BARE, "font-mono")}
           onChange={(e) => setText(e.target.value)} onBlur={done}
           onKeyDown={(e) => (e.key === "Enter" && (e.preventDefault(), done())) || (e.key === "Escape" && (e.stopPropagation(), onDone(undefined)))} />
  )
}

/** A new record row: the fields you set asked for, those that start by themselves filled in. */
function Making({ record, type, sample, onAdd, onClose }: { record?: string; type?: Type; sample: unknown[]; onAdd: (row: Record<string, unknown>) => void; onClose: () => void }) {
  type Ask = { key: string; type?: Type; ask: boolean; initial?: unknown }
  const [asks, setAsks] = useState<Ask[] | null>(null)
  const [given, setGiven] = useState<Record<string, unknown>>({})
  useEffect(() => {
    ;(async () => {
      const read = record ? await window.proki.fields({ op: "read", record }) : null
      if (read && !read.error && record && read.records.includes(record)) {
        return setAsks(read.fields.map((f) => ({ key: f.key, type: f.worked, ask: f.srcs.some((s) => s.from === "user"), initial: f.srcs.find((s) => s.from === "auto")?.initial })))
      }
      const props = propsOf(type) ?? {}
      const keys  = [...new Set([...Object.keys(props), ...sample.flatMap((r) => Object.keys((r ?? {}) as object))])]
      setAsks(keys.map((key) => ({ key, type: props[key] as Type | undefined, ask: true })))
    })()
  }, [record, type, sample])
  if (!asks) return null
  const made = Object.fromEntries(asks.filter((a) => !a.ask && a.initial !== undefined).map((a) => [a.key, a.initial]))
  return (
    <Dialog open onOpenChange={(to) => !to && onClose()}>
      <DialogContent over className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-sm">New row</DialogTitle>
          <DialogDescription className="sr-only">Fill in its fields.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col text-xs">
          {asks.filter((a) => a.ask).map((a) => (
            <div key={a.key} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] items-center gap-3 border-b py-1.5 last:border-b-0">
              <span className="flex min-w-0 items-center gap-1.5"><TypeIcon type={a.type} /><code className="truncate font-medium">{a.key}</code></span>
              {emptyOf(a.type)
                ? <Collection value={given[a.key]} type={a.type} title={a.key} onPut={async (v) => (setGiven({ ...given, [a.key]: v }), null)} />
                : <Scalar value={given[a.key] ?? null} string={said(a.type) === "string"} flag={said(a.type) === "boolean"} onPut={async (v) => (setGiven({ ...given, [a.key]: v }), null)} />}
            </div>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="button" size="sm" onClick={() => onAdd({ ...made, ...given })}>Add</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
