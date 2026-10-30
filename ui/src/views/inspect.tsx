// A value too big for a line, as a table: a list of records a row each and a column a field, a
// list of plain values a row each by its place, a record a row a field. A cell too big for
// itself (a list, a record) says what it holds, and opens in the table's place; the trail
// above goes back.

import { useState, type ReactNode } from "react"
import { ChevronRight } from "lucide-react"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { cn } from "@/lib/utils"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { shown } from "@/views/program-inspect"

type Step = { label: string; value: unknown }

/** Whether a value fits a cell as it is: not a list, not a record (an empty one says "none"). */
export const atomic = (value: unknown) => value === null || typeof value !== "object" || Object.keys(value).length === 0

const isRecord = (value: unknown): value is Record<string, unknown> => !atomic(value) && !Array.isArray(value)

/** A value as a cell says it: text as it is, yes or no, a dash for none. */
function plain(value: unknown): string {
  if (value !== null && typeof value === "object") return "none"
  if (typeof value === "string") return value
  if (typeof value === "boolean") return value ? "yes" : "no"
  return shown(value)
}

/** What a list or a record holds, to open: "3 items", "4 fields". */
function holds(value: unknown): string {
  if (Array.isArray(value)) return value.length === 1 ? "1 item" : `${value.length} items`
  const n = Object.keys(value as object).length
  return n === 1 ? "1 field" : `${n} fields`
}

/** A cue to open what's too big for a line: what it holds, and an arrow. */
export function Opens({ value, onOpen, className }: { value: unknown; onOpen: () => void; className?: string }) {
  return (
    <button type="button" onClick={(e) => (e.stopPropagation(), onOpen())}
            className={cn("-mx-1 inline-flex items-center gap-0.5 rounded px-1 whitespace-nowrap text-muted-foreground underline decoration-dotted underline-offset-2 hover:bg-muted hover:text-foreground", className)}>
      {holds(value)}<ChevronRight className="size-3" />
    </button>
  )
}

export function Inspect({ title, value, open, onOpenChange, about }: {
  title: string
  value: unknown
  open: boolean
  onOpenChange: (open: boolean) => void
  about?: string
}) {
  const [trail, setTrail] = useState<Step[]>([])
  const at   = trail.length ? trail[trail.length - 1].value : value
  const into = (label: string, inner: unknown) => setTrail([...trail, { label, value: inner }])
  const cell = (label: string, inner: unknown): ReactNode =>
    atomic(inner) ? <span className="whitespace-pre-wrap">{plain(inner)}</span> : <Opens value={inner} onOpen={() => into(label, inner)} />

  return (
    <Dialog open={open} onOpenChange={(to) => (setTrail([]), onOpenChange(to))}>
      <DialogContent className="flex max-h-[80vh] flex-col sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-1 font-mono text-sm">
            {[{ label: title, value }, ...trail].map((step, i, all) => i < all.length - 1 ? (
              <span key={i} className="inline-flex items-center gap-1">
                <button className="text-muted-foreground hover:text-foreground" onClick={() => setTrail(trail.slice(0, i))}>{step.label}</button>
                <ChevronRight className="size-3 text-muted-foreground" />
              </span>
            ) : <span key={i}>{step.label}</span>)}
          </DialogTitle>
          <DialogDescription>{(!trail.length && about) || (at !== null && typeof at === "object" ? holds(at) : "A single value.")}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 overflow-auto rounded-lg border">
          <Grid value={at} cell={cell} />
        </div>
      </DialogContent>
    </Dialog>
  )
}

/** The table a value makes: its rows and columns, each cell as `cell` says it. */
function Grid({ value, cell }: { value: unknown; cell: (label: string, inner: unknown) => ReactNode }) {
  const head = (names: string[]) => (
    <TableHeader className="sticky top-0 bg-background">
      <TableRow>{names.map((n, i) => <TableHead key={i} className={i === 0 ? "w-10 text-right text-muted-foreground" : "font-mono"}>{n}</TableHead>)}</TableRow>
    </TableHeader>
  )
  const index = (i: number | string) => <TableCell className="w-10 text-right align-top text-muted-foreground tabular-nums">{i}</TableCell>

  if (atomic(value)) return <p className="p-3 font-mono text-sm whitespace-pre-wrap">{plain(value)}</p>

  if (Array.isArray(value) && value.every(isRecord)) {
    const columns = [...new Set(value.flatMap((r) => Object.keys(r)))]
    return (
      <Table className="text-xs">
        {head(["#", ...columns])}
        <TableBody>
          {value.map((r, i) => (
            <TableRow key={i}>
              {index(i)}
              {columns.map((c) => <TableCell key={c} className="max-w-64 align-top font-mono tabular-nums">{c in r ? cell(`[${i}].${c}`, r[c]) : ""}</TableCell>)}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  const rows: [string | number, unknown][] = Array.isArray(value) ? value.map((v, i) => [i, v]) : Object.entries(value as object)
  return (
    <Table className="text-xs">
      {head(Array.isArray(value) ? ["#", "value"] : ["", "value"])}
      <TableBody>
        {rows.map(([k, v]) => (
          <TableRow key={k}>
            {Array.isArray(value) ? index(k) : <TableCell className="w-px text-right align-top font-mono whitespace-nowrap text-muted-foreground">{k}</TableCell>}
            <TableCell className="align-top font-mono tabular-nums">{cell(Array.isArray(value) ? `[${k}]` : String(k), v)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
