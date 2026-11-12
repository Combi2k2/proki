// An action's parts as rows in its dialog: a label and a shaded box each, as the dialog for a new one has them.
// A list's rows add what its items look like, and a way to make one.

import { Fragment, useEffect, useState, type ReactNode } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { Reference, Type } from "@/lib/proki"
import { exprText, parseExpr } from "@/lib/typed"
import { Editable } from "@/views/in-place"
import { kindOf, schemaOf, TypeIcon } from "@/views/fields"
import { Making } from "@/views/inspect"
import { Opens } from "@/views/value-parts"

export const NAMES = "proki-names"  // the names a field suggests: a <datalist> the page fills

type Rows  = [string, string, "text" | "expr"][]
type Field = (key: string, how: "text" | "expr") => Omit<React.ComponentProps<typeof Editable>, "label">

/** What each kind of action says in its dialog, a row each: [label, the param, how it's read]. A kind
 * not here (a poke, a question) is changed in its own form. */
export const ACTION_ROWS: Record<string, Rows> = {
  set:    [["Set", "name", "text"], ["To", "expr", "expr"], ["When", "when", "text"]],
  add:    [["Add", "expr", "expr"], ["To", "name", "text"], ["When", "when", "text"]],
  sub:    [["Subtract", "expr", "expr"], ["From", "name", "text"], ["When", "when", "text"]],
  append: [["List", "name", "text"], ["Item", "expr", "expr"], ["When", "when", "text"]],
  remove: [["List", "name", "text"], ["Index", "id", "text"], ["When", "when", "text"]],
  open:   [["Page", "path", "text"]],
  lock:   [],
}
const HINTS: Record<string, string> = { name: "pokes", expr: "pokes + 1", when: "always", id: "todo.id", path: "'tasks'" }

/** A form's rows: each part's text as the params hold it, and how a change to it is kept. */
export const rowField = (params: Record<string, unknown>, set: (key: string, value: unknown) => void): Field => (key, how) => ({
  value: how === "expr" ? exprText(params[key]) : String(params[key] ?? ""),
  onSave: async (t) => (set(key, how === "expr" ? parseExpr(t) ?? undefined : t.trim() || undefined), null),
})

/** A list as the engine knows it: its type, and the record it is, if it's one. */
function useList(name: string) {
  const [found, setFound] = useState<{ type: Type; record?: string } | null>(null)
  useEffect(() => {
    const n = name.trim()
    let live = true
    if (!n) return setFound(null)
    ;(async () => {
      const [known, read] = await Promise.all([window.proki.tool("reference") as Promise<Reference>, window.proki.fields({ op: "read", record: n })])
      if (!live) return
      if (!read.error && read.records.includes(n)) {
        const properties = Object.fromEntries(read.fields.map((f) => [f.key, { ...schemaOf(f.worked ?? "any"), description: f.desc }]))
        return setFound({ record: n, type: { type: "array", items: { type: "object", properties } } as Type })
      }
      const v = known.variables.flatMap((x) => [x, ...((x as { fields?: Reference["variables"] }).fields ?? [])]).find((x) => x.name === n)
      setFound(v && kindOf(v.type) === "list" ? { type: v.type as Type } : null)
    })()
    return () => void (live = false)
  }, [name])
  return found
}

/** An action's rows. A list's (append, remove): once it names a list, an icon to see what an item holds; an append's
 * item, given the list has fields, an icon to make one. `kind`: the action's; `field`: each part's text and how it's kept. */
export function ActionRows({ kind, field }: { kind: string; field: Field }) {
  const rows  = ACTION_ROWS[kind] ?? []
  const found = useList(kind === "append" || kind === "remove" ? field("name", "text").value ?? "" : "")
  const [making, setMaking] = useState(false)
  const typed = parseExpr(field("expr", "expr").value)
  const parts = (typed && typeof typed === "object" && !Array.isArray(typed) ? typed : {}) as Record<string, string>  // the item as typed: each field's expression
  const props = Object.entries(((found?.type as { items?: { properties?: Record<string, Type> } } | undefined)?.items?.properties) ?? {})
  const aside = (key: string): ReactNode => {
    if (!found) return null
    if (key === "name") return (
      <Popover>
        <PopoverTrigger asChild><Button type="button" size="icon-sm" variant="ghost" aria-label="What an item holds" title="What an item holds"><TypeIcon type={(found.type as { items?: Type }).items ?? "any"} className="size-4" /></Button></PopoverTrigger>
        <PopoverContent align="end" className="w-64 gap-1 text-xs">
          {props.length === 0 ? <p className="text-muted-foreground">Not typed yet: an item can be anything.</p> : props.map(([k, t]) => (
            <div key={k} className="flex items-center gap-1.5"><TypeIcon type={t} /><code className="font-medium">{k}</code><span className="text-muted-foreground">{kindOf(t)}</span></div>
          ))}
        </PopoverContent>
      </Popover>
    )
    if (key === "expr" && kind === "append" && props.length > 0) return (
      <>
        <Opens value={parts} onOpen={() => setMaking(true)} className="mt-1.5 h-5 shrink-0 font-mono text-xs" />
        {making && <Making record={found.record} type={found.type} initial={parts} names={NAMES} sample={[]} title="New item" action="Use" onClose={() => setMaking(false)}
                           onAdd={(row) => {
                             void field("expr", "expr").onSave?.(exprText(Object.fromEntries(Object.entries({ ...parts, ...row }).filter(([, e]) => String(e ?? "").trim()))))  // each field as it was typed
                             setMaking(false)
                           }} />}
      </>
    )
    return null
  }
  return <RowFields rows={rows} field={field} aside={aside} />
}

/** Rows: each a label and a shaded box, read as one line and opened in full to change. `hints`: what an empty one says; `boxes`: a row's own box class; `aside`: beside a box; `label`: the labels' width; `joiner`: a word at the labels' end, in the code font, as "is" joins a name to what it stands for. */
export function RowFields({ rows, field, hints = HINTS, boxes, aside, label: width = "6rem", joiner }: {
  rows: Rows; field: Field; hints?: Record<string, string>; boxes?: Record<string, string>; aside?: (key: string) => ReactNode; label?: string; joiner?: string
}) {
  if (rows.length === 0) return null
  return (
    <dl style={{ gridTemplateColumns: `${width} minmax(0,1fr)` }} className={cn("grid items-start gap-x-3 gap-y-2 text-xs", !joiner && "border-t pt-4")}>
      {rows.map(([label, key, how]) => (
        <Fragment key={key}>
          {joiner ? <dt className="flex justify-between gap-2 py-1.5 pl-2 font-mono"><span className="truncate">{label}</span><span className="font-sans text-muted-foreground">{joiner}</span></dt>
                  : <dt className="py-1.5 text-muted-foreground">{label}</dt>}
          <dd className="flex items-start gap-1">
            <Editable label={label} code long clamp list={NAMES} placeholder={hints[key] ?? "–"} className={cn("w-full min-w-0 flex-1 rounded-md bg-muted px-2 py-1.5 text-xs", boxes?.[key])} {...field(key, how)} />
            {aside?.(key)}
          </dd>
        </Fragment>
      ))}
    </dl>
  )
}
