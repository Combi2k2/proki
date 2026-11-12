// Tables: each kind of record (a task, a group, yours), and each other list of records (every app seen),
// picked from a list, its records as the same table a list of records opens as anywhere: a row each and
// a column a field, changed where it's read, rows added, moved and taken out, all kept with Save. The
// search keeps the rows with it anywhere. The table you looked at is kept.

import { useCallback, useEffect, useMemo, useState } from "react"
import { PageHeader, SearchBox } from "@/components/page"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import type { Reference, Type, VarDetail, Weighed } from "@/lib/proki"
import { recallJson, rememberJson } from "@/lib/remember"
import { schemaOf } from "@/views/fields"
import { Inspect, matches } from "@/views/inspect"
import { useSetter } from "@/views/resources"

/** A list whose items are records: one with fields of its own. */
const tabled = (type?: Type) => typeof type === "object" && (type as { type?: string; items?: { properties?: object } }).type === "array" && !!(type as { items?: { properties?: object } }).items?.properties

const STAMPS = { id: { type: "integer" }, created_at: { type: "number", format: "time" }, updated_at: { type: "number", format: "time" } }  // every record's own

export function TablesView() {
  const [kinds, setKinds] = useState<string[]>([])
  const [kind, setKind]   = useState(() => recallJson("tables.kind", ""))
  const [read, setRead]   = useState<Weighed | null>(null)
  const [error, setError] = useState("")
  const [query, setQuery] = useState("")
  const [lists, setLists] = useState<VarDetail[]>([])  // the other lists of records: variables, set as a whole

  const load = useCallback(async () => {
    const [asked, known] = await Promise.all([window.proki.fields({ op: "read", ...(kind ? { record: kind } : {}) }), window.proki.tool("reference") as Promise<Reference>])
    const answer = asked.error && kind ? await window.proki.fields({ op: "read" }) : asked  // a list that isn't a kind of record: the kinds, from the tasks'
    if (answer.error) return setError(answer.error)
    setError("")
    const flat = known.variables.flatMap((v) => [v, ...((v as { fields?: VarDetail[] }).fields ?? [])])
    const more = flat.filter((v) => tabled(v.type) && !answer.records.includes(v.name))
    setLists(more)
    const all  = [...answer.records, ...more.map((v) => v.name)]
    setKinds(all.sort())
    setRead(answer)
    if (!kind || (!answer.records.includes(kind) && !more.some((v) => v.name === kind))) setKind(answer.records.includes("work.tasks") ? "work.tasks" : answer.records[0] ?? "")
  }, [kind])
  useEffect(() => void load(), [load])

  const list   = lists.find((v) => v.name === kind)
  const value  = useMemo(() => list ? (Array.isArray(list.value) ? list.value : []) : read?.rows.map((r) => r.values) ?? [], [list, read])
  const fields = useMemo(() => read?.fields ?? [], [read])
  const type   = useMemo(() => list?.type ?? ({ type: "array", items: { type: "object", properties: {
    ...STAMPS, ...Object.fromEntries(fields.map((f) => [f.key, { ...schemaOf(f.worked ?? "any"), description: f.desc }])) } } }) as Type, [list, fields])
  const count  = list ? Object.keys((type as { items: { properties: object } }).items.properties).length : fields.length
  const setter = useSetter(kind || undefined, !!kind, value)
  const keep   = setter && (async (to: unknown) => (await setter(to)) ?? (await load(), null))
  const found  = query ? value.filter((r) => matches(r, query)).length : value.length

  const pick = (to: string) => (setRead(null), setQuery(""), setKind(to), rememberJson("tables.kind", to))

  return (
    <div className="flex h-full flex-col gap-4 px-8 pt-7 pb-6">
      <PageHeader title="Tables" beside={kinds.length > 0 && (
          <Select value={kind} onValueChange={pick}>
            <SelectTrigger aria-label="Table" className="w-48 font-mono text-xs"><SelectValue /></SelectTrigger>
            <SelectContent position="popper">{kinds.map((k) => <SelectItem key={k} value={k} className="font-mono text-xs">{k}</SelectItem>)}</SelectContent>
          </Select>
        )}>
        <SearchBox value={query} onChange={setQuery} label={`Search ${kind || "the records"}`} />
      </PageHeader>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {read && (
        <>
          <p className="-mt-2 text-xs text-muted-foreground tabular-nums">
            {query ? `${found} of ${value.length} records` : `${value.length} record${value.length === 1 ? "" : "s"}`} · {count} fields
          </p>
          <div className="min-h-0 flex-1">
            <Inspect key={kind} inline open title={kind} type={type} value={value} onOpenChange={() => {}} edit={keep} record={kind} query={query} />
          </div>
        </>
      )}
    </div>
  )
}
