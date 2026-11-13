// Apps: the apps and websites @classify knows, each with its icon, its label and how deep time on it is,
// who gave the label (user, dev or jev), and whether it's tracked. A label picked here is
// yours (confirmed, never asked about again); one not tracked keeps its label; one taken out is gone
// until it's seen again. A filter by what's left to you, a search (who gave the label, and the depth, too), and a sort by a
// column's head. Reloads when the window is focused.

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AppWindow, ArrowDown, ArrowUp, Globe, Search, Trash2 } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { ErrorDialog, unresolvable } from "@/components/error-dialog"
import { PageHeader } from "@/components/page"
import { Button } from "@/components/ui/button"
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
  deep: "tint-emerald",
  shallow: "tint-sky",
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
  const [icons, setIcons] = useState<Record<string, string>>({})  // the apps' own, from Proki; a website's is asked of the website
  const [broken, setBroken] = useState<Set<string>>(new Set())  // the websites with no favicon to show
  const asked = useRef(new Set<string>())  // the apps whose icon was asked for already

  const load = useCallback(async () => {
    const answer = await window.proki.apps({ op: "read" })
    if (answer.error) return setError(answer.error)
    setError((was) => (unresolvable(was) ? "" : was))  // Proki answers again
    setApps(answer.apps)
    setLabels(answer.labels)
    const keys = answer.apps.map((a) => a.key).filter((k) => !site(k) && !asked.current.has(k))
    keys.forEach((k) => asked.current.add(k))
    for (let i = 0; i < keys.length; i += 20) {  // a few at a time: all of them at once are too big for one answer
      const some  = keys.slice(i, i + 20)
      const found = (await window.proki.apps({ op: "icons", keys: some })) as unknown as Record<string, string> & { error?: string }
      if (found.error) some.forEach((k) => asked.current.delete(k))  // asked again on the next load
      else setIcons((had) => ({ ...had, ...found }))
    }
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
  const remove = async (app: App) => {
    setApps((all) => all.filter((a) => a.key !== app.key))
    const answer = await window.proki.apps({ op: "remove", key: app.key })
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
      .filter((app) => keeps(app) && (!words || `${app.key} ${labelOf(app)?.name ?? ""} ${labelOf(app)?.depth ?? ""} ${from(app) ?? ""}`.toLowerCase().includes(words)))
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
      <div className="px-8 pt-7 pb-8">
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

        {error && <ErrorDialog message={error} onClose={() => setError("")} />}
        {shown.length === 0 ? (
          <Empty className="mt-6">
            <EmptyHeader>
              <EmptyMedia variant="icon"><AppWindow /></EmptyMedia>
              <EmptyTitle>{apps.length ? "Nothing matches" : "No apps yet"}</EmptyTitle>
              <EmptyDescription>
                {apps.length ? "Try another filter or search." : "As you use apps and websites, Proki asks about them, and they show here."}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Table className="table-fixed">
            <colgroup>
              <col />{/* the app or website: the rest of the width, its name cut short */}
              <col className="w-52" /><col className="w-28" /><col className="w-24" /><col className="w-24" /><col className="w-20" /><col className="w-10" />
            </colgroup>
            <TableHeader>
              <TableRow>
                <TableHead>{head("key", "App or website")}</TableHead>
                <TableHead>{head("label", "Label")}</TableHead>
                <TableHead>Depth</TableHead>
                <TableHead>From</TableHead>
                <TableHead>{head("set_at", "Changed")}</TableHead>
                <TableHead className="text-right">Tracked</TableHead>
                <TableHead><span className="sr-only">Take out</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((app) => {
                const label = labelOf(app)
                const by   = from(app)
                return (
                  <TableRow key={app.key} className={cn("group/row", app.track === false && "text-muted-foreground")}>
                    <TableCell>
                      <span className="flex min-w-0 items-center gap-2 font-medium">
                        {site(app.key) ? (broken.has(app.key) ? <Globe className="size-4 shrink-0 text-muted-foreground" />
                                                              : <img src={`https://${app.key}/favicon.ico`} alt="" loading="lazy" className="size-4 shrink-0 rounded-sm"
                                                                     onError={() => setBroken((had) => new Set(had).add(app.key))} />)
                                       : icons[app.key] ? <img src={icons[app.key]} alt="" className="size-4 shrink-0 rounded-sm" />
                                       : <AppWindow className="size-4 shrink-0 text-muted-foreground" />}
                        <span title={app.key} className="min-w-0 truncate">{app.key}</span>
                        {app.track === false && <Badge variant="outline" className="font-normal">not tracked</Badge>}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <select value={app.label ?? ""} onChange={(e) => change(app, { label: Number(e.target.value) })}
                                  aria-label={`${app.key}'s label`}
                                  className={cn("-ml-1.5 h-7 max-w-full truncate rounded-md bg-transparent px-1 text-sm outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
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
                    <TableCell className="text-xs text-muted-foreground">{by === "jev" && app.conf !== null ? `jev, ${Math.round(app.conf * 100)}%` : by ?? "–"}</TableCell>
                    <TableCell className="text-xs whitespace-nowrap text-muted-foreground">{ago(app.set_at)}</TableCell>
                    <TableCell className="text-right">
                      <Switch checked={app.track !== false} onCheckedChange={(track) => change(app, { track })} aria-label={`track ${app.key}`} />
                    </TableCell>
                    <TableCell className="px-0 text-right">
                      <Confirm title={`Take out ${app.key}?`} action="Take out" onConfirm={() => remove(app)}
                               description="It's gone from this list, its label with it. If you use it again, it comes back as new, and Proki asks about it.">
                        <Button variant="ghost" size="icon-sm" aria-label={`Take out ${app.key}`}
                                className="text-muted-foreground opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100 hover:text-destructive"><Trash2 /></Button>
                      </Confirm>
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

/** Whether a key is a website's host, not an app's name. */
const site = (key: string) => key.includes(".") && !key.includes(" ")

/** Who gave its label: user, dev (Proki's list) or jev (null: no label yet). */
function from(app: App): "user" | "dev" | "jev" | null {
  if (app.label === null) return null
  return app.source === "usr" ? "user" : app.source === "dev" ? "dev" : "jev"
}
