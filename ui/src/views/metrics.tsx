// Metrics: Charts, each reported signal over a horizon, in buckets that fit it; Signals, every
// global signal, to report or not, and how its buckets are made.

import { useCallback, useEffect, useState } from "react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { ChartLine } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import type { Buckets, Horizon, Method, Metric } from "@/lib/proki"
import { cn } from "@/lib/utils"

// the series color, chosen for each mode's surface (validated: lightness, chroma, 3:1 contrast)
const SERIES   = { light: "var(--metric)", dark: "var(--metric)" }   // blue, the year's grid too
const HORIZONS = [["day", "Day", "5 min"], ["week", "Week", "30 min"], ["month", "Month", "2 h"], ["year", "Year", "1 day"]] as const
const METHODS: Method[] = ["mean", "sum", "min", "max", "last"]

const title = (name: string) => name.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase())

export function MetricsView() {
  const [metrics, setMetrics] = useState<Metric[]>([])
  const [page, setPage] = useState<"charts" | "signals">("charts")
  const [horizon, setHorizon] = useState<Horizon>("week")
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    const answer = await window.proki.metrics({ op: "list" })
    if (answer.error) return setError(answer.error)
    setError("")
    setMetrics(answer.metrics)
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const change = async (name: string, changed: Partial<Metric>) => {
    setMetrics((all) => all.map((m) => (m.name === name ? { ...m, ...changed } : m)))  // at once, then as the engine says
    const answer = await window.proki.metrics({ op: "change", name, ...changed })
    if (answer.error) setError(answer.error)
    load()
  }

  const reported = metrics.filter((m) => m.on)

  return (
    <div className="mx-auto max-w-5xl px-8 pt-7 pb-8">
      <PageHeader title="Time reports" className="mb-5" beside={
        <Tabs value={page} onValueChange={(v) => setPage(v as typeof page)}>
          <TabsList>
            <TabsTrigger value="charts">Charts</TabsTrigger>
            <TabsTrigger value="signals">Signals <span className="text-muted-foreground tabular-nums">{reported.length}</span></TabsTrigger>
          </TabsList>
        </Tabs>}>
        {page === "charts" && (
          <div role="group" aria-label="Over" className="flex gap-1 rounded-lg bg-muted p-1">
            {HORIZONS.map(([h, label, size]) => (
              <button key={h} onClick={() => setHorizon(h)} title={`a bar every ${size}`}
                      aria-pressed={horizon === h}
                      className={cn("rounded-md px-3 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                                    horizon === h && "bg-background font-medium text-foreground shadow-xs")}>
                {label}
              </button>
            ))}
          </div>
        )}
      </PageHeader>
      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}

      {page === "signals" ? <Signals metrics={metrics} onChange={change} /> : reported.length === 0 ? (
        <Empty className="mt-6">
          <EmptyHeader>
            <EmptyMedia variant="icon"><ChartLine /></EmptyMedia>
            <EmptyTitle>Nothing reported</EmptyTitle>
            <EmptyDescription>Turn signals on in Signals.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="grid gap-4">
          {reported.map((m) => <Chart key={m.name} metric={m} horizon={horizon} />)}
        </div>
      )}
    </div>
  )
}

const KEEPS = [[1440, "Day"], [10080, "Week"], [43200, "Month"], [525600, "Year"]] as const
const GRID  = "grid grid-cols-[3rem_13rem_minmax(0,1fr)_4rem_6rem_5.5rem] items-center gap-3"

/** Every global signal: the persisted ones first, to report or not, how far back, and how
 * their buckets are made; the others greyed out. */
function Signals({ metrics, onChange }: { metrics: Metric[]; onChange: (name: string, changed: Partial<Metric>) => void }) {
  const sorted = [...metrics.filter((m) => m.persist), ...metrics.filter((m) => !m.persist)]
  return (
    <div className="overflow-hidden rounded-lg border">
      <div className={cn(GRID, "border-b bg-muted/60 px-3 py-1.5 text-xs font-medium text-muted-foreground")}>
        <span>Report</span><span>Signal</span><span>Description</span><span>Pace</span><span>Keep</span><span>Bucket</span>
      </div>
      {sorted.map((m) => (
        <div key={m.name} className={cn(GRID, "border-b px-3 py-2", !m.persist && "opacity-45")}
             title={m.persist ? undefined : "No saved history"}>
          <Switch checked={m.on} disabled={!m.persist} onCheckedChange={(on) => onChange(m.name, { on })} aria-label={`report ${m.name}`} />
          <span className="truncate font-mono text-xs font-medium" title={m.expr}>{m.name}</span>
          <span className="truncate text-xs text-muted-foreground" title={m.expr}>{m.desc || m.expr}</span>
          <span className="text-xs text-muted-foreground tabular-nums">{pace(m.pace)}</span>
          {m.persist ? (
            <NativeSelect size="sm" value={m.keep ?? ""} onChange={(e) => onChange(m.name, { keep: Number(e.target.value) })} aria-label="keep">
              {m.keep !== null && !KEEPS.some(([k]) => k === m.keep) && <NativeSelectOption value={m.keep}>{pace(m.keep)}</NativeSelectOption>}
              {KEEPS.map(([k, label]) => <NativeSelectOption key={k} value={k}>{label}</NativeSelectOption>)}
            </NativeSelect>
          ) : <span className="text-xs text-muted-foreground">–</span>}
          {m.persist ? (
            <NativeSelect size="sm" value={m.method} onChange={(e) => onChange(m.name, { method: e.target.value as Method })} aria-label="bucket">
              {METHODS.map((method) => <NativeSelectOption key={method} value={method}>{method}</NativeSelectOption>)}
            </NativeSelect>
          ) : <span className="text-xs text-muted-foreground">–</span>}
        </div>
      ))}
      <p className="bg-muted/30 px-3 py-2.5 text-xs text-muted-foreground">
        Only signals with saved history can be metrics. To add one, open the signal in Programs, set its History (minutes) and
        turn on “Keep history across restarts”. Its past is filled in from its inputs, as far back as they reach.
      </p>
    </div>
  )
}

/** Minutes, as they read: "5 min", "1 h", "1 d" (none: "cycle", a value every cycle). */
function pace(minutes: number | null): string {
  if (minutes === null) return "cycle"
  if (minutes < 60) return `${minutes} min`
  if (minutes < 1440) return `${minutes / 60} h`
  return `${Math.round(minutes / 1440)} d`
}

/** One metric over the horizon, a bar a bucket. */
function Chart({ metric, horizon }: { metric: Metric; horizon: Horizon }) {
  const [read, setRead] = useState<Buckets | null>(null)  // null: still loading

  useEffect(() => {
    let live = true
    window.proki.metrics({ op: "read", name: metric.name, horizon }).then((answer) => live && !answer.error && setRead(answer))
    return () => {
      live = false
    }
  }, [metric.name, metric.method, horizon])

  const shown = (value: number | null) =>
    value == null ? "–" : Math.abs(value) < 10 ? value.toFixed(2).replace(/\.?0+$/, "") || "0" : `${Math.round(value)}`
  const label = (t: Date) => horizon === "day" ? t.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : horizon === "week" ? t.toLocaleDateString(undefined, { weekday: "short", hour: "numeric" })
    : horizon === "month" ? t.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "numeric" })
    : t.toLocaleDateString(undefined, { month: "short", day: "numeric" })
  const data = (read?.buckets ?? []).map(([t, value]) => ({ label: label(new Date(t)), value }))
  const latest = [...data].reverse().find((d) => d.value != null)
  const config = { value: { label: title(metric.name), theme: SERIES } } satisfies ChartConfig
  const axisText = { fill: "var(--muted-foreground)", fontSize: 11 }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title(metric.name)}</CardTitle>
        <CardDescription>
          {latest ? <>latest <span className="font-medium text-foreground tabular-nums">{shown(latest.value)}</span> · </> : null}
          {metric.method} per {HORIZONS.find(([h]) => h === horizon)![2]}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {read === null ? (
          <p className="py-16 text-center text-sm text-muted-foreground">Loading…</p>
        ) : !latest ? (
          <p className="py-16 text-center text-sm text-muted-foreground">No data in this range yet.</p>
        ) : horizon === "year" ? (
          <Days buckets={read!.buckets} shown={shown} />
        ) : (
          <ChartContainer config={config} className="aspect-auto h-48 w-full">
            <BarChart data={data} margin={{ left: 0, right: 12, top: 8 }} barCategoryGap="25%">
              <CartesianGrid vertical={false} stroke="var(--border)" strokeWidth={1} />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={axisText} minTickGap={32} />
              <YAxis width={40} tickLine={false} axisLine={false} tick={axisText} />
              <ChartTooltip cursor={{ fill: "var(--muted)" }} content={<ChartTooltipContent formatter={(v) => shown(Number(v))} />} />
              <Bar dataKey="value" fill="var(--color-value)" isAnimationActive={false} shape={Crisp} />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}

/** A bar on whole pixels: every bar as wide as the others (a bandwidth rounded the same way),
 * so they all read alike, however many there are. */
function Crisp({ x, y, width, height, fill }: { x?: number; y?: number; width?: number; height?: number; fill?: string }) {
  if (x == null || y == null || !width || !height) return null
  const w = Math.max(1, Math.round(width))
  const top = Math.round(height >= 0 ? y : y + height)
  return <rect x={Math.round(x + (width - w) / 2)} y={top} width={w} height={Math.max(1, Math.round(Math.abs(height)))} fill={fill} shapeRendering="crispEdges" />
}

const WEEKDAYS = ["", "Mon", "", "Wed", "", "Fri", ""]
const LEVELS = [0.25, 0.5, 0.75, 1]  // a day's share of the year's highest, in four steps

/** A year of days as weeks across and weekdays down, each day as blue as its value. */
function Days({ buckets, shown }: { buckets: [string, number | null][]; shown: (value: number | null) => string }) {
  const days = buckets.map(([t, value]) => ({ day: new Date(t), value }))
  const first = days[0]?.day.getDay() ?? 0  // the first week starts on a Sunday: the days before, left empty
  const top = Math.max(...days.map((d) => Math.abs(d.value ?? 0)), 0)
  const level = (value: number | null) => (value == null || top === 0 || value === 0 ? -1 : LEVELS.findIndex((l) => Math.abs(value) / top <= l))
  const weeks = Math.ceil((first + days.length) / 7)
  const months = days.flatMap((d, i) => (d.day.getDate() === 1 ? [{ week: Math.floor((first + i) / 7), label: d.day.toLocaleDateString(undefined, { month: "short" }) }] : []))

  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-[3px]" style={{ gridTemplateColumns: `2rem repeat(${weeks}, 11px)`, gridTemplateRows: "1rem repeat(7, 11px)" }}>
        {months.map((m) => (
          <span key={m.week} className="text-[10px] text-muted-foreground" style={{ gridColumn: m.week + 2, gridRow: 1 }}>{m.label}</span>
        ))}
        {WEEKDAYS.map((w, i) => <span key={i} className="text-[10px] leading-[11px] text-muted-foreground" style={{ gridColumn: 1, gridRow: i + 2 }}>{w}</span>)}
        {days.map((d, i) => {
          const l = level(d.value)
          return (
            <span key={i} title={`${d.day.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}: ${shown(d.value)}`}
                  className={cn("rounded-[2px]", l < 0 && "bg-muted")}
                  style={{ gridColumn: Math.floor((first + i) / 7) + 2, gridRow: ((first + i) % 7) + 2,
                           ...(l >= 0 ? { backgroundColor: "var(--metric)", opacity: 0.25 + l * 0.25 } : {}) }} />
          )
        })}
      </div>
      <div className="mt-2 flex items-center justify-end gap-1 text-[10px] text-muted-foreground">
        Less
        <span className="size-[11px] rounded-[2px] bg-muted" />
        {LEVELS.map((_, l) => <span key={l} className="size-[11px] rounded-[2px]" style={{ backgroundColor: "var(--metric)", opacity: 0.25 + l * 0.25 }} />)}
        More
      </div>
    </div>
  )
}
