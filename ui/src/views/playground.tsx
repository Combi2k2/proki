// The playground: made-up signals and variables of proki's own (proki/playground.py), to try
// things on without touching yours. On top, its signals, a value a minute, which nothing sets.
// Then, on the left: an operator on one of them, worked out minute by minute, a cursor sweeping
// through time and showing what the operator reads there (a bin, a window, a minute back); an
// expression of your own; an action, taken on the variables. On the right, every variable: the
// place you're typing (the longest name at the end of what you typed) is outlined, and what an
// action changed flashes. Its variables are kept as actions leave them, until you reset them.

import { useEffect, useMemo, useRef, useState } from "react"
import { CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceDot, ReferenceLine, XAxis, YAxis } from "recharts"
import { ChevronRight, Pause, Play, RotateCcw, Zap } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { Input } from "@/components/ui/input"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { Played, Type } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { CodeInput, Expr } from "@/views/code"
import { said, TypeIcon } from "@/views/fields"
import { hover, Value } from "@/views/programs"

const OPS = {  // what each reads at minute t, in words
  every:    "the mean of each full bin of w minutes, held until the next one ends",
  ts_mean:  "the mean of the last w minutes",
  ts_sum:   "the total of the last w minutes",
  ts_min:   "the smallest of the last w minutes",
  ts_max:   "the largest of the last w minutes",
  delay:    "the value w minutes ago",
  ts_count: "how many times it changed in the last w minutes",
} as const
type Op = keyof typeof OPS
const KINDS = {  // each action, what it does here, and one to start from: what it changes, by what
  set:    ["a variable, or a place in one, to the value", "tasks[1].done", "a > 0.5"],
  add:    ["the value added to a number", "streak", "1"],
  sub:    ["the value taken from a number", "goal", "30"],
  append: ["an item added at the end of a list (of records: its fields)", "tasks", ""],
  remove: ["the record with that id taken out of a list of records", "tasks", "2"],
} as const
type Kind = keyof typeof KINDS
/** A mistake, and how to put it right where it's a common one. */
const fixed = (error: string) => /unknown name '(true|false|none|null)'/i.test(error) ? `${error}: write True, False or None, capitalised` : error
type Vars = Played["variables"]
const AXIS = { fill: "var(--muted-foreground)", fontSize: 11 }

/** Minute `i` on the playground's clock, from its `start` ("09:00"). */
const clock = (start: string, i: number) => {
  const [h, m] = start.split(":").map(Number), at = h * 60 + m + i
  return `${Math.floor(at / 60) % 24}:${String(at % 60).padStart(2, "0")}`
}
const num = (v: unknown) => (typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(2)) : v === null || v === undefined ? "None" : JSON.stringify(v))

/** The places in `before` and `after` that differ, as paths ("tasks[1].done"), the new ones too. */
function changed(before: unknown, after: unknown, at = ""): string[] {
  if (JSON.stringify(before) === JSON.stringify(after)) return []
  const nested = (v: unknown) => v !== null && typeof v === "object"
  if (!nested(before) || !nested(after) || Array.isArray(before) !== Array.isArray(after)) return [at]
  const b = before as Record<string, unknown>, a = after as Record<string, unknown>
  const keys = Array.isArray(a) ? [...Array(Math.max((after as unknown[]).length, (before as unknown[]).length)).keys()].map(String) : [...new Set([...Object.keys(b), ...Object.keys(a)])]
  const under = keys.flatMap((k) => changed(b[k], a[k], Array.isArray(a) ? `${at}[${k}]` : at ? `${at}.${k}` : k))
  return under.length ? under : [at]
}

/** The place the end of `text` names in the variables: its longest name there, as deep as it goes ("tasks[1]" of "tasks[1].nam"). */
function placed(text: string, vars: Vars): string | null {
  for (let i = 0; i < text.length; i++) {
    const m = /^([A-Za-z_]\w*)((?:\.\w*|\[-?\d*\]?)*)$/.exec(text.slice(i))
    if (!m || (i > 0 && /[\w.\]]/.test(text[i - 1])) || !(m[1] in vars)) continue
    let at = m[1], value: unknown = vars[m[1]].value
    for (const [, key, item] of m[2].matchAll(/\.(\w+)|\[(-?\d+)\]/g)) {
      if (key !== undefined && value && typeof value === "object" && !Array.isArray(value) && key in value) (at += `.${key}`), (value = (value as Record<string, unknown>)[key])
      else if (item !== undefined && Array.isArray(value) && value.at(Number(item)) !== undefined) {
        const n = Number(item) < 0 ? value.length + Number(item) : Number(item)
        at += `[${n}]`; value = value[n]
      } else break
    }
    return at
  }
  return null
}

export function Playground() {
  const [shipped, setShipped] = useState<Played | null>(null)
  const [expr, setExpr]       = useState("")
  const [vars, setVars]       = useState<Vars>({})
  const [typing, setTyping]   = useState("")  // what's being typed where a place can be named
  const [flash, setFlash]     = useState<{ paths: string[]; key: number }>({ paths: [], key: 0 })
  const [error, setError]     = useState("")
  useEffect(() => {
    window.proki.tool("playground").then((answer) => answer.error ? setError(answer.error) : (setShipped(answer), setVars(answer.variables)))
  }, [])
  const at = useMemo(() => placed(typing, vars), [typing, vars])
  if (!shipped) return <section id="playground" className="scroll-mt-6 text-sm text-muted-foreground">{error || "Loading the playground…"}</section>

  const acted = (after: Vars) => {
    const paths = Object.keys({ ...vars, ...after }).flatMap((k) => changed(vars[k]?.value, after[k]?.value, k))
    setVars(after)
    setFlash((f) => ({ paths, key: f.key + 1 }))
    return paths
  }
  return (
    <section id="playground" aria-labelledby="playground-title" className="scroll-mt-6">
      <div className="mb-3 flex items-end gap-3">
        <div className="min-w-0 flex-1">
          <h2 id="playground-title" className="text-base font-semibold">Playground</h2>
          <p className="text-xs text-muted-foreground">Made-up signals and variables of its own, to try anything on: nothing of yours is read or set.</p>
        </div>
        <Button size="sm" variant="ghost" onClick={() => (setVars(shipped.variables), setFlash((f) => ({ paths: [], key: f.key + 1 })))}>
          <RotateCcw data-icon="inline-start" /> Reset the variables
        </Button>
      </div>
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        {Object.entries(shipped.signals).map(([name, s]) => <Signal key={name} name={name} desc={s.desc} values={s.values} start={shipped.start} />)}
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <Operators shipped={shipped} />
          <Expression expr={expr} onExpr={(to) => (setExpr(to), setTyping(to))} vars={vars} start={shipped.start} onFocus={setTyping} />
          <Acting vars={vars} onActed={acted} onTyping={setTyping} />
        </div>
        <Variables vars={vars} at={at} flash={flash} />
      </div>
    </section>
  )
}

/** A signal, minute by minute: its name, what it is, its line (a gap where it's unknown). */
function Signal({ name, desc, values, start }: { name: string; desc: string; values: (number | null)[]; start: string }) {
  const data = values.map((v, minute) => ({ minute, v }))
  return (
    <div className="rounded-xl border bg-card px-3 pt-2.5 pb-1">
      <p className="px-1 text-xs"><code className="font-mono font-semibold">{name}</code> <span className="text-muted-foreground">· {desc}</span></p>
      <ChartContainer config={{ v: { label: name, color: "var(--metric)" } } satisfies ChartConfig} className="aspect-auto h-24 w-full">
        <ComposedChart data={data} margin={{ left: 0, right: 8, top: 6, bottom: 0 }}>
          <XAxis dataKey="minute" type="number" domain={[0, values.length - 1]} tickLine={false} axisLine={false} tick={AXIS} tickFormatter={(m) => clock(start, m)} ticks={[0, 30, 60, 90, values.length - 1]} />
          <YAxis width={32} tickLine={false} axisLine={false} tick={AXIS} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => clock(start, p[0]?.payload.minute)} formatter={(v) => num(v)} />} />
          <Line dataKey="v" stroke="var(--color-v)" strokeWidth={1.75} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ChartContainer>
    </div>
  )
}

/** An operator on a signal, worked out each minute; a cursor goes through time, showing what it reads there. */
function Operators({ shipped }: { shipped: Played }) {
  const names = Object.keys(shipped.signals)
  const [op, setOp]       = useState<Op>("ts_mean")
  const [of, setOf]       = useState(names[0])
  const [w, setW]         = useState(5)
  const [values, setValues] = useState<unknown[]>([])
  const still = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches
  const [playing, setPlaying] = useState(!still)
  const xs = shipped.signals[of].values, n = xs.length
  const [t, setT] = useState(20)
  const expr = `${op}(${of}, ${w})`
  useEffect(() => void window.proki.tool("playground", { expr }).then((a) => !a.error && setValues(a.values ?? [])), [expr])
  useEffect(() => {
    if (!playing) return
    const every = setInterval(() => setT((t) => (t + 1 >= n ? w : t + 1)), 160)
    return () => clearInterval(every)
  }, [playing, n, w])

  const got = values[t] as number | null | undefined
  const from = op === "every" ? Math.floor(t / w) * w - w : op === "delay" ? t - w : t - w + 1  // the minutes it reads
  const to   = op === "every" ? Math.floor(t / w) * w - 1 : op === "delay" ? t - w : t
  const seen = xs.map((v, i) => [i, v] as const).filter(([i, v]) => i >= from && i <= to && v !== null) as [number, number][]
  const pick = op === "ts_min" || op === "ts_max" ? seen.reduce<[number, number] | null>((b, r) => (!b || (op === "ts_min" ? r[1] < b[1] : r[1] > b[1]) ? r : b), null) : null
  const apart = op === "ts_sum" || op === "ts_count"  // a scale of its own
  const data  = xs.map((v, minute) => ({ minute, x: v, y: values[minute] as number | null }))
  const config = { x: { label: of, color: "var(--muted-foreground)" }, y: { label: expr, color: "var(--metric)" } } satisfies ChartConfig
  const told = got === null || got === undefined ? "unknown: nothing to read yet"
    : op === "every" ? `${num(got)}, the mean of ${of} from ${clock(shipped.start, from)} to ${clock(shipped.start, to)}, held since ${clock(shipped.start, to + 1)}`
    : op === "delay" ? `${num(got)}, ${of} at ${clock(shipped.start, from)}`
    : `${num(got)}, read from ${of} between ${clock(shipped.start, from)} and ${clock(shipped.start, to)}`

  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-sm font-semibold">An operator, over time</h3>
        <ToggleGroup type="single" size="sm" spacing={1} value={of} onValueChange={(v) => v && setOf(v)} aria-label="The signal">
          {names.map((s) => <ToggleGroupItem key={s} value={s} className="h-7 px-2.5 font-mono text-xs">{s}</ToggleGroupItem>)}
        </ToggleGroup>
        <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
          w <Input type="number" min={1} max={30} value={w} onChange={(e) => setW(Math.min(30, Math.max(1, Number(e.target.value) || 1)))} aria-label="Its window, in minutes" className="h-7 w-14 text-xs tabular-nums" /> min
        </label>
      </div>
      <ToggleGroup type="single" size="sm" spacing={1} value={op} onValueChange={(v) => v && setOp(v as Op)} aria-label="The operator" className="mb-2 flex-wrap justify-start">
        {(Object.keys(OPS) as Op[]).map((o) => <ToggleGroupItem key={o} value={o} className="h-7 px-2 font-mono text-xs">{o}</ToggleGroupItem>)}
      </ToggleGroup>
      <p className="mb-1 text-xs"><Expr className="font-semibold">{expr}</Expr> <span className="text-muted-foreground">· {OPS[op].replace("w minutes", `${w} minute${w === 1 ? "" : "s"}`)}</span></p>
      <ChartContainer config={config} className="aspect-auto h-52 w-full">
        <ComposedChart data={data} margin={{ left: 0, right: apart ? 0 : 8, top: 8, bottom: 0 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="minute" type="number" domain={[0, n - 1]} tickLine={false} axisLine={false} tick={AXIS} tickFormatter={(m) => clock(shipped.start, m)} ticks={[0, 30, 60, 90, n - 1]} />
          <YAxis yAxisId="x" width={32} tickLine={false} axisLine={false} tick={AXIS} />
          <YAxis yAxisId="y" orientation="right" hide={!apart} width={apart ? 36 : 0} tickLine={false} axisLine={false} tick={AXIS} />
          {op === "every" && [...Array(Math.ceil(n / w)).keys()].map((k) => <ReferenceLine key={k} yAxisId="x" x={k * w} stroke="var(--border)" />)}
          {from >= 0 && <ReferenceArea yAxisId="x" x1={from - 0.5} x2={to + 0.5} fill="var(--metric)" fillOpacity={0.12} stroke="var(--metric)" strokeOpacity={0.4} />}
          <Line yAxisId="x" dataKey="x" stroke="var(--color-x)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line yAxisId={apart ? "y" : "x"} dataKey="y" type={op === "every" || op === "ts_count" ? "stepAfter" : "linear"} stroke="var(--color-y)" strokeWidth={2} dot={false} isAnimationActive={false} />
          {(op === "every" || op === "ts_mean") && typeof got === "number" && from >= 0 && <ReferenceLine yAxisId="x" segment={[{ x: from, y: got }, { x: to, y: got }]} stroke="var(--metric)" strokeWidth={2} strokeDasharray="4 3" />}
          {pick && <ReferenceDot yAxisId="x" x={pick[0]} y={pick[1]} r={4} fill="var(--background)" stroke="var(--metric)" strokeWidth={2} />}
          {pick && <ReferenceLine yAxisId="x" segment={[{ x: pick[0], y: pick[1] }, { x: t, y: pick[1] }]} stroke="var(--metric)" strokeDasharray="4 3" />}
          {op === "delay" && from >= 0 && xs[from] !== null && <ReferenceDot yAxisId="x" x={from} y={xs[from]!} r={4} fill="var(--background)" stroke="var(--metric)" strokeWidth={2} />}
          {op === "delay" && from >= 0 && xs[from] !== null && <ReferenceLine yAxisId="x" segment={[{ x: from, y: xs[from]! }, { x: t, y: xs[from]! }]} stroke="var(--metric)" strokeDasharray="4 3" />}
          <ReferenceLine yAxisId="x" x={t} stroke="var(--foreground)" strokeOpacity={0.5} />
          {typeof got === "number" && <ReferenceDot yAxisId={apart ? "y" : "x"} x={t} y={got} r={4.5} fill="var(--metric)" stroke="var(--background)" strokeWidth={2} />}
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => clock(shipped.start, p[0]?.payload.minute)} formatter={(v, k) => `${k === "x" ? of : expr}  ${num(v)}`} />} />
        </ComposedChart>
      </ChartContainer>
      <div className="mt-2 flex items-center gap-2">
        <Button size="icon-sm" variant="outline" aria-label={playing ? "Pause" : "Play"} onClick={() => setPlaying((p) => !p)}>{playing ? <Pause /> : <Play />}</Button>
        <input type="range" min={0} max={n - 1} value={t} onChange={(e) => (setPlaying(false), setT(Number(e.target.value)))} aria-label="The minute"
               className="h-1.5 flex-1 cursor-pointer accent-[var(--metric)]" />
        <span className="w-10 text-right font-mono text-xs tabular-nums">{clock(shipped.start, t)}</span>
      </div>
      <p role="status" className="mt-2 text-xs text-muted-foreground">At <span className="font-mono text-foreground tabular-nums">{clock(shipped.start, t)}</span>, it gives <span className="text-foreground">{told}</span>.</p>
    </div>
  )
}

/** An expression of yours on the playground: drawn if it moves with the signals, else its value; on your values if it names yours. */
function Expression({ expr, onExpr, vars, start, onFocus }: { expr: string; onExpr: (expr: string) => void; vars: Vars; start: string; onFocus: (text: string) => void }) {
  const [answer, setAnswer] = useState<{ values?: unknown[]; value?: unknown; type?: Type; error?: string; yours?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)
  const run = async (text = expr) => {
    if (!text.trim()) return setAnswer(null)
    setBusy(true)
    const here = await window.proki.tool("playground", { expr: text, variables: Object.fromEntries(Object.entries(vars).map(([k, v]) => [k, v.value])) })
    const yours = here.error?.includes("unknown name") ? await window.proki.tool("evaluate", { expr: text }) : null  // one of your names: on yours, now
    setAnswer(yours && !yours.error ? { ...yours, yours: true } : here.error ? { error: fixed(here.error) } : { values: here.values, type: here.type, value: here.values?.at(-1) })
    setBusy(false)
  }
  useEffect(() => { if (expr) run(expr) }, [expr])  // eslint-disable-line react-hooks/exhaustive-deps
  const moves = !!answer?.values && answer.values.every((v) => v === null || typeof v === "number" || typeof v === "boolean") && new Set(answer.values.map(String)).size > 1
  return (
    <div className="rounded-xl border bg-card p-4">
      <h3 className="mb-0.5 text-sm font-semibold">An expression</h3>
      <p className="mb-3 text-xs text-muted-foreground">On the playground's names, a minute at a time; one of yours is read as it is now.</p>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); run() }}>
        <CodeInput value={expr} onChange={(e) => onExpr(e.target.value)} onFocus={(e) => onFocus(e.target.value)} placeholder="ts_mean(a, 10) > 0.6 and len(tasks) > 2"
                   aria-label="Expression" layout="flex-1" className="h-9 text-sm" />
        <Button type="submit" disabled={busy || !expr.trim()}><Play data-icon="inline-start" /> Run</Button>
      </form>
      {answer && (answer.error ? <p role="status" className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 font-mono text-xs text-destructive">{answer.error}</p> : (
        <div role="status" className="mt-3 rounded-lg bg-muted px-3 py-2">
          <div className="flex items-start gap-2 font-mono text-xs">
            <pre className="min-w-0 flex-1 whitespace-pre-wrap break-words">{moves ? `at ${clock(start, answer.values!.length - 1)}: ${num(answer.value)}` : JSON.stringify(answer.value ?? null, null, 2)}</pre>
            {answer.yours && <Badge variant="secondary" className="shrink-0 text-[11px]">on your values</Badge>}
            <Badge variant="outline" className="shrink-0 text-[11px]">{said(answer.type)}</Badge>
          </div>
          {moves && (
            <ChartContainer config={{ y: { label: expr, color: "var(--metric)" } } satisfies ChartConfig} className="mt-1 aspect-auto h-28 w-full">
              <ComposedChart data={answer.values!.map((v, minute) => ({ minute, y: typeof v === "boolean" ? Number(v) : v }))} margin={{ left: 0, right: 8, top: 6, bottom: 0 }}>
                <XAxis dataKey="minute" type="number" domain={[0, answer.values!.length - 1]} tickLine={false} axisLine={false} tick={AXIS} tickFormatter={(m) => clock(start, m)} ticks={[0, 30, 60, 90, answer.values!.length - 1]} />
                <YAxis width={32} tickLine={false} axisLine={false} tick={AXIS} {...(answer.type === "boolean" ? { domain: [0, 1], ticks: [0, 1], tickFormatter: (v: number) => (v ? "yes" : "no") } : {})} />
                <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => clock(start, p[0]?.payload.minute)} formatter={(v) => (answer.type === "boolean" ? (v ? "yes" : "no") : num(v))} />} />
                <Line dataKey="y" type={answer.type === "boolean" ? "stepAfter" : "linear"} stroke="var(--color-y)" strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ChartContainer>
          )}
        </div>
      ))}
    </div>
  )
}

/** An action, taken on the playground's variables at its last minute: what it changed flashes on the right. */
function Acting({ vars, onActed, onTyping }: { vars: Vars; onActed: (after: Vars) => string[]; onTyping: (text: string) => void }) {
  const [kind, setKind] = useState<Kind>("set")
  const [name, setName] = useState<string>(KINDS.set[1])
  const [expr, setExpr] = useState<string>(KINDS.set[2])
  const [fields, setFields] = useState<Record<string, string>>({})
  const [told, setTold] = useState<{ text: string; bad?: boolean } | null>(null)
  const items = vars[name]?.value
  const record = kind === "append" && Array.isArray(items) && items[0] && typeof items[0] === "object" ? Object.keys(items[0] as object) : null
  useEffect(() => {
    if (record) setFields((f) => Object.fromEntries(record.map((k) => [k, f[k] ?? (k === "id" ? String((items as { id?: number }[]).reduce((m, i) => Math.max(m, Number(i.id) || 0), 0) + 1) : "")])))
  }, [name, kind])  // eslint-disable-line react-hooks/exhaustive-deps
  const take = async () => {
    const params = kind === "remove" ? { name, id: expr } : kind === "append" && record ? { name, expr: Object.fromEntries(Object.entries(fields).filter(([, v]) => v.trim())) } : { name, expr }
    const answer = await window.proki.tool("playground", { action: { [kind]: params }, variables: Object.fromEntries(Object.entries(vars).map(([k, v]) => [k, v.value])) })
    if (answer.error) return setTold({ text: fixed(answer.error), bad: true })
    const paths = onActed(answer.variables)
    setTold({ text: paths.length ? `Changed ${paths.join(", ")}.` : "Nothing changed: an unknown value, a place that isn't there, or the value it had." })
  }
  return (
    <div className="rounded-xl border bg-card p-4">
      <h3 className="mb-0.5 text-sm font-semibold">An action</h3>
      <p className="mb-3 text-xs text-muted-foreground">Taken on the variables at the playground's last minute, as a state would.</p>
      <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); take() }}>
        <ToggleGroup type="single" size="sm" spacing={1} value={kind} onValueChange={(v) => v && (setKind(v as Kind), setName(KINDS[v as Kind][1]), setExpr(KINDS[v as Kind][2]), setTold(null))} aria-label="The action" className="justify-start">
          {(Object.keys(KINDS) as Kind[]).map((k) => <ToggleGroupItem key={k} value={k} className="h-7 px-2.5 font-mono text-xs">{k}</ToggleGroupItem>)}
        </ToggleGroup>
        <p className="text-xs text-muted-foreground"><code className="font-mono text-foreground">{kind}</code>: {KINDS[kind][0]}.</p>
        <div className="flex flex-wrap items-center gap-2">
          <CodeInput value={name} onChange={(e) => (setName(e.target.value), onTyping(e.target.value))} onFocus={(e) => onTyping(e.target.value)}
                     aria-label="What it changes" placeholder="tasks[0].done" layout="w-48" className="h-8 text-xs" />
          <span className="text-xs text-muted-foreground">{kind === "remove" ? "the item with id" : kind === "append" ? "gets" : kind === "set" ? "to" : "by"}</span>
          {record ? (
            <div className="flex flex-1 flex-wrap gap-1.5">
              {record.map((k) => (
                <label key={k} className="flex items-center gap-1 text-xs">
                  <span className="font-mono text-muted-foreground">{k}</span>
                  <CodeInput value={fields[k] ?? ""} onChange={(e) => setFields((f) => ({ ...f, [k]: e.target.value }))} aria-label={`Its ${k}`}
                             placeholder={k === "name" ? "'Rest'" : k === "done" ? "False" : "5"} layout="w-24" className="h-8 text-xs" />
                </label>
              ))}
            </div>
          ) : (
            <CodeInput value={expr} onChange={(e) => setExpr(e.target.value)} onFocus={(e) => onTyping(e.target.value)} aria-label="Its expression"
                       placeholder={kind === "remove" ? "2" : "streak + 1"} layout="min-w-32 flex-1" className="h-8 text-xs" />
          )}
          <Button type="submit" size="sm" disabled={!name.trim()}><Zap data-icon="inline-start" /> Take it</Button>
        </div>
      </form>
      {told && <p role="status" className={cn("mt-2 text-xs", told.bad ? "font-mono text-destructive" : "text-muted-foreground")}>{told.text}</p>}
    </div>
  )
}

/** Every variable of the playground, a line each as the drawer has them: open a list or a record
 * for its places, a line each too. `at` is outlined, `flash`'s flash; what holds either opens. */
function Variables({ vars, at, flash }: { vars: Vars; at: string | null; flash: { paths: string[]; key: number } }) {
  const box = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState<string[]>([])
  const toggle = (path: string) => setOpen((o) => (o.includes(path) ? o.filter((p) => p !== path) : [...o, path]))
  useEffect(() => {  // what changed, or the place named, brought into view
    const path = flash.paths[0] ?? at
    if (path) box.current?.querySelector(`[data-path="${CSS.escape(path)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" })
  }, [flash, at])
  return (
    <aside aria-label="The playground's variables" className="flex flex-col rounded-[14px] border bg-background lg:sticky lg:top-4">
      <header className="border-b px-3 py-2.5">
        <h3 className="text-sm font-medium">Variables</h3>
        <p className="text-xs text-muted-foreground">The playground's, as its actions leave them</p>
      </header>
      <div ref={box} className="flex max-h-[36rem] flex-col gap-0.5 overflow-y-auto overscroll-contain p-3 [scrollbar-color:var(--border)_transparent] [scrollbar-width:thin]">
        {Object.entries(vars).map(([name, v]) => (
          <Place key={name} path={name} label={name} value={v.value} type={v.type} desc={v.desc} at={at} flash={flash} open={open} onToggle={toggle} depth={0} />
        ))}
      </div>
    </aside>
  )
}

const kindOf = (v: unknown): Type => (Array.isArray(v) ? "array" : v === null ? "any" : typeof v === "object" ? "object" : typeof v === "string" ? "string" : typeof v === "boolean" ? "boolean" : "number")

function Place({ path, label, value, type, desc, at, flash, open, onToggle, depth }: {
  path: string; label: string; value: unknown; type?: Type; desc?: string; at: string | null; flash: { paths: string[]; key: number }
  open: string[]; onToggle: (path: string) => void; depth: number
}) {
  const nested = value !== null && typeof value === "object" && Object.keys(value as object).length > 0
  const inside = (p: string | null) => !!p && p !== path && (p.startsWith(`${path}.`) || p.startsWith(`${path}[`))
  const shown  = nested && (open.includes(path) || inside(at) || flash.paths.some(inside))
  const lit    = flash.paths.includes(path)
  const line = (
    <div key={lit ? flash.key : undefined} data-path={path} style={{ paddingLeft: depth * 12 + 4 }}
         className={cn("flex items-center gap-2 rounded-md py-1 pr-1 text-xs", at === path && "ring-2 ring-[var(--metric)]", lit && "bg-[color-mix(in_oklch,var(--metric)_12%,transparent)] motion-safe:animate-[flash_1.6s_ease-out]")}>
      {nested ? (
        <button onClick={() => onToggle(path)} aria-expanded={shown} aria-label={`${shown ? "Close" : "Open"} ${path}`} className="-ml-0.5 rounded-sm text-muted-foreground hover:text-foreground">
          <ChevronRight strokeWidth={3} className={cn("size-3.5 transition-transform", shown && "rotate-90")} />
        </button>
      ) : <span aria-hidden className="w-3 shrink-0" />}
      <TypeIcon type={type ?? kindOf(value)} />
      <span title={[path, hover({ desc, type: type ?? kindOf(value) })].filter(Boolean).join(" · ")} className="min-w-0 flex-1 truncate font-mono text-muted-foreground">{label}</span>
      <Value value={value} name={path} />
    </div>
  )
  if (!shown) return line
  const entries = Array.isArray(value) ? value.map((v, i) => [`[${i}]`, `${path}[${i}]`, v] as const) : Object.entries(value as object).map(([k, v]) => [k, `${path}.${k}`, v] as const)
  return <>{line}{entries.map(([l, p, v]) => <Place key={p} path={p} label={l} value={v} at={at} flash={flash} open={open} onToggle={onToggle} depth={depth + 1} />)}</>
}
