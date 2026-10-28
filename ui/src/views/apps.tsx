// Apps: the apps and websites @classify knows, each with its label and how deep time on it is,
// who gave the label (you, proki's list, or jev and how sure), and whether it's tracked. A
// label picked here is yours (confirmed, never asked about again); one not tracked keeps its
// label. A filter by what's left to you, a search, and a sort by a column's head. Reloads
// when the window is focused.

import { useCallback, useEffect, useMemo, useState } from "react"
import { AppWindow, ArrowDown, ArrowUp, Globe, Search } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Badge } from "@/components/ui/badge"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { ago, type App, type Depth, type Label } from "@/lib/proki"

type Filter = "all" | "open" | "yours" | "untracked"
type Column = "key" | "label" | "set_at"

const FILTERS: { filter: Filter; title: string; keeps: (app: App) => boolean }[] = [
  { filter: "all", title: "All", keeps: () => true },
  { filter: "open", title: "To confirm", keeps: (app) => app.track !== false && !(app.label !== null && app.source === "usr") },
  { filter: "yours", title: "Confirmed", keeps: (app) => app.track !== false && app.label !== null && app.source === "usr" },
  { filter: "untracked", title: "Not tracked", keeps: (app) => app.track === false },
]

const DEPTH: Record<Depth, string> = {
  deep: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  shallow: "bg-sky-500/15 text-sky-700 dark:text-sky-400",
  neutral: "bg-muted text-muted-foreground",
  distraction: "bg-destructive/10 text-destructive",
}

export function AppsView() {
  const [apps, setApps] = useState<App[]>([])
  const [labels, setLabels] = useState<Label[]>([])
  const [filter, setFilter] = useState<Filter>("all")
  const [search, setSearch] = useState("")
  const [sort, setSort] = useState<{ by: Column; up: boolean }>({ by: "set_at", up: false })
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    const answer = await window.proki.apps({ op: "read" })
    if (answer.error) return setError(answer.error)
    setError("")
    setApps(answer.apps)
    setLabels(answer.labels)
  }, [])

  useEffect(() => {
    load()
    window.addEventListener("focus", load)
    return () => window.removeEventListener("focus", load)
  }, [load])

  // shown at once, then saved: a mistake puts it back as proki has it
  const change = async (app: App, changed: Partial<Pick<App, "label" | "track">>) => {
    const yours = "label" in changed ? { source: "usr", conf: null, track: true } : {}
    setApps((all) => all.map((a) => (a.key === app.key ? { ...a, ...yours, ...changed, set_at: new Date().toISOString() } : a)))
    const answer = await window.proki.apps({ op: "change", key: app.key, ...changed })
    if (answer.error) setError(answer.error)
    load()
  }
  const groups = useMemo(() => [...new Set(labels.map((label) => label.group))], [labels])

  const byId = useMemo(() => new Map(labels.map((label) => [label.id, label])), [labels])
  const labelOf = (app: App) => (app.label === null ? null : byId.get(app.label) ?? null)
  const shown = useMemo(() => {
    const keeps = FILTERS.find((f) => f.filter === filter)!.keeps
    const words = search.trim().toLowerCase()
    const value = (app: App) => (sort.by === "label" ? labelOf(app)?.name ?? "￿" : sort.by === "key" ? app.key.toLowerCase() : app.set_at)
    return apps
      .filter((app) => keeps(app) && (!words || `${app.key} ${labelOf(app)?.name ?? ""}`.toLowerCase().includes(words)))
      .sort((a, b) => (value(a) < value(b) ? -1 : value(a) > value(b) ? 1 : 0) * (sort.up ? 1 : -1))
  }, [apps, labels, filter, search, sort])

  const head = (by: Column, title: string) => (
    <button className="flex items-center gap-1 hover:text-foreground"
            onClick={() => setSort({ by, up: sort.by === by ? !sort.up : by !== "set_at" })}>
      {title}
      {sort.by === by && (sort.up ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
    </button>
  )

  return (
    <TooltipProvider>
      <div className="mx-auto max-w-5xl px-8 pt-7 pb-8">
        <PageHeader title="Apps & time" className="mb-5"
                    sub={<span className="tabular-nums">{apps.filter((a) => a.track).length} tracked · {apps.filter(FILTERS[1].keeps).length} to confirm</span>} />

        <div className="mb-4 flex items-center gap-3">
          <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
            <TabsList>
              {FILTERS.map(({ filter: f, title, keeps }) => (
                <TabsTrigger key={f} value={f}>
                  {title} <span className="text-muted-foreground tabular-nums">{apps.filter(keeps).length}</span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <div className="relative ml-auto w-64">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find an app or a label…" className="pl-8" />
          </div>
        </div>

        {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
        {shown.length === 0 ? (
          <Empty className="mt-6">
            <EmptyHeader>
              <EmptyMedia variant="icon"><AppWindow /></EmptyMedia>
              <EmptyTitle>{apps.length ? "Nothing matches" : "No apps yet"}</EmptyTitle>
              <EmptyDescription>
                {apps.length ? "Try another filter or search." : "As you use apps and websites, proki asks about them, and they show here."}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{head("key", "App or website")}</TableHead>
                <TableHead>{head("label", "Label")}</TableHead>
                <TableHead>Depth</TableHead>
                <TableHead>From</TableHead>
                <TableHead>{head("set_at", "Changed")}</TableHead>
                <TableHead className="text-right">Tracked</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((app) => {
                const label = labelOf(app)
                const site = app.key.includes(".") && !app.key.includes(" ")
                return (
                  <TableRow key={app.key} className={cn(app.track === false && "text-muted-foreground")}>
                    <TableCell>
                      <span className="flex min-w-0 items-center gap-2 font-medium">
                        {site ? <Globe className="size-3.5 shrink-0 text-muted-foreground" /> : <AppWindow className="size-3.5 shrink-0 text-muted-foreground" />}
                        <span title={app.key} className="max-w-[20rem] truncate">{app.key}</span>
                        {app.track === false && <Badge variant="outline" className="font-normal">not tracked</Badge>}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <select value={app.label ?? ""} onChange={(e) => change(app, { label: Number(e.target.value) })}
                                  aria-label={`${app.key}'s label`}
                                  className={cn("-ml-1.5 h-7 max-w-48 rounded-md bg-transparent px-1 text-sm outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                                                !label && "text-muted-foreground")}>
                            {!label && <option value="" disabled>– pick a label</option>}
                            {groups.map((group) => (
                              <optgroup key={group} label={group}>
                                {labels.map((l) => l.group === group && <option key={l.id} value={l.id}>{l.name}</option>)}
                              </optgroup>
                            ))}
                          </select>
                        </TooltipTrigger>
                        {label && <TooltipContent className="max-w-xs">{label.group}: {label.desc}</TooltipContent>}
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      {label && <span className={cn("rounded-md px-1.5 py-0.5 text-xs font-medium", DEPTH[label.depth])}>{label.depth}</span>}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{source(app)}</TableCell>
                    <TableCell className="text-xs whitespace-nowrap text-muted-foreground">{ago(app.set_at)}</TableCell>
                    <TableCell className="text-right">
                      <Switch checked={app.track !== false} onCheckedChange={(track) => change(app, { track })} aria-label={`track ${app.key}`} />
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </TooltipProvider>
  )
}

/** Who gave its label: you, proki's list, or jev and how sure. */
function source(app: App): string {
  if (app.label === null) return app.track === false ? "you: not tracked" : "not labeled yet"
  if (app.source === "usr") return "you"
  if (app.source === "dev") return "proki's list"
  return app.conf === null ? "jev" : `jev, ${Math.round(app.conf * 100)}% sure`
}
