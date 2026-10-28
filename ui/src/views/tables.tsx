// Tables: each kind of record (a task, a group, yours), its records as a table, a row each and a
// column a field: its id first, then its fields as you made them, then what proki works out for
// it, then when it was made and changed. A column's head sorts by it, again the other way; the
// search keeps the rows with it anywhere. A list or a record in a cell opens, as a table of its
// own. The kind you looked at is kept.

import { useEffect, useMemo, useState } from "react"
import { ArrowDown, ArrowUp, Check, Search, Table2, X } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Type, Weighed } from "@/lib/proki"
import { recallJson, rememberJson } from "@/lib/remember"
import { cn } from "@/lib/utils"
import { TypeIcon } from "@/views/fields"
import { atomic, Inspect, Opens } from "@/views/inspect"

const STAMPS = ["created_at", "updated_at"]  // every record's, last
type Column = { key: string; desc: string; type: Type | undefined }

export function TablesView() {
  const [kinds, setKinds]   = useState<string[]>([])
  const [kind, setKind]     = useState(() => recallJson("tables.kind", ""))
  const [read, setRead]     = useState<Weighed | null>(null)
  const [error, setError]   = useState("")
  const [query, setQuery]   = useState("")
  const [order, setOrder]   = useState<{ key: string; down: boolean } | null>(null)
  const [opened, setOpened] = useState<{ title: string; value: unknown } | null>(null)

  useEffect(() => {
    let live = true
    window.proki.fields({ op: "read", ...(kind ? { record: kind } : {}) }).then((answer) => {
      if (!live) return
      if (answer.error) return setError(answer.error)
      setError("")
      setKinds(answer.records)
      setRead(answer)
      if (!kind || !answer.records.includes(kind)) setKind(answer.records.includes("work.tasks") ? "work.tasks" : answer.records[0] ?? "")
    })
    return () => void (live = false)
  }, [kind])

  const columns = useMemo<Column[]>(() => {
    if (!read) return []
    const fields = read.fields.map((f) => ({ key: f.key, desc: f.desc, type: f.worked }))
    const worked = read.own.filter((k) => k !== "id" && !STAMPS.includes(k)).map((key) => ({ key, desc: "worked out by proki", type: undefined }))
    return [{ key: "id", desc: "", type: "integer" }, ...fields, ...worked, ...STAMPS.map((key) => ({ key, desc: key === "created_at" ? "made" : "last changed", type: "time" }))]
  }, [read])

  const rows = useMemo(() => {
    const found = (read?.rows ?? []).filter((r) => !query || JSON.stringify(Object.values(r.values)).toLowerCase().includes(query.toLowerCase()))
    if (!order) return found
    const at = (r: (typeof found)[number]) => r.values[order.key]
    return [...found].sort((a, b) => {
      const [x, y] = [at(a), at(b)]
      if (x == null || y == null) return x == null ? (y == null ? 0 : 1) : -1  // none last, either way
      const by = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true })
      return order.down ? -by : by
    })
  }, [read, query, order])

  const pick = (to: string) => (setKind(to), rememberJson("tables.kind", to), setOrder(null), setQuery(""))
  const sort = (key: string) => setOrder((o) => (o?.key === key ? (o.down ? null : { key, down: true }) : { key, down: false }))

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-4 px-8 pt-7 pb-6">
      <PageHeader title="Tables" beside={kinds.length > 0 && (
          <Tabs value={kind} onValueChange={pick}>
            <TabsList>{kinds.map((k) => <TabsTrigger key={k} value={k} className="font-mono text-xs">{k}</TabsTrigger>)}</TabsList>
          </Tabs>
        )}>
        <label className="relative">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search" aria-label={`Search ${kind || "the records"}`} className="h-8 w-56 pl-8 text-sm" />
        </label>
      </PageHeader>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {read && !read.rows.length ? (
        <Empty className="mt-6">
          <EmptyHeader>
            <EmptyMedia variant="icon"><Table2 /></EmptyMedia>
            <EmptyTitle>No records yet</EmptyTitle>
            <EmptyDescription>{kind}'s records show here as they're made.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : read && (
        <>
          <p className="-mt-2 text-xs text-muted-foreground tabular-nums">
            {query ? `${rows.length} of ${read.rows.length} records` : `${read.rows.length} record${read.rows.length === 1 ? "" : "s"}`} · {columns.length} fields
          </p>
          <div className="min-h-0 flex-1 overflow-hidden rounded-xl border [&>[data-slot=table-container]]:h-full [&>[data-slot=table-container]]:overflow-auto">
            <Table className="text-xs">
              <TableHeader className="sticky top-0 z-10 bg-background shadow-[inset_0_-1px_0_var(--border)]">
                <TableRow className="hover:bg-transparent">
                  {columns.map((c) => (
                    <TableHead key={c.key} aria-sort={order?.key === c.key ? (order.down ? "descending" : "ascending") : "none"} className="px-0">
                      <button onClick={() => sort(c.key)} title={[c.key, c.desc].filter(Boolean).join(" · ")}
                              className="flex h-full w-full items-center gap-1.5 px-3 font-mono font-medium whitespace-nowrap text-muted-foreground hover:text-foreground">
                        <TypeIcon type={c.type} />{c.key}
                        {order?.key === c.key && (order.down ? <ArrowDown className="size-3" /> : <ArrowUp className="size-3" />)}
                      </button>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id}>
                    {columns.map((c) => (
                      <TableCell key={c.key} className={cn("max-w-72 px-3 align-top", c.key === "id" && "text-muted-foreground")}>
                        <Cell value={r.values[c.key]} type={c.type} onOpen={(value) => setOpened({ title: `${r.name}.${c.key}`, value })} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
      <Inspect title={opened?.title ?? ""} value={opened?.value ?? null} open={opened !== null} onOpenChange={(to) => !to && setOpened(null)} />
    </div>
  )
}

/** A field's value in its cell: a time as a day and a time, yes or no as a tick or a cross, a
 * dash for none (an empty list too); a list or a record says what it holds, and opens. */
function Cell({ value, type, onOpen }: { value: unknown; type: Type | undefined; onOpen: (value: unknown) => void }) {
  if (value == null || (typeof value === "object" && !Object.keys(value).length)) return <span className="text-muted-foreground/60">–</span>
  if (!atomic(value)) return <Opens value={value} onOpen={() => onOpen(value)} />
  if (typeof value === "boolean") return value
    ? <Check aria-label="yes" className="size-3.5 text-emerald-600 dark:text-emerald-400" />
    : <X aria-label="no" className="size-3.5 text-muted-foreground" />
  if (type === "time" && typeof value === "number") {
    const at = new Date(value * 60_000)
    return <time dateTime={at.toISOString()} className="whitespace-nowrap tabular-nums">{at.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</time>
  }
  if (typeof value === "number") return <span className="tabular-nums">{Number.isInteger(value) ? value : value.toFixed(2)}</span>
  return <span title={String(value)} className="line-clamp-2 break-words">{String(value)}</span>
}
