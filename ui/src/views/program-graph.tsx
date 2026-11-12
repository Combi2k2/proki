// A program as a graph: each state a box, each way out an arrow to the state it goes to, with
// its capsule. The boxes are laid out once as springs would pull them, and stay where they are:
// a box you drag stays where you put it, kept for the program, and so is the view. Arrows are
// bound to the boxes' edges, the side nearest the other box, as a drawing app binds them:
// curved, elbow (right angles, rounded) or straight. Or springs: the boxes laid out live, each
// way a spring and each box pushing the others off, the arrows arcs; a box you drag pulls the
// others, a double-click fixes it where it is (its border bolder), or frees it. Until you move the
// view, it fits the boxes as they settle and as the window's room changes. Each capsule is
// one size, its way's number, lying along its arrow. While the program checks the ways out of
// the state it's in, and a moment after, each one tried is tinted by whether it holds (green,
// red), the ones after the first that does aren't tried, and the one it takes flows. The state
// the program is in is lit: a ring running round it while it does its actions, the time left
// when it waits. The start is marked, the one open (`picked`) ringed. A box opens the state (a
// click, or Enter or Space on it), a capsule the way out (`onInspect`); a click on nothing, `onPane`.

import { useEffect, useMemo, useRef, useState } from "react"
import {
  Background, BackgroundVariant, BaseEdge, EdgeLabelRenderer, Handle, MarkerType, Panel, Position, ReactFlow, ReactFlowProvider,
  getBezierPath, getSmoothStepPath, getStraightPath, useInternalNode, useNodesInitialized, useNodesState, useReactFlow,
  type Edge, type EdgeProps, type InternalNode, type Node, type NodeProps, type Viewport,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import dagre from "@dagrejs/dagre"
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type Simulation, type SimulationNodeDatum } from "d3-force"
import { Broom, Check, CornerDownRight, Hourglass, Plus, Loader2, Maximize, Minus, Orbit, Spline, X, ZoomIn, ZoomOut } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { ProgramDetail } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { recall, remember } from "@/lib/remember"
import { humane } from "@/lib/friendly"
import { isElse, minutes, summary, type Inspected } from "@/views/program-inspect"

const H = 64  // a box's height
const GAP = 6  // between a box's edge and the arrow bound to it
const FIT = { padding: { top: "112px", right: "48px", bottom: "64px", left: "48px" } as const, maxZoom: 1.1 }  // room for the card over its top
const STYLES = ["curved", "elbow", "straight", "springs"] as const  // springs: laid out live, its arrows arcs
type Style = (typeof STYLES)[number]
type XY = { x: number; y: number }
type State = ProgramDetail["states"][number]
type StateData = { state: State; start: boolean; lit: boolean; picked: boolean; fixed: boolean; waking: string | null; onOpen: () => void }
type Box = SimulationNodeDatum & { id: string; w: number }
type WayData = { label: string; hint: string; number: number; tried: boolean | null; flowing: boolean; dashed: boolean; lane: number; lanes: number; style: Style; onOpen: () => void }
type StateNode = Node<StateData, "state">
type WayEdge = Edge<WayData, "way">

const width = (name: string) => Math.max(140, name.length * 8.6 + 44)

/** Where each state goes, laid out in columns, left to right, from the start. */
function layout(detail: ProgramDetail): Record<string, XY> {
  const g = new dagre.graphlib.Graph({ multigraph: true })
  g.setGraph({ rankdir: "LR", nodesep: 70, ranksep: 140, marginx: 20, marginy: 20 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const s of detail.states) g.setNode(s.name, { width: width(s.name), height: H })
  for (const s of detail.states) s.next.forEach((b, i) => b.goto !== s.name && g.setEdge(s.name, b.goto, { width: 90, height: 20 }, `${i}`))
  dagre.layout(g)
  return Object.fromEntries(detail.states.map((s) => {
    const n = g.node(s.name)
    return [s.name, { x: n.x - n.width / 2, y: n.y - n.height / 2 }]
  }))
}

/** The springs between the boxes, from where they are: each way a spring, each box pushing the
 *  others off. Stopped: tick it, or restart it to watch them move. */
function springs(detail: ProgramDetail, from: Record<string, XY>): Simulation<Box, undefined> {
  const boxes = detail.states.map((s) => ({ id: s.name, w: width(s.name), x: (from[s.name]?.x ?? 0) + width(s.name) / 2, y: (from[s.name]?.y ?? 0) + H / 2 }) as Box)
  const ways  = detail.states.flatMap((s) => s.next.filter((b) => b.goto !== s.name).map((b) => ({ source: s.name, target: b.goto, len: (width(s.name) + width(b.goto)) / 2 + 200 })))
  return forceSimulation(boxes)
    .force("ways", forceLink<Box, (typeof ways)[number]>(ways).id((b) => b.id).distance((w) => w.len).strength(0.6))
    .force("apart", forceManyBody().strength(-1400))
    .force("room", forceCollide<Box>((b) => b.w / 2 + 60))
    .force("x", forceX(0).strength(0.04)).force("y", forceY(0).strength(0.04))
    .stop()
}

const corner = (b: Box): XY => ({ x: Math.round(b.x! - b.w / 2), y: Math.round(b.y! - H / 2) })  // a box's top left, from its centre

/** Whether a way holds now: each condition true, each rule more likely than not (null: one
 *  can't tell yet). */
function holds(b: ProgramDetail["states"][number]["next"][number]): boolean | null {
  const said = [...b.conds.map((c) => c.value), ...b.rules.map((r) => (r.chance == null ? null : r.chance >= 0.5))]
  if (said.some((v) => v === false)) return false
  return said.every((v) => v === true) ? true : null
}

/** Kept for a program, in this window: where its boxes were put, and the view. */
function kept<T>(key: string): T | null {
  try { return JSON.parse(localStorage.getItem(key) ?? "null") as T | null } catch { return null }
}
function keep(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* no storage here */ }
}

/** A program's boxes and view, forgotten: one made new under a name used before starts fitted, not where an old one was left. */
export function forgetGraph(name: string) {
  for (const part of ["places", "view", "fixed"]) try { localStorage.removeItem(`graph.${name}.${part}`) } catch { /* no storage here */ }
}

/** A button down the graph's left side: its own box, its icon big. */
const SIDE = "rounded-xl bg-background/90 shadow-sm backdrop-blur [&_svg]:size-6!"

type GraphProps = {
  detail: ProgramDetail
  picked?: string | null
  onInspect: (next: Inspected) => void
  onPane?: () => void
  onAdd?: () => void                                    // a "+" to make a new state
  sweep?: { names: string[]; onSweep: () => void }      // a broom to delete the states nothing leads to (`names`)
}

export function GraphView(props: GraphProps) {
  return <ReactFlowProvider><Graph {...props} /></ReactFlowProvider>
}

function Graph({ detail, picked, onInspect, onPane, onAdd, sweep }: GraphProps) {
  const placesKey = `graph.${detail.name}.places`, viewKey = `graph.${detail.name}.view`, fixedKey = `graph.${detail.name}.fixed`
  const shape = JSON.stringify(detail.states.map((s) => [s.name, s.next.map((b) => b.goto)]))  // what the layout depends on
  const auto = useMemo(() => Object.fromEntries(springs(detail, layout(detail)).tick(400).nodes().map((b) => [b.id, corner(b)])), [shape])  // eslint-disable-line react-hooks/exhaustive-deps
  const [places, setPlaces] = useState<Record<string, XY>>(() => kept(placesKey) ?? {})  // the boxes you moved
  const [style, setStyle] = useState<Style>(() => recall("graph.style", STYLES, "springs"))
  const [view] = useState(() => kept<Viewport>(viewKey))
  const flow  = useReactFlow()
  const moved = useRef(!!view)  // you moved the view: it's left where you put it
  const hand  = useRef(false)   // the zoom buttons moving it: yours too
  const click = useRef(0)       // in springs, a click waits 150ms for a second one: a double-click fixes the box
  const box   = useRef<HTMLDivElement>(null)
  const refit = () => !moved.current && flow.fitView({ ...FIT, duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 300 })
  const ready = useNodesInitialized()
  useEffect(() => void (ready && refit()), [ready, shape])  // eslint-disable-line react-hooks/exhaustive-deps -- fitted once the boxes are measured, and as the states change
  const [fixed, setFixed] = useState<string[]>(() => kept(fixedKey) ?? [])  // in springs, the boxes you fixed where they are
  const live = style === "springs"
  const now = detail.on ? detail.state : null
  const doing    = !!now && !detail.waking && !!detail.states.find((s) => s.name === now)?.do.length  // its actions running, its wait not begun
  const checking = !!now && !doing && (!detail.waking || Date.parse(detail.waking) <= Date.now())  // its wait over: it tries its ways out
  const dark = document.documentElement.classList.contains("dark")

  const made = (s: State): StateNode => ({
    id: s.name, type: "state", position: places[s.name] ?? auto[s.name] ?? { x: 0, y: 0 },
    data: { state: s, start: s.name === detail.initial, lit: s.name === now, picked: s.name === picked, fixed: live && fixed.includes(s.name),
            waking: s.name === now ? detail.waking : null, onOpen: () => onInspect({ kind: "state", state: s.name }) },
  })
  const [nodes, setNodes, onNodesChange] = useNodesState<StateNode>(detail.states.map((s) => made(s)))
  useEffect(() => {  // what the states say, as it changes; each box kept as it is (where, its size), so it's not measured again
    setNodes((old) => detail.states.map((s) => {
      const was = old.find((n) => n.id === s.name)
      return was ? { ...was, data: made(s).data } : made(s)
    }))
  }, [detail, auto, picked, live, fixed])  // eslint-disable-line react-hooks/exhaustive-deps

  const said = useMemo(() => {  // while it checks: each way out of the state it's in, whether it holds, and the one it takes
    const s = checking ? detail.states.find((s) => s.name === now) : null
    if (!s) return null
    const holding = s.next.map(holds), taken = holding.findIndex((v) => v === true)
    return Object.fromEntries(s.next.map((_, i) => [`${s.name}#${i}`, { tried: taken < 0 || i <= taken ? holding[i] : null, flowing: i === taken }]))
  }, [detail, now, checking])
  const [after, setAfter] = useState<typeof said>(null)  // what the last check said, for a cycle after it
  const last = useRef(said)
  useEffect(() => {
    if (said) { last.current = said; setAfter(null); return }
    if (!last.current) return
    setAfter(last.current)
    last.current = null
    const t = setTimeout(() => setAfter(null), 1000)
    return () => clearTimeout(t)
  }, [said])
  const shown = said ?? after

  const edges = useMemo<WayEdge[]>(() => {
    const pair = (a: string, b: string) => [a, b].sort().join("\u0000")
    const count = new Map<string, number>(), seen = new Map<string, number>()
    for (const s of detail.states) for (const b of s.next) count.set(pair(s.name, b.goto), (count.get(pair(s.name, b.goto)) ?? 0) + 1)
    return detail.states.flatMap((s) =>
      s.next.map((way, index) => {
        const key = pair(s.name, way.goto), lane = seen.get(key) ?? 0
        seen.set(key, lane + 1)
        return {
          id: `${s.name}#${index}`, type: "way" as const, source: s.name, target: way.goto,
          markerEnd: { type: MarkerType.Arrow, width: 16, height: 16, strokeWidth: 1.6, color: "var(--muted-foreground)" },
          data: { label: summary(way), number: index + 1, hint: way.desc, dashed: isElse(way), lane, lanes: count.get(key)!, style,
                  tried: shown?.[`${s.name}#${index}`]?.tried ?? null, flowing: !!shown?.[`${s.name}#${index}`]?.flowing,
                  onOpen: () => onInspect({ kind: "way", state: s.name, index }) },
        }
      }))
  }, [detail, style, shown])  // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (s: Style) => (setStyle(s), remember("graph.style", s))
  useEffect(() => {  // a new layout (a state added, a way changed): every box where it puts it, unless you moved it
    setNodes((old) => old.map((n) => ({ ...n, position: places[n.id] ?? auto[n.id] ?? n.position })))
  }, [auto])  // eslint-disable-line react-hooks/exhaustive-deps

  const sim  = useRef<Simulation<Box, undefined> | null>(null)  // in springs: the springs, live
  const held = useRef(new Set<string>())  // the boxes you drag
  const at   = useRef(nodes)
  at.current = nodes
  const settle = (s: Simulation<Box, undefined>) => setPlaces(() => {  // every box kept where it is
    const next = Object.fromEntries(s.nodes().map((b) => [b.id, corner(b)]))
    keep(placesKey, next)
    return next
  })
  useEffect(() => {  // springs: the boxes pulled from where they are, the fixed ones staying
    if (!live) return
    const s = sim.current = springs(detail, Object.fromEntries(at.current.map((n) => [n.id, n.position])))
    const by = new Map(s.nodes().map((b) => [b.id, b]))
    for (const id of fixed) {
      const b = by.get(id)
      if (b) [b.fx, b.fy] = [b.x, b.y]
    }
    s.on("tick", () => setNodes((old) => old.map((n) => {
      const b = by.get(n.id)
      return held.current.has(n.id) || !b || !Number.isFinite(b.x) || !Number.isFinite(b.y) ? n : { ...n, position: corner(b) }
    })))
    s.on("end", () => (settle(s), refit()))  // fitted each time it settles, a box you dragged too
    s.alpha(0.5).restart()
    return () => void (s.stop(), sim.current = null)
  }, [live, auto])  // eslint-disable-line react-hooks/exhaustive-deps
  const hold = (moved: Node[]) => {  // the boxes you drag, where your pointer has them
    const by = new Map(sim.current?.nodes().map((b) => [b.id, b]))
    for (const n of moved) {
      const b = by.get(n.id)
      if (b) [b.fx, b.fy] = [n.position.x + b.w / 2, n.position.y + H / 2]
    }
  }
  const drop = (moved: Node[]) => {  // springs: the boxes you let go of free again, but the fixed ones
    hold(moved)
    const by = new Map(sim.current?.nodes().map((b) => [b.id, b]))
    for (const n of moved) {
      held.current.delete(n.id)
      const b = by.get(n.id)
      if (b && !fixed.includes(n.id)) [b.fx, b.fy] = [null, null]
    }
    sim.current?.alphaTarget(0).alpha(0.3).restart()
  }
  const fix = (n: Node) => {  // springs: a box fixed where it is, or freed
    const next = fixed.includes(n.id) ? fixed.filter((id) => id !== n.id) : [...fixed, n.id]
    const b = sim.current?.nodes().find((b) => b.id === n.id)
    if (b) [b.fx, b.fy] = next.includes(n.id) ? [n.position.x + b.w / 2, n.position.y + H / 2] : [null, null]
    setFixed(next)
    keep(fixedKey, next)
    sim.current?.alpha(0.3).restart()
  }

  useEffect(() => {  // the room it has changes (the window resized)
    const watched = new ResizeObserver(() => refit())
    watched.observe(box.current!)
    return () => watched.disconnect()
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={box} className="relative min-h-0 flex-1"
         onKeyDown={(e) => {  // a box opens on Enter or Space, as on a click
           const id = (e.key === "Enter" || e.key === " ") && (e.target as HTMLElement).closest<HTMLElement>(".react-flow__node")?.dataset.id
           if (id) (e.preventDefault(), onInspect({ kind: "state", state: id }))
         }}>
      <ReactFlow<StateNode, WayEdge>
        nodes={nodes} edges={edges} onNodesChange={onNodesChange} nodeTypes={NODES} edgeTypes={EDGES}
        onNodeDragStart={(_, __, moved) => live && (moved.forEach((n) => held.current.add(n.id)), hold(moved), sim.current?.alphaTarget(0.3).restart())}
        onNodeDrag={(_, __, moved) => live && hold(moved)}
        onNodeDragStop={(_, __, moved) => live ? drop(moved) : setPlaces((all) => {
          const next = { ...all, ...Object.fromEntries(moved.map((n) => [n.id, { x: Math.round(n.position.x), y: Math.round(n.position.y) }])) }
          keep(placesKey, next)
          return next
        })}
        onNodeDoubleClick={(_, n) => live && (clearTimeout(click.current), fix(n))}
        zoomOnDoubleClick={!live}
        onNodeClick={(e, n) => !live ? n.data.onOpen() : e.detail < 2 && (click.current = window.setTimeout(n.data.onOpen, 150))}
        onPaneClick={onPane}
        onMoveEnd={(e, v) => (e || hand.current) && ((hand.current = false), (moved.current = true), keep(viewKey, v))}
        defaultViewport={view ?? undefined} fitView={!view} fitViewOptions={FIT}
        minZoom={0.3} maxZoom={2.5} nodesConnectable={false} edgesFocusable={false} deleteKeyCode={null}
        colorMode={dark ? "dark" : "light"} proOptions={{ hideAttribution: true }}
        aria-label={`${detail.name}: its states and transitions`}>
        <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} />
        <Panel position="bottom-center">
          <div className="flex gap-1 rounded-xl border bg-background/90 p-1 shadow-sm backdrop-blur">
            <Button size="icon-sm" variant="ghost" title="Zoom in" aria-label="Zoom in" onClick={() => (hand.current = true, void flow.zoomIn())}><ZoomIn /></Button>
            <Button size="icon-sm" variant="ghost" title="Zoom out" aria-label="Zoom out" onClick={() => (hand.current = true, void flow.zoomOut())}><ZoomOut /></Button>
            <Button size="icon-sm" variant="ghost" title="Fit to the window" aria-label="Fit to the window"
                    onClick={() => ((moved.current = false), keep(viewKey, null), void flow.fitView({ ...FIT, duration: 300 }))}><Maximize /></Button>
          </div>
        </Panel>
        {(onAdd || sweep) && (
          <Panel position="center-left" className="flex flex-col gap-2">
            {onAdd && <Button size="icon-lg" variant="outline" className={cn(SIDE, "size-11")} title="New state" aria-label="New state" onClick={onAdd}><Plus /></Button>}
            {sweep && (sweep.names.length > 0 ? (
              <Confirm title={`Delete ${sweep.names.length === 1 ? "a state nothing leads to" : `${sweep.names.length} states nothing leads to`}?`}
                       description={`${sweep.names.map(humane).join(", ")}, with their actions and transitions. Nothing can reach ${sweep.names.length === 1 ? "it" : "them"} from the start. This can't be undone.`}
                       action="Delete" onConfirm={sweep.onSweep}>
                <Button size="icon-lg" variant="outline" className={cn(SIDE, "size-11")} title="Sweep away the states nothing leads to" aria-label="Sweep away the states nothing leads to"><Broom /></Button>
              </Confirm>
            ) : (
              <Button size="icon-lg" variant="outline" className={cn(SIDE, "size-11")} title="Every state can be reached" aria-label="Every state can be reached" disabled><Broom /></Button>
            ))}
          </Panel>
        )}
        <Panel position="bottom-left">
          <ToggleGroup type="single" size="sm" spacing={1} value={style} onValueChange={(s) => s && pick(s as typeof style)} aria-label="The view"
                       className="gap-1 rounded-xl border bg-background/90 p-1 shadow-sm backdrop-blur">
            {STYLES.map((s) => {
              const Icon = s === "curved" ? Spline : s === "elbow" ? CornerDownRight : s === "straight" ? Minus : Orbit
              return (
                <ToggleGroupItem key={s} value={s} className="size-7 px-0" aria-label={`${s} arrows`}
                                 title={s === "springs" ? "Springs: drag a state to pull the others, double-click it to fix it" : `${s[0].toUpperCase()}${s.slice(1)} arrows`}>
                  <Icon />
                </ToggleGroupItem>
              )
            })}
          </ToggleGroup>
        </Panel>
      </ReactFlow>
    </div>
  )
}

/** A state: its name, what it does, how often; lit when the program's in it. Arrows bind to it
 * anywhere on its edge, so its handles are only there to be bound to, unseen. */
function StateBox({ data, dragging }: NodeProps<StateNode>) {
  const { state: s, start, lit, picked, fixed, waking } = data
  const [, tick] = useState(0)
  useEffect(() => {
    if (!waking) return
    const t = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [waking])
  const left = waking ? Math.max(0, Math.round((new Date(waking).getTime() - Date.now()) / 1000)) : null
  const waits = lit && left !== null && left > 0
  const doing = lit && !waking && !!s.do.length  // its wait not begun: its actions running
  return (
    <div title={[s.desc, fixed && "fixed where it is: double-click to free it"].filter(Boolean).join(" · ") || undefined} style={{ width: width(s.name), height: H }}
         aria-label={fixed ? `${s.name}, fixed` : undefined}
         className={cn("relative flex flex-col items-center justify-center rounded-xl bg-card px-3 text-card-foreground shadow-xs transition-colors",
                       fixed ? "border-[3px] border-foreground" : "border-[1.5px]",
                       lit ? "border-primary bg-primary text-primary-foreground" : !fixed && "hover:border-foreground/30", dragging && "shadow-md",
                       picked && "ring-2 ring-ring ring-offset-2 ring-offset-background")}>
      {lit && <span aria-hidden className={cn("pointer-events-none absolute -inset-1.5 rounded-[16px]", doing ? "animate-round" : "border-2 border-brand/60 motion-safe:animate-breathe")} />}
      {start && <span className="absolute -top-5 left-2 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">start</span>}
      <span className="max-w-full truncate font-mono text-[14px] font-medium">{humane(s.name)}</span>
      <span className={cn("flex items-center gap-1 text-xs", lit ? "text-primary-foreground/80" : "text-muted-foreground")}>
        {waits ? (
          <><Hourglass className="size-3 animate-hourglass" aria-hidden /><span className="tabular-nums" aria-label={`waits ${left} seconds more`}>{clock(left!)}</span></>
        ) : doing ? (
          <span aria-label="doing its actions">doing<span aria-hidden className="animate-dots text-left font-mono">...</span></span>
        ) : lit ? (
          <><Loader2 className="size-3 motion-safe:animate-spin" aria-hidden />checking</>
        ) : <>{s.do.length ? `${s.do.length} action${s.do.length > 1 ? "s" : ""}` : "waits"} · {minutes(s.every)}</>}
      </span>
      <Handle type="source" position={Position.Right} className="!invisible" isConnectable={false} />
      <Handle type="target" position={Position.Left} className="!invisible" isConnectable={false} />
    </div>
  )
}

/** Seconds left as a clock: 4:05, or 1:02:05 past an hour. */
function clock(t: number): string {
  const [h, m, sec] = [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60]
  return `${h ? `${h}:${String(m).padStart(2, "0")}` : m}:${String(sec).padStart(2, "0")}`
}

let probe: SVGPathElement | null = null  // measures a path: where a point on it is, and which way it runs there

/** A point along a path, `at` its distance from the start given the path's length, and its
 * angle there in degrees, turned to read left to right. */
function along(path: string, at: (len: number) => number): XY & { angle: number } {
  if (!probe) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg")
    svg.setAttribute("style", "position:absolute;width:0;height:0;overflow:hidden")
    svg.setAttribute("aria-hidden", "true")
    probe = svg.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "path"))
    document.body.appendChild(svg)
  }
  probe.setAttribute("d", path)
  const half = at(probe.getTotalLength())
  const [a, b, c] = [probe.getPointAtLength(half - 2), probe.getPointAtLength(half + 2), probe.getPointAtLength(half)]
  let angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI
  if (angle > 90) angle -= 180
  if (angle < -90) angle += 180
  return { x: c.x, y: c.y, angle }
}

const centre = (n: InternalNode): XY => ({
  x: n.internals.positionAbsolute.x + (n.measured.width ?? 0) / 2, y: n.internals.positionAbsolute.y + (n.measured.height ?? 0) / 2,
})

/** Where a box's edge meets the line from its centre toward `to`, a gap out, and which side
 * that is. */
function bound(n: InternalNode, to: XY): XY & { side: Position } {
  const w = (n.measured.width ?? 0) / 2 + GAP, h = (n.measured.height ?? 0) / 2 + GAP, c = centre(n)
  const dx = to.x - c.x, dy = to.y - c.y
  const s = Math.min(w / Math.abs(dx || 1e-9), h / Math.abs(dy || 1e-9))
  const across = Math.abs(dx) * h > Math.abs(dy) * w
  return { x: c.x + dx * s, y: c.y + dy * s, side: across ? (dx > 0 ? Position.Right : Position.Left) : dy > 0 ? Position.Bottom : Position.Top }
}

/** A way out: an arrow from its state's edge to the other's, the side each faces the other,
 * moved aside when more than one goes between the same two; a loop over the box for one back
 * to itself. Its capsule opens it. */
function WayArrow({ id, source, target, data, markerEnd }: EdgeProps<WayEdge>) {
  const from = useInternalNode(source), to = useInternalNode(target)
  if (!from || !to || !data) return null
  let path: string
  if (source === target) {
    const c = centre(from), top = from.internals.positionAbsolute.y - GAP, h = 36 + data.lane * 24
    const l = c.x - 24 - data.lane * 6, r = c.x + 24 + data.lane * 6
    path = data.style === "curved" || data.style === "springs"
      ? `M${r},${top} C${r + 18},${top - h * 1.3} ${l - 18},${top - h * 1.3} ${l},${top}`
      : `M${r},${top} L${r},${top - h + 10} Q${r},${top - h} ${r - 10},${top - h} L${l + 10},${top - h} Q${l},${top - h} ${l},${top - h + 10} L${l},${top}`
  } else {
    const a = centre(from), b = centre(to), len = Math.hypot(b.x - a.x, b.y - a.y) || 1
    const off = (data.lane - (data.lanes - 1) / 2) * (source < target ? 1 : -1) * 22  // lanes are counted one way along the pair
    const n = { x: (-(b.y - a.y) / len) * off, y: ((b.x - a.x) / len) * off }
    const aside = (p: XY & { side: Position }) => (p.side === Position.Left || p.side === Position.Right ? { ...p, y: p.y + n.y } : { ...p, x: p.x + n.x })
    const p = aside(bound(from, { x: b.x + n.x, y: b.y + n.y })), q = aside(bound(to, { x: a.x + n.x, y: a.y + n.y }))
    const at = { sourceX: p.x, sourceY: p.y, sourcePosition: p.side, targetX: q.x, targetY: q.y, targetPosition: q.side }
    const bend = (0.2 + data.lane * 0.14) * len  // springs: an arc bowed to the left of its way, the lanes further out
    const c = { x: (a.x + b.x) / 2 + (-(b.y - a.y) / len) * bend, y: (a.y + b.y) / 2 + ((b.x - a.x) / len) * bend }
    const [s, t] = [bound(from, c), bound(to, c)]
    ;[path] = data.style === "springs" ? [`M${s.x},${s.y} Q${c.x},${c.y} ${t.x},${t.y}`]
      : data.style === "elbow" ? getSmoothStepPath({ ...at, borderRadius: 10, offset: 18 })
      : data.style === "straight" ? getStraightPath(at)
      : getBezierPath({ ...at, curvature: 0.3 })
  }
  const f    = (data.lane + 1) / (data.lanes + 1)  // the lanes' capsules apart, counted one way along the pair
  const mid  = along(path, (len) => len * (source === target || data.style === "springs" ? 0.5 : source < target ? f : 1 - f))
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} className={cn(data.flowing && "animate-flow")}
                style={{ strokeWidth: data.flowing ? 2.2 : 1.6, strokeDasharray: data.dashed && !data.flowing ? "5 5" : undefined,
                         stroke: data.flowing ? "var(--primary)" : undefined, opacity: data.tried === false ? 0.45 : 1 }} />
      <EdgeLabelRenderer>
        <button onClick={data.onOpen} title={[`${data.number}`, data.label, data.hint].filter(Boolean).join(" · ")}
                aria-label={`transition ${data.number}: ${data.label}${data.tried === true ? ", holds now" : data.tried === false ? ", doesn't hold now" : ""}`}
                style={{ transform: `translate(-50%, -50%) translate(${mid.x}px, ${mid.y}px) rotate(${mid.angle}deg)` }}
                className={cn("nodrag nopan pointer-events-auto absolute flex h-5 min-w-8 items-center justify-center rounded-full border-[1.5px] bg-background px-1 font-mono text-xs font-medium",
                              "before:absolute before:-inset-0.5 before:content-['']",  // a 24px target
                              "transition-colors", data.dashed && "border-dashed",
                              data.tried === true ? "border-emerald-500/70 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950 dark:text-emerald-300 dark:hover:bg-emerald-900"
                                : data.tried === false ? "border-destructive/60 bg-red-50 text-destructive hover:bg-red-100 dark:bg-red-950 dark:hover:bg-red-900"
                                : cn("hover:border-foreground/50 hover:bg-accent", data.dashed ? "text-muted-foreground" : "text-foreground"))}>
          <span style={{ transform: `rotate(${-mid.angle}deg)` }} className="flex items-center gap-0.5">
            {data.tried === true ? <Check aria-hidden strokeWidth={3} className="size-2.5" /> : data.tried === false && <X aria-hidden strokeWidth={3} className="size-2.5" />}
            {data.number}
          </span>
        </button>
      </EdgeLabelRenderer>
    </>
  )
}

const NODES = { state: StateBox }
const EDGES = { way: WayArrow }
