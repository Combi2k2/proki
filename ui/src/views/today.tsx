// Today: where you are now, and what to do next. Your focus today as its spread, from scattered
// to focused, the lines between its bands (drag one to move it, double-click to add or remove
// one), the minutes of each, worked out here as the lines move, and your focus now, moving
// along it; how far you are into the focused time you aim for, as the day clock counts it; your
// tasks, the next one first; a box to note a thought in, kept as what it is or sorted later; and
// the automations helping you, each opened in the editor. The page is panels: drag between two to give one more room, kept as you left it.
// Focus now refreshes each cycle, as the engine works it out; the rest with it.

import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent, type ReactNode } from "react"
import { ArrowRight, Check, Clock, Flame, Lightbulb, ListTodo, MessageCircle, Play, Square } from "lucide-react"
import { useDefaultLayout } from "react-resizable-panels"
import { PageHeader } from "@/components/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { doing, friendly } from "@/lib/friendly"
import { dueText, type Bucket, type FocusDay, type Reference, type Today, type View } from "@/lib/proki"
import { cn } from "@/lib/utils"

const CYCLE = 10_000  // the engine's: focus now changes no faster

/** Minutes, said: "45m", "2h", "2h 10m". */
const hm = (m: number) => (m < 60 ? `${Math.round(m)}m` : `${Math.floor(m / 60)}h${Math.round(m % 60) ? ` ${Math.round(m % 60)}m` : ""}`)

type Go = (view: View, opened?: number | string) => void

export function TodayView({ onGo }: { onGo: Go }) {
  const [today, setToday]     = useState<Today | null>(null)
  const [helpers, setHelpers] = useState<Reference["programs"]>([])
  const [error, setError]     = useState("")

  const load = useCallback(async () => {
    const answer = await window.proki.today()
    if (answer.error) return setError(answer.error)
    setError("")
    setToday(answer)
  }, [])
  useEffect(() => {
    load()
    window.proki.tool("reference").then((known) => !known.error && setHelpers(known.programs))
    const every = setInterval(load, CYCLE)
    window.addEventListener("focus", load)
    return () => {
      clearInterval(every)
      window.removeEventListener("focus", load)
    }
  }, [load])

  const session = (op: "start" | "stop") => {
    window.proki.session(op)
    setToday((was) => was && { ...was, in_session: op === "start" })  // as it'll be, once the engine's cycle sees it
  }
  const work = async (id: number) => {
    await window.proki.tasks({ op: "work", id })
    setToday((was) => was && { ...was, in_session: true })
  }
  /** The lines moved, added or taken away: kept as their variable's value, the one the rules
   * read too. */
  const move = async (lines: number[]) => {
    if (!today || lines.join() === today.day.lines.join()) return
    setToday((was) => was && { ...was, day: { ...was.day, lines } })
    const answer = await window.proki.tool("apply_changes", { changes: [{ op: "update", kind: "variable", data: {
      name: "focus_lines", scope: "global", program: null, state: null, changes: { value: JSON.stringify(lines) } } }] })
    const now = answer.error ? answer : await window.proki.tool("set_value", { name: "focus_lines", value: lines })  // as they start, and now
    if (now.error) setError(now.error), load()
  }

  const narrow = useNarrow()
  const rows = useDefaultLayout({ id: "today.rows" }), top = useDefaultLayout({ id: "today.top" })
  const bottom = useDefaultLayout({ id: "today.bottom" }), side = useDefaultLayout({ id: "today.side" })

  const spread = (
    <Card size="sm" className="h-full">
      <CardHeader>
        <CardTitle>Your focus today</CardTitle>
        <CardDescription>How focused you were, each 5 minutes at the computer. Drag a line to move it; double-click to add or remove one.</CardDescription>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col">
        {today ? <Spread day={today.day} now={today.focus} onMove={move} /> : <Skeleton className="size-full" />}
      </CardContent>
    </Card>
  )
  const goal = (
    <Card size="sm" className="h-full">
      <CardHeader>
        <CardTitle>Daily goal</CardTitle>
        <CardDescription>Focused time</CardDescription>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col items-center gap-2">
        {today ? <Goal day={today.day} /> : <Skeleton className="aspect-square h-full rounded-full" />}
      </CardContent>
    </Card>
  )

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col gap-5 px-8 pt-7 pb-6">
      <PageHeader className="shrink-0" title={new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
                  sub={today?.in_session && <span className="font-medium text-focused">You're in a focus session</span>}>
        {today?.in_session
          ? <Button variant="outline" onClick={() => session("stop")}><Square data-icon="inline-start" /> End focus session</Button>
          : <Button onClick={() => session("start")} disabled={!today}><Play data-icon="inline-start" /> Start a focus session</Button>}
      </PageHeader>
      {error && <Alert variant="destructive" className="shrink-0"><AlertDescription>Proki isn't answering right now: {error}</AlertDescription></Alert>}

      {narrow ? (  // too narrow for the panels side by side: one under the other, scrolled
        <div className="-mx-8 grid min-h-0 flex-1 auto-rows-min grid-cols-[minmax(0,1fr)_minmax(0,11rem)] gap-3 overflow-y-auto px-8 pb-2 max-[560px]:grid-cols-1">
          <div className="h-64">{spread}</div>
          <div className="h-64 max-[560px]:h-auto">{goal}</div>
          <div className="col-span-full h-80"><Tasks today={today} onWork={work} onGo={onGo} /></div>
          <div className="col-span-full h-72"><Capture onGo={onGo} /></div>
          <div className="col-span-full h-72"><Helping programs={helpers} onGo={onGo} /></div>
        </div>
      ) : (
      <ResizablePanelGroup orientation="vertical" className="min-h-0 flex-1" {...rows}>
        <ResizablePanel id="focus" defaultSize="42" minSize="30">
          <ResizablePanelGroup orientation="horizontal" {...top}>
            <ResizablePanel id="spread" defaultSize="76" minSize="50">{spread}</ResizablePanel>
            <Between />
            <ResizablePanel id="goal" defaultSize="24" minSize="18">{goal}</ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>
        <Between across />
        <ResizablePanel id="next" defaultSize="58" minSize="30">
          <ResizablePanelGroup orientation="horizontal" {...bottom}>
            <ResizablePanel id="tasks" defaultSize="50" minSize="30">
              <Tasks today={today} onWork={work} onGo={onGo} />
            </ResizablePanel>
            <Between />
            <ResizablePanel id="side" defaultSize="50" minSize="30">
              <ResizablePanelGroup orientation="vertical" {...side}>
                <ResizablePanel id="note" defaultSize="50" minSize="30"><Capture onGo={onGo} /></ResizablePanel>
                <Between across />
                <ResizablePanel id="helping" defaultSize="50" minSize="30"><Helping programs={helpers} onGo={onGo} /></ResizablePanel>
              </ResizablePanelGroup>
            </ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>
      </ResizablePanelGroup>
      )}
    </div>
  )
}

/** Whether the window is too narrow for Today's panels side by side. */
function useNarrow() {
  const query = "(max-width: 1079px)"
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const watched = window.matchMedia(query)
    const change = () => setNarrow(watched.matches)
    watched.addEventListener("change", change)
    return () => watched.removeEventListener("change", change)
  }, [])
  return narrow
}

/** The gap between two panels, to drag: its grip shows as you near it. */
function Between({ across }: { across?: boolean }) {
  return (
    <ResizableHandle withHandle className={cn("bg-transparent [&>div]:opacity-0 [&>div]:transition-opacity hover:[&>div]:opacity-100 focus-visible:[&>div]:opacity-100",
                                              across ? "aria-[orientation=horizontal]:h-4" : "w-4")} />
  )
}

/** A panel's card: its title, what it holds, a way to all of it at its corner, and what it shows,
 * scrolling when it's more than the panel. */
function Panel({ title, about, go, children, className }: {
  title: string; about: ReactNode; go: { label: string; onClick: () => void }; children: ReactNode; className?: string
}) {
  return (
    <Card size="sm" className="h-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{about}</CardDescription>
        <CardAction>
          <Button variant="link" size="sm" className="h-auto px-0" onClick={go.onClick}>{go.label} <ArrowRight data-icon="inline-end" /></Button>
        </CardAction>
      </CardHeader>
      <CardContent className={cn("flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden", className)}>{children}</CardContent>
    </Card>
  )
}

// --- your focus today ---------------------------------------------------------------------

const WIDTH = 600, HEIGHT = 120, POINTS = 120, SPREAD = 0.05, GAP = 0.05

type Band = { key: string; label: string; from: number; to: number; minutes: number; color: string }

/** The bands between the lines, from distracted to focused: each its colour, from red to green
 * as it's higher, and its minutes, of the samples in it. */
function banded(lines: number[], samples: number[], every: number): Band[] {
  const edges = [0, ...lines, 1], last = edges.length - 2
  return edges.slice(0, -1).map((from, i) => {
    const to = edges[i + 1]
    return { key: String(i), from, to, minutes: every * samples.filter((f) => f >= from && (f < to || i === last)).length,
             label: i === 0 ? "Distracted" : i === last ? "Focused" : last === 2 ? "Shallow" : `Shallow ${i}`,
             color: `color-mix(in oklch, var(--focused) ${Math.round((i / Math.max(last, 1)) * 100)}%, var(--distracted))` }
  })
}

/** Today's focus as its spread along 0 to 1: the more of the day at a value, the higher it
 * goes. Coloured by the band it's in, the lines between them (each dragged, or moved by its
 * arrow keys once focused; double-clicked, or Delete, to take it away; a double-click between
 * them adds one), and focus now on it. Under each band, between its ticks, its name and
 * minutes. */
function Spread({ day, now, onMove }: { day: FocusDay; now: number | null; onMove: (lines: number[]) => void }) {
  const [grown, setGrown] = useState(false)
  const [lines, setLines] = useState(day.lines)
  const [held, setHeld]   = useState<number | null>(null)
  const plot = useRef<HTMLDivElement>(null)
  useEffect(() => { const t = requestAnimationFrame(() => setGrown(true)); return () => cancelAnimationFrame(t) }, [])
  useEffect(() => { if (held === null) setLines(day.lines) }, [day.lines.join(), held])  // eslint-disable-line react-hooks/exhaustive-deps

  const path = useMemo(() => {
    if (!day.samples.length) return ""
    const at = Array.from({ length: POINTS + 1 }, (_, i) => i / POINTS)
    const density = at.map((x) => day.samples.reduce((sum, f) => sum + Math.exp(-(((x - f) / SPREAD) ** 2) / 2), 0))
    const top = Math.max(...density)
    const y = (d: number) => HEIGHT - (d / top) * (HEIGHT - 6)
    return `M0,${HEIGHT} ` + at.map((x, i) => `L${(x * WIDTH).toFixed(1)},${y(density[i]).toFixed(1)}`).join(" ") + ` L${WIDTH},${HEIGHT} Z`
  }, [day.samples])
  const bands = banded(lines, day.samples, day.every)

  /** The line `i` at `to`, kept clear of its neighbours and of the ends. */
  const put = (i: number, to: number) => {
    const lo = (lines[i - 1] ?? 0) + GAP, hi = (lines[i + 1] ?? 1) - GAP
    return lines.map((v, j) => (j === i ? Math.min(Math.max(Math.round(to * 100) / 100, lo), hi) : v))
  }
  const where = (e: { clientX: number }) => {
    const box = plot.current?.getBoundingClientRect()
    return box ? (e.clientX - box.left) / box.width : null
  }
  const add = (e: MouseEvent) => {
    const at = where(e)
    if (at === null || lines.some((v) => Math.abs(v - at) < GAP) || at < GAP || at > 1 - GAP) return
    onMove([...lines, Math.round(at * 100) / 100].sort((a, b) => a - b))
  }
  const remove = (i: number) => lines.length > 1 && onMove(lines.filter((_, j) => j !== i))
  const drag = (i: number) => ({
    onPointerDown: (e: PointerEvent) => (e.currentTarget.setPointerCapture(e.pointerId), setHeld(i)),
    onPointerMove: (e: PointerEvent) => {
      const at = where(e)
      if (held === i && at !== null) setLines(put(i, at))
    },
    onPointerUp: () => (setHeld(null), onMove(lines)),
    onDoubleClick: (e: MouseEvent) => (e.stopPropagation(), remove(i)),
    onKeyDown: (e: KeyboardEvent) => {
      const by = { ArrowLeft: -0.01, ArrowRight: 0.01 }[e.key]
      if (by) (e.preventDefault(), setLines(put(i, lines[i] + by)))
      if (e.key === "Delete" || e.key === "Backspace") (e.preventDefault(), remove(i))
    },
    onKeyUp: (e: KeyboardEvent) => e.key.startsWith("Arrow") && onMove(lines),
  })

  return (
    <figure className="flex min-h-0 flex-1 flex-col" aria-label={`Today: ${bands.map((b) => `${hm(b.minutes)} ${b.label.toLowerCase()}`).join(", ")}`}>
      <div ref={plot} className="relative min-h-12 flex-1" onDoubleClick={add}>
        {path ? (
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none" aria-hidden
               className={cn("absolute inset-0 size-full origin-bottom transition-transform duration-700 ease-out motion-reduce:transition-none",
                             grown ? "scale-y-100" : "scale-y-0")}>
            <defs>
              {bands.map((b) => (
                <clipPath key={b.key} id={`band-${b.key}`}><rect x={b.from * WIDTH} y={0} width={(b.to - b.from) * WIDTH} height={HEIGHT} /></clipPath>
              ))}
            </defs>
            {bands.map((b) => (
              <g key={b.key} clipPath={`url(#band-${b.key})`} style={{ color: b.color }}>
                <path d={path} fill="currentColor" fillOpacity={0.28} />
                <path d={path} fill="none" stroke="currentColor" strokeWidth={2} vectorEffect="non-scaling-stroke" />
              </g>
            ))}
          </svg>
        ) : (
          <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">Nothing yet today: your focus shows here as you work.</p>
        )}
        {now !== null && (
          <div className="pointer-events-none absolute inset-y-0 flex flex-col items-center transition-[left] duration-1000 ease-out motion-reduce:transition-none"
               style={{ left: `${now * 100}%`, translate: "-50% 0" }}>
            <span className="rounded-md bg-foreground px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap text-background tabular-nums">
              Now {Math.round(now * 100)}
            </span>
            <span className="w-px flex-1 bg-foreground" />
            <span className="size-2 rounded-full bg-foreground ring-4 ring-foreground/15 motion-safe:animate-pulse" />
          </div>
        )}
        {lines.map((v, i) => (
          <div key={i} role="slider" tabIndex={0} aria-orientation="horizontal" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v * 100)}
               aria-label={`Where ${bands[i + 1].label.toLowerCase()} starts`} title="Drag to move; double-click to take it away"
               className="group/line absolute inset-y-0 -ml-2 flex w-4 cursor-ew-resize touch-none justify-center outline-none"
               style={{ left: `${v * 100}%` }} {...drag(i)}>
            <span className={cn("w-0 border-l border-dashed border-foreground/30 transition-colors group-hover/line:border-solid group-hover/line:border-foreground/70 group-focus-visible/line:border-solid group-focus-visible/line:border-ring",
                                held === i && "border-solid border-foreground")} />
            <span className={cn("absolute -top-1 rounded bg-popover px-1 text-[11px] font-medium text-popover-foreground tabular-nums opacity-0 shadow-sm ring-1 ring-foreground/10 transition-opacity group-hover/line:opacity-100 group-focus-visible/line:opacity-100",
                                held === i && "opacity-100")}>
              {Math.round(v * 100)}
            </span>
          </div>
        ))}
      </div>
      <Legend bands={bands} />
    </figure>
  )
}

/** Each band's name and minutes, under the middle of it, between the ticks at its ends; a
 * narrow one's nudged aside to stay readable. */
function Legend({ bands }: { bands: Band[] }) {
  const ROOM = Math.min(0.2, 1 / bands.length)  // the least between two labels' middles, of the whole width
  const centers = bands.map((b) => (b.from + b.to) / 2)
  for (let i = 1; i < centers.length; i++) centers[i] = Math.max(centers[i], centers[i - 1] + ROOM)
  for (let i = centers.length - 1; i >= 0; i--) centers[i] = Math.min(centers[i], 1 - ROOM / 2 - (centers.length - 1 - i) * ROOM)
  centers[0] = Math.max(centers[0], ROOM / 2)
  const ticks = [0, ...bands.map((b) => b.to)]
  return (
    <div className="relative h-12 shrink-0 border-t border-foreground/15">
      {ticks.map((t, i) => <span key={i} aria-hidden className="absolute top-0 h-1.5 border-l border-foreground/30" style={{ left: `${t * 100}%`, translate: i === ticks.length - 1 ? "-1px 0" : undefined }} />)}
      {bands.map((b, i) => (
        <div key={b.key} className="absolute top-2 flex flex-col items-center whitespace-nowrap transition-[left] duration-150"
             style={{ left: `${centers[i] * 100}%`, translate: "-50% 0" }}>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="size-2 shrink-0 rounded-full" style={{ background: b.color }} />{b.label}
          </span>
          <span className="text-sm font-medium tabular-nums">{hm(b.minutes)}</span>
        </div>
      ))}
    </div>
  )
}

/** The focused time today against the time you aim for, as a ring filling up; under it, what's left,
 * the days in a row you reached it and the week so far. */
function Goal({ day }: { day: FocusDay }) {
  const size = 128, stroke = 10, r = (size - stroke) / 2, around = 2 * Math.PI * r
  const share = day.goal > 0 ? Math.min(day.focused / day.goal, 1) : 0
  return (
    <>
      <figure className="relative aspect-square min-h-0 max-w-full flex-1" aria-label={`${hm(day.focused)} focused of your ${hm(day.goal)} goal`}>
        <svg viewBox={`0 0 ${size} ${size}`} className="size-full" aria-hidden>
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--muted)" strokeWidth={stroke} />
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--focused)" strokeWidth={stroke} strokeLinecap="round"
                    strokeDasharray={around} strokeDashoffset={around * (1 - share)}
                    className="transition-[stroke-dashoffset] duration-700 ease-out motion-reduce:transition-none" />
          </g>
          <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" className="fill-foreground font-heading text-[26px] tracking-[-0.04em] tabular-nums">
            {hm(day.focused)}
          </text>
        </svg>
      </figure>
      <p className="flex shrink-0 flex-wrap justify-center gap-x-3 text-xs text-muted-foreground tabular-nums">
        <span className="font-medium text-foreground">{share >= 1 ? "Goal reached" : `${hm(day.goal - day.focused)} to go`}</span>
        {!!day.streak && <span className="flex items-center gap-1"><Flame className="size-3 text-shallow" />{day.streak} {day.streak === 1 ? "day" : "days"} in a row</span>}
        {day.week != null && <span>{hm(day.week)} this week</span>}
      </p>
    </>
  )
}

// --- your tasks -----------------------------------------------------------------------------

function Tasks({ today, onWork, onGo }: { today: Today | null; onWork: (id: number) => void; onGo: Go }) {
  const next = today?.next
  return (
    <Panel title="Your tasks" about={today?.tasks_open == null ? " " : `${today.tasks_open} open you can start`}
           go={{ label: "All tasks", onClick: () => onGo("tasks") }} className="gap-3">
      {!today ? <Skeleton className="h-16 w-full" /> : next ? (
        <div className="flex flex-col gap-2 rounded-lg bg-muted/60 p-3">
          <span className="text-xs text-muted-foreground">Up next · {next.group.name}</span>
          <span className="text-base leading-snug font-medium text-balance">{next.task.name}</span>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline"><Clock data-icon="inline-start" />{hm(next.task.estimate)}</Badge>
            {next.deadline && <Badge variant={dueText(next.deadline) === "overdue" ? "destructive" : "secondary"}>{dueText(next.deadline)}</Badge>}
            <Button size="sm" className="ml-auto" onClick={() => onWork(next.task.id)}><Play data-icon="inline-start" /> Work on it</Button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Nothing to start yet. Write down what you need to do, and proki plans it into tasks.</p>
      )}
      {today && today.after.length > 0 && (
        <ul className="flex flex-col">
          {today.after.map(({ task, group }) => (
            <li key={task.id}>
              <button onClick={() => onGo("tasks", group.id)} className="flex w-full items-center gap-2 rounded-md px-1 py-1 text-left text-sm hover:bg-muted">
                <span className="min-w-0 flex-1 truncate">{task.name}</span>
                <span className="max-w-32 shrink-0 truncate text-xs text-muted-foreground">{group.name}</span>
                <span className="w-10 shrink-0 text-right text-xs text-muted-foreground tabular-nums">{hm(task.estimate)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

// --- a thought, and who's helping ---------------------------------------------------------

const KEEP_AS: { bucket: Bucket; label: string; icon: typeof Lightbulb }[] = [
  { bucket: "Idea", label: "Idea", icon: Lightbulb },
  { bucket: "Todo", label: "Todo", icon: ListTodo },
  { bucket: "Thought", label: "Thought", icon: MessageCircle },
]

/** A thought noted on the spot, kept as what you say it is, or for the note sorter to file
 * (⌘ Enter). The box takes the panel's room, and scrolls past it: all that's written stays in
 * reach. */
function Capture({ onGo }: { onGo: Go }) {
  const [text, setText] = useState("")
  const [kept, setKept] = useState<Bucket | null>(null)
  const keep = async (bucket: Bucket) => {
    if (!text.trim()) return
    const answer = await window.proki.notes({ op: "add", bucket, text: text.trim() })
    if (answer.error) return
    setText("")
    setKept(bucket)
    setTimeout(() => setKept(null), 2500)
  }
  return (
    <Panel title="Something on your mind?" about="Write it down and let it go."
           go={{ label: "All notes", onClick: () => onGo("notes") }} className="overflow-hidden">
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <Textarea value={text} onChange={(e) => setText(e.target.value)} aria-label="A note"
                  placeholder="Call the dentist, an idea for the talk… (⌘ Enter: proki sorts it for you)"
                  className="min-h-12 flex-1 resize-none overflow-y-auto field-sizing-fixed [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                  onKeyDown={(e) => e.key === "Enter" && (e.metaKey || e.ctrlKey) && keep("Unsorted")} />
        <div role="group" aria-label="Keep it as" className="flex shrink-0 flex-wrap items-center gap-1.5">
          <span className="mr-auto text-xs text-muted-foreground">Keep as</span>
          {KEEP_AS.map(({ bucket, label, icon: Icon }) => (
            <Button key={bucket} size="sm" variant="outline" disabled={!text.trim() && kept !== bucket} onClick={() => keep(bucket)}
                    className={cn(kept === bucket && "text-brand")}>
              {kept === bucket ? <Check data-icon="inline-start" /> : <Icon data-icon="inline-start" />}{kept === bucket ? "Kept" : label}
            </Button>
          ))}
        </div>
      </div>
    </Panel>
  )
}

function Helping({ programs, onGo }: { programs: Reference["programs"]; onGo: Go }) {
  const on   = programs.filter((p) => p.on)
  const busy = on.filter((p) => doing(p).busy).length
  return (
    <Panel title="Helping you" about={`${on.length} on${busy ? `, ${busy} working now` : ""}`}
           go={{ label: "All automations", onClick: () => onGo("programs") }} className="gap-1.5">
      {on.length === 0 && <p className="text-sm text-muted-foreground">No automations are on.</p>}
      {on.map((p) => {
        const { title, icon: Icon } = friendly(p)
        const now = doing(p)
        return (
          <button key={p.name} onClick={() => onGo("programs", p.name)} title={`See how ${title} works`}
                  className="-mx-1.5 flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-sm transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
            <Icon aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate">{title}</span>
            <span className={cn("ml-auto shrink-0 text-xs", now.busy ? "font-medium text-brand" : "text-muted-foreground")}>{now.busy ? now.text : "Ready"}</span>
          </button>
        )
      })}
    </Panel>
  )
}
