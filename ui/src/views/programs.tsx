// Programs, as scopes: Global › a program › a state. Each scope shows what's in it (the
// programs, each a card in the part of your day it belongs to; a program's states; a state's
// actions and transitions); what it can use (its signals, variables or rules, from one scope at
// a time, and the inputs) is in the drawer at the window's edge, for the scope you're in.
// Click into a program to go in, the path above goes back out; a state opens over the window, as
// a dialog does, back to the one you came from, closed by a click outside it (back to the graph).
//
// Each change goes to the engine as one (`apply_changes`): checked, and kept only if every
// program still runs. A state renamed takes its new name in the transitions to it, and as the
// program's start; a transition to a state not there yet makes it.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { DndContext, closestCenter, type DragEndEvent } from "@dnd-kit/core"
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { ArrowLeft, ArrowRight, Check, ChevronRight, Code, GripVertical, Eye, EyeOff, Lock, Pencil, Plus, RotateCcw, Trash2, X } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { PageHeader } from "@/components/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type {
  ActionSpec, BranchSpec, Change, GlobalSpecs, ProgramDetail, ProgramSpecs, Reference, RuleSpec, Scope, SignalSpec, Type, VarDetail, VariableSpec,
} from "@/lib/proki"
import { recall, recallJson, remember, rememberJson } from "@/lib/remember"
import { cn } from "@/lib/utils"
import { ACTIONS, ActionForm, BranchForm, NAMES, ProgramForm, RuleForm, SignalForm, StateForm, VariableForm, type Save } from "@/views/program-forms"
import { Expr } from "@/views/code"
import { RecordFields, said, TypeField, TypeIcon, TypeInside } from "@/views/fields"
import { GraphView } from "@/views/program-graph"
import { action, shown } from "@/views/program-inspect"
import { atomic, Inspect, Opens } from "@/views/inspect"
import { IconPicker } from "@/views/icon-picker"
import { useDrag } from "@/views/tasks"
import { AREAS, doing, friendly, humane, type Area } from "@/lib/friendly"

type Path = { program: string | null; state: string | null }
export type Where = { scope: Scope; program: string | null; state: string | null }
type Kind = "variable" | "signal" | "rule"
type Spec = VariableSpec | SignalSpec | RuleSpec
type Apply = (changes: Change[]) => Promise<string | null>
type Running = Reference["programs"][number]

const depth = (p: Path) => (p.program === null ? 0 : p.state === null ? 1 : 2)
const CHANGED = "proki:changed"  // a change kept: each part showing one reads it again
export const GLOBAL: Where = { scope: "global", program: null, state: null }

/** The programs, from `open`'s if given; `onWhere` hears the scope you're in. */
export function ProgramsView({ open = null, onWhere }: { open?: string | null; onWhere?: (where: Where) => void }) {
  const [path, setPath] = useState<Path>({ program: open, state: null })
  const [deeper, setDeeper] = useState(true)  // the way the last move went: in, or out
  const [trail, setTrail] = useState<string[]>([])  // the states you came through to this one, in this program
  const [reference, setReference] = useState<Reference | null>(null)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    const answer = await window.proki.tool("reference")
    if (answer.error) return setError(answer.error)
    setError("")
    setReference(answer)
  }, [])

  useEffect(() => {
    load()
    const live = setInterval(load, 5000)  // the states they're in, and the values
    window.addEventListener(CHANGED, load)
    return () => (clearInterval(live), window.removeEventListener(CHANGED, load))
  }, [load])
  useEffect(() => onWhere?.(path.program === null ? GLOBAL : { scope: path.state === null ? "program" : "state", ...path }), [path, onWhere])

  const title = (name: string) => {  // as the cards say it, else its name
    const found = reference?.programs.find((p) => p.name === name)
    return found ? friendly(found).title : name
  }
  const go = (next: Path, replace = false) => {  // replace: the same state, under another name
    const within = next.program === path.program && next.state !== null
    setTrail(!within ? [] : path.state && next.state !== path.state && !replace ? [...trail, path.state] : trail)
    setDeeper(depth(next) >= depth(path))
    setPath(next)
  }
  const back = () => (setTrail(trail.slice(0, -1)), setPath({ ...path, state: trail.at(-1) ?? null }))

  return (
    <div className="flex h-full min-h-0 flex-col">
      {path.program !== null && <nav className="flex items-center gap-1 px-8 pt-6 pb-3 text-sm">
        <Crumb active={path.program === null} onClick={() => go({ program: null, state: null })}>Automations</Crumb>
        {path.program !== null && (
          <>
            <ChevronRight className="size-4 text-muted-foreground" />
            <Crumb active>{title(path.program)}</Crumb>
          </>
        )}
      </nav>}
      {error && <p className="px-8 pb-2 text-sm text-destructive">{error}</p>}
      <div key={path.program ?? ""}
           className={cn("min-h-0 flex-1 overflow-y-auto px-8 pb-10 animate-in fade-in-0 duration-200", path.program === null && "pt-7", deeper ? "zoom-in-95" : "zoom-in-105")}>
        {reference && (path.program === null
          ? <GlobalScope reference={reference} onGo={go} onLoad={load} />
          : <ProgramScope key={path.program} name={path.program} state={path.state} before={trail.at(-1)} reference={reference} onGo={go} onBack={back} onLoad={load} />)}
      </div>
    </div>
  )
}

function Crumb({ active, mono, onClick, children }: { active?: boolean; mono?: boolean; onClick?: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick} disabled={!onClick || active}
            className={cn("max-w-[24rem] truncate rounded-md px-1.5 py-0.5", mono && "font-mono", active ? "font-heading text-xl font-semibold tracking-tight"
                                                                                    : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
      {children}
    </button>
  )
}

/** A scope's page: what's in it; `back`, if given, behind it, and `over` over both. */
function Layout({ main, back, over }: { main: ReactNode; back?: ReactNode; over?: ReactNode }) {
  if (!back) return <div className="flex min-w-0 flex-col gap-4">{main}</div>
  return (  // all of the page behind, the rest over it
    <div className="relative -mx-8 -mb-10 h-[calc(100%+2.5rem)] px-8">
      <div className="absolute inset-0 flex flex-col">{back}</div>
      <div className="pointer-events-none relative flex max-w-2xl min-w-0 flex-col gap-4 *:pointer-events-auto">{main}</div>
      {over}
    </div>
  )
}

/** A state, in the middle of the window: back to the one you came from (`before`), closed by ✕,
 * Escape or a click outside it. */
function Over({ state, before, onBack, onClose, children }: { state: string; before?: string; onBack: () => void; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && !e.defaultPrevented && !document.querySelector("[role=dialog], [role=alertdialog]") && onClose()
    window.addEventListener("keydown", key)
    return () => window.removeEventListener("keydown", key)
  }, [onClose])
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/10 p-6 supports-backdrop-filter:backdrop-blur-xs animate-in fade-in-0 duration-150 motion-reduce:animate-none"
         onClick={(e) => e.target === e.currentTarget && onClose()}>
      <aside aria-label={`the state ${state}`}
             className="flex max-h-[88vh] w-full max-w-2xl flex-col rounded-xl border bg-background shadow-lg animate-in fade-in-0 slide-in-from-top-2 duration-200 motion-reduce:animate-none">
        <header className="flex items-center gap-1 border-b py-2 pr-2 pl-4">
          {before && <Button size="sm" variant="ghost" className="-ml-2.5 text-muted-foreground" onClick={onBack} title={`Back to ${humane(before)}`}><ArrowLeft /> {humane(before)}</Button>}
          {before && <ChevronRight className="size-4 shrink-0 text-muted-foreground" />}
          <h2 title={state} className="min-w-0 flex-1 truncate px-1 font-heading text-base font-semibold">{humane(state)}</h2>
          <Button size="icon-sm" variant="ghost" aria-label="Close" onClick={onClose}><X /></Button>
        </header>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">{children}</div>
      </aside>
    </div>,
    document.body,
  )
}

/** Specs of a part (a program's, or the global scope's: null), and `change`: sent at once,
 * null when kept, else the mistake. */
function useSpecs<T>(name: string | null, enabled = true, onChanged?: () => void) {
  const [specs, setSpecs] = useState<T | null>(null)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    if (!enabled) return
    const answer = await window.proki.tool("program_specs", { name })
    if (answer.error) return setError(answer.error)
    setSpecs(answer as T)
  }, [name, enabled])

  useEffect(() => {
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [load])

  const change: Apply = async (changes) => {
    const answer = await window.proki.tool("apply_changes", { changes })
    if (answer.error) return answer.error
    setError("")
    window.dispatchEvent(new Event(CHANGED))  // this one too
    onChanged?.()
    return null
  }
  const act = async (changes: Change[]) => setError((await change(changes)) ?? "")
  return { specs, error, setError, change, act }
}

// --- global ---------------------------------------------------------------------------------

function GlobalScope({ reference, onGo, onLoad }: { reference: Reference; onGo: (p: Path) => void; onLoad: () => void }) {
  const { specs, error, setError, change, act } = useSpecs<GlobalSpecs>(null, true, onLoad)
  const [creating, setCreating] = useState(false)
  const [area, setArea] = useState<Area | "all">("all")

  const switchOn = async (name: string, on: boolean) => {
    const answer = await window.proki.tool("switch_program", { name, on })
    if (answer.error) setError(answer.error)
    onLoad()
  }
  const create: Save = async (data) => {
    const mistake = await change([{ op: "add", kind: "program", data }])
    if (!mistake) onGo({ program: String(data.name), state: null })
    return mistake
  }

  const made  = reference.programs.map((p) => ({ program: p, ...friendly(p) }))
  const on    = reference.programs.filter((p) => p.on).length
  const busy  = reference.programs.filter((p) => doing(p).busy).length
  const areas = AREAS.filter((a) => made.some((m) => m.area === a.id))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title="Automations" sub={<>
          Little helpers that work on their own while you do. Open one to see how it works, step by step, and change it.{" "}
          <span className="text-foreground"><span className="font-medium tabular-nums">{on} of {reference.programs.length}</span> on</span>
          {busy > 0 && <>, <span className="tabular-nums">{busy}</span> working right now</>}.
        </>}>
        {specs?.default && specs.changed && (
          <Confirm title="Reset the global settings?" description="Your changes to them go back to how they came." action="Reset"
                   onConfirm={async () => { setError((await revert(null)) ?? ""); act([]) }}>
            <Button size="sm" variant="outline"><RotateCcw data-icon="inline-start" /> Reset global</Button>
          </Confirm>
        )}
        <Button size="sm" onClick={() => setCreating(true)} disabled={creating}><Plus data-icon="inline-start" /> New automation</Button>
      </PageHeader>
      {error && <Mistake text={error} />}
      {creating && <ProgramForm saveLabel="Create" onSave={create} onCancel={() => setCreating(false)} />}

      <ToggleGroup type="single" variant="outline" size="sm" value={area} onValueChange={(v) => setArea((v || "all") as Area | "all")}
                   aria-label="Show automations for" className="flex-wrap">
        <ToggleGroupItem value="all">All</ToggleGroupItem>
        {areas.map((a) => <ToggleGroupItem key={a.id} value={a.id}>{a.title}</ToggleGroupItem>)}
      </ToggleGroup>

      {areas.filter((a) => area === "all" || a.id === area).map((a) => (
        <section key={a.id} aria-labelledby={`area-${a.id}`} className="flex flex-col gap-3">
          <div>
            <h2 id={`area-${a.id}`} className="text-base font-semibold">{a.title}</h2>
            <p className="text-xs text-muted-foreground">{a.about}</p>
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] gap-3">  {/* each card 270–360px wide: its least ¾ of its most */}
            {made.filter((m) => m.area === a.id).map(({ program }) => (
              <ProgramCard key={program.name} program={program} onOpen={() => onGo({ program: program.name, state: null })}
                           onSwitch={(to) => switchOn(program.name, to)} />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

/** A program as a card: its icon, title and what it does; a switch; what it's doing now, and
 * how many states it has. Click it to go in. */
function ProgramCard({ program, onOpen, onSwitch }: { program: Running; onOpen: () => void; onSwitch: (on: boolean) => void }) {
  const { title, icon: Icon, about } = friendly(program)
  const now = doing(program)
  return (
    <Card size="sm" role="button" tabIndex={0} onClick={onOpen} onKeyDown={(e) => e.target === e.currentTarget && e.key === "Enter" && onOpen()}
          aria-label={`${title}: see how it works`}
          className={cn("w-full max-w-[360px] cursor-pointer transition-[box-shadow,opacity] hover:ring-foreground/20 focus-visible:ring-ring", !program.on && "opacity-75")}>
      <CardHeader>
        <div className="flex items-start gap-3">
          <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", program.on ? "bg-primary/12 text-primary" : "bg-muted text-muted-foreground")}>
            <Icon aria-hidden className="size-[18px]" />
          </span>
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-1.5">
              {title}
              {program.kind === "code" && <Code className="size-3.5 shrink-0 text-muted-foreground" aria-label="built in, read only" />}
            </CardTitle>
            <CardDescription className="mt-0.5 line-clamp-2 min-h-[2lh]">{about}</CardDescription>
          </div>
        </div>
        <CardAction>
          <Switch checked={program.on} onClick={(e) => e.stopPropagation()} onCheckedChange={onSwitch} aria-label={`${title}: ${program.on ? "on" : "off"}`} />
        </CardAction>
      </CardHeader>
      <CardFooter className="mt-auto justify-between gap-2 border-t pt-3 text-xs">
        <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
          <span aria-hidden className={cn("size-1.5 shrink-0 rounded-full", now.busy ? "bg-brand motion-safe:animate-pulse" : program.on ? "bg-foreground/35" : "bg-muted-foreground/40")} />
          <span className={cn("truncate", now.busy && "font-medium text-foreground")}>{now.text}</span>
        </span>
        <span className="shrink-0 text-muted-foreground tabular-nums">{program.states.length} {program.states.length === 1 ? "step" : "steps"}</span>
      </CardFooter>
    </Card>
  )
}

// --- a program, and a state -----------------------------------------------------------------


function ProgramScope({ name, state, before, reference, onGo, onBack, onLoad }: {
  name: string
  state: string | null
  before?: string   // the state you came from to this one
  reference: Reference
  onGo: (p: Path, replace?: boolean) => void
  onBack: () => void
  onLoad: () => void
}) {
  const running = reference.programs.find((p) => p.name === name)
  const config = running?.kind !== "code"
  const { specs, error, setError, change, act } = useSpecs<ProgramSpecs>(name, config, onLoad)
  const [detail, setDetail] = useState<ProgramDetail | null>(null)

  const held = useRef<ProgramDetail | null>(null)
  const loadDetail = useCallback(async () => {
    const answer = await window.proki.tool("get_program", { name })
    if (!answer.error) setDetail(held.current = answer)
  }, [name])
  useEffect(() => {  // every 5 seconds; each second while its wait is over, until it waits again
    loadDetail()
    let n = 0
    const due = (d: ProgramDetail | null) => !!d?.on && (!d.waking || Date.parse(d.waking) <= Date.now())
    const live = setInterval(() => (++n % 5 === 0 || due(held.current)) && loadDetail(), 1000)
    window.addEventListener(CHANGED, loadDetail)
    return () => (clearInterval(live), window.removeEventListener(CHANGED, loadDetail))
  }, [loadDetail])

  if (!running) return <p className="text-sm text-muted-foreground">No program {name}.</p>
  if (!detail || (config && !specs)) return <p className="text-sm text-muted-foreground">{error || "Loading…"}</p>

  const props = { name, specs, detail, reference, change, act, setError, onGo, after: () => (loadDetail(), onLoad()) }

  return (
    <Layout
      main={<>{error && <Mistake text={error} />}<ProgramMain {...props} /></>}
      back={<GraphView key={detail.name} detail={detail} picked={state} onInspect={(next) => next && onGo({ program: name, state: next.state })}
                       onPane={() => onGo({ program: name, state: null })} />}
      over={state !== null && (
        <Over state={state} before={before} onBack={onBack} onClose={() => onGo({ program: name, state: null })}>
          <StateMain key={state} {...props} state={state} />
        </Over>
      )}
    />
  )
}

type ScopeProps = {
  name: string
  specs: ProgramSpecs | null  // null: a program in code
  detail: ProgramDetail
  reference: Reference
  change: Apply
  act: (changes: Change[]) => void
  setError: (error: string) => void
  onGo: (p: Path, replace?: boolean) => void
  after: () => void
}

function ProgramMain({ name, specs, detail, reference, change, act, setError, onGo, after }: ScopeProps) {
  const [editing, setEditing] = useState(false)
  const running = reference.programs.find((p) => p.name === name)
  const { icon: Icon } = friendly(running ?? { ...detail, name })

  const switchOn = async (on: boolean) => {
    const answer = await window.proki.tool("switch_program", { name, on })
    if (answer.error) setError(answer.error)
    after()
  }
  const saveProgram: Save = async (data) => {
    const mistake = await change([{ op: "update", kind: "program", data: { name, changes: data } }])
    if (!mistake) {
      setEditing(false)
      if (data.name !== name) onGo({ program: String(data.name), state: null })
    }
    return mistake
  }

  return (
    <>
      {editing && specs ? (
        <ProgramForm spec={specs.program} states={specs.states.map((s) => s.name)} onSave={saveProgram} onCancel={() => setEditing(false)} />
      ) : (
        <div className="flex items-start gap-3 rounded-xl border bg-card p-4 shadow-xs">
          <IconPicker value={detail.icon ?? ""} disabled={!specs} label="Change its icon"
                      onPick={(icon) => act([{ op: "update", kind: "program", data: { name, changes: { icon } } }])}>
            <button className={cn("grid size-10 shrink-0 place-items-center rounded-lg", detail.on ? "bg-primary/12 text-primary" : "bg-muted text-muted-foreground",
                                  specs && "hover:ring-2 hover:ring-primary/30")}>
              <Icon aria-hidden className="size-5" />
            </button>
          </IconPicker>
          <div className="min-w-0 flex-1">
            <p className="text-sm">{detail.desc || <span className="text-muted-foreground">No description.</span>}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {detail.on ? <>Now: <span className="text-foreground">{humane(detail.state)}</span></> : "Off"}
              {" · "}starts at <span>{humane(detail.initial)}</span>
              {detail.tags.length > 0 && <> · {detail.tags.map((t) => `#${t}`).join(" ")}</>}
              {!specs && <> · <Code className="inline size-3 align-[-2px]" /> in code, read only</>}
            </p>
          </div>
          <Switch checked={detail.on} onCheckedChange={switchOn} aria-label="on" />
          {specs && (
            <>
              <Button size="icon-sm" variant="ghost" aria-label="Edit" onClick={() => setEditing(true)}><Pencil /></Button>
              {specs.default && specs.changed && (
                <Confirm title={`Reset ${friendly(running ?? { ...detail, name }).title}?`} description="Your changes to it go back to how it came." action="Reset"
                         onConfirm={async () => { setError((await revert(name)) ?? ""); act([]) }}>
                  <Button size="icon-sm" variant="ghost" aria-label="Reset"><RotateCcw /></Button>
                </Confirm>
              )}
              <Confirm title={`Delete ${friendly(running ?? { ...detail, name }).title}?`} description="The automation and its steps are deleted. This can't be undone."
                       onConfirm={async () => {
                         const mistake = await change([{ op: "remove", kind: "program", data: { name } }])
                         if (mistake) setError(mistake)
                         else onGo({ program: null, state: null })
                       }}>
                <Button size="icon-sm" variant="ghost" aria-label="Delete"><Trash2 /></Button>
              </Confirm>
            </>
          )}
        </div>
      )}

    </>
  )
}

function StateMain({ name, state, specs, detail, reference, change, act, setError, onGo }: ScopeProps & { state: string }) {
  const [editing, setEditing] = useState(false)
  const live = detail.states.find((s) => s.name === state)
  const spec = specs?.states.find((s) => s.name === state)
  if (!live) return <p className="text-sm text-muted-foreground">No state {state}.</p>
  const go = (to: string) => onGo({ program: name, state: to })

  const saveState: Save = async (data) => {
    if (!specs) return null
    const renamed = String(data.name)
    const changes: Change[] = [{ op: "update", kind: "state", data: { program: name, name: state, changes: data } }]
    if (renamed !== state) {  // the ways out to it, and the program's start, go to its new name
      const seen: Record<string, number> = {}
      for (const b of specs.branches) {
        const index = (seen[b.state] = (seen[b.state] ?? -1) + 1)
        if (b.goto === state) {
          changes.push({ op: "update", kind: "branch", data: { program: name, state: b.state === state ? renamed : b.state, at: index, changes: { goto: renamed } } })
        }
      }
      if (specs.program.initial === state) changes.push({ op: "update", kind: "program", data: { name, changes: { initial: renamed } } })
    }
    const mistake = await change(changes)
    if (!mistake) {
      setEditing(false)
      if (renamed !== state) onGo({ program: name, state: renamed }, true)
    }
    return mistake
  }

  const at = { program: name, state }
  const actions = specs?.actions.filter((a) => a.state === state) ?? []
  const branches = specs?.branches.filter((b) => b.state === state) ?? []

  return (
    <>
      {editing && spec ? <StateForm spec={spec} onSave={saveState} onCancel={() => setEditing(false)} /> : (
        <div className="flex items-center gap-3 rounded-xl border bg-card p-4 shadow-xs">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              {state === detail.initial && <Badge variant="outline" className="text-[10px]">start</Badge>}
              {detail.on && state === detail.state && <Badge className="text-[10px]">now</Badge>}
              <p className="text-sm">{live.desc || <span className="text-muted-foreground">No description.</span>}</p>
            </div>
          </div>
          {specs && (
            <>
              <Button size="icon-sm" variant="ghost" aria-label="Edit" onClick={() => setEditing(true)}><Pencil /></Button>
              <Confirm title={`Delete the state ${state}?`} description="It and what it does are deleted. This can't be undone."
                       onConfirm={async () => {
                         const mistake = await change([{ op: "remove", kind: "state", data: { program: name, name: state } }])
                         if (mistake) setError(mistake)
                         else onGo({ program: name, state: null })
                       }}>
                <Button size="icon-sm" variant="ghost" aria-label="Delete"><Trash2 /></Button>
              </Confirm>
            </>
          )}
        </div>
      )}

      {specs ? (
        <>
          <Ordered title="Actions" empty="None: it waits." kind="action" at={at} items={actions} act={act} change={change}
                   line={(a: ActionSpec) => {
                     const { text } = action({ [a.kind]: a.params })
                     const [said, Icon, tint] = ACTIONS[a.kind] ?? [a.kind, Code, "bg-muted text-muted-foreground"]
                     return (
                       <>
                         <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-md", tint)}><Icon className="size-3" /></span>
                         <span className="w-12 shrink-0 font-medium">{said}</span>
                         {a.desc ? <span className="truncate text-muted-foreground">{a.desc}</span> : <Expr className="truncate">{text}</Expr>}
                       </>
                     )
                   }}
                   form={(a, onSave, onCancel) => <ActionForm spec={a} at={at} about={reference.actions} taken={actions.filter((b) => b !== a).map((b) => b.name)} onSave={onSave} onCancel={onCancel} />} />
          <Ordered title="Transitions" empty="None: it stays." kind="branch" at={at} items={branches} act={act} change={change}
                   before={(data) => specs.states.some((s) => s.name === data.goto) ? []
                     : [{ op: "add", kind: "state", data: { program: name, name: data.goto, desc: "", every: 1 } }]}
                   line={(b: BranchSpec, i: number) => <Way branch={b} live={live.next[i]} alone={branches.length === 1} onGo={go} />}
                   form={(b, onSave, onCancel) => <BranchForm spec={b} states={specs.states.map((s) => s.name)} onSave={onSave} onCancel={onCancel} />} />
        </>
      ) : (
        <>
          <Block title="Actions">
            {live.do.length === 0 && <p className="text-xs text-muted-foreground">None: it waits.</p>}
            {live.do.map((entry, i) => {
              const { kind, text } = action(entry)
              return <div key={i} className="flex gap-2 rounded-lg border px-3 py-1.5 text-xs"><span className="font-medium">{kind}</span><span className="truncate text-muted-foreground">{text}</span></div>
            })}
          </Block>
          <Block title="Transitions">
            {live.next.length === 0 && <p className="text-xs text-muted-foreground">In code.</p>}
            {live.next.map((b, i) => (
              <div key={i} className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs">
                <Way branch={{ program: name, state, goto: b.goto, when: [...b.conds.map((c) => c.expr), ...b.rules.map((r) => r.name)], desc: b.desc }} live={b} alone={live.next.length === 1} onGo={go} />
              </div>
            ))}
          </Block>
        </>
      )}
    </>
  )
}

/** A transition: what it's for, then each condition under it, marked whether it holds now (a
 * rule: more likely than not to fire), the rules with what they're for; and where it goes (click:
 * go there). What doesn't hold is greyed; `alone`, the state's only one, isn't called the else. */
function Way({ branch, live, alone, onGo }: { branch: BranchSpec; live?: ProgramDetail["states"][number]["next"][number]; alone?: boolean; onGo: (state: string) => void }) {
  return (
    <>
      <span className="grid min-w-0 flex-1 grid-cols-[0.875rem_minmax(0,10rem)_minmax(0,1fr)] items-center gap-x-2 gap-y-1 pl-1">
        {branch.desc && <span className="col-span-2 col-start-2 text-foreground">{branch.desc}</span>}
        {branch.when.length === 0 && !alone && <span className="col-start-2 text-muted-foreground">else</span>}
        {branch.when.map((w) => {
          const rule  = live?.rules.find((r) => r.name === w)
          const holds = rule ? (rule.chance == null ? null : rule.chance >= 0.5) : live?.conds.find((c) => c.expr === w)?.value
          return (
            <span key={w} className={cn("contents", holds !== true && "text-muted-foreground")}>
              <Truth value={holds} />
              <Expr className={cn("truncate", holds !== true && "opacity-60")} title={w}>{w}</Expr>
              <span className="min-w-0 text-muted-foreground">{rule?.desc}</span>
            </span>
          )
        })}
      </span>
      <span className="flex w-28 shrink-0">
        <span role="button" tabIndex={0} onClick={(e) => (e.stopPropagation(), onGo(branch.goto))} onKeyDown={(e) => e.key === "Enter" && onGo(branch.goto)}
              title={branch.goto} className="flex min-w-0 items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[11px] hover:border-foreground/30">
          <ArrowRight className="size-3 shrink-0" /><span className="truncate">{branch.goto}</span>
        </span>
      </span>
    </>
  )
}

/** Whether something holds now: a green tick, a red cross, a dash when it isn't known. */
function Truth({ value }: { value: unknown }) {
  if (value === true)  return <Check className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-label="true now" />
  if (value === false) return <X className="size-3.5 shrink-0 text-destructive" aria-label="false now" />
  return <span className="w-3.5 shrink-0 text-center text-muted-foreground" aria-label="not known now">–</span>
}

/** A state's actions or transitions: in order, each carried by its grip, edited or deleted, and
 * one added last. A drop kept shows at once; one refused springs back, and says why. `before`:
 * what's changed first, for what's saved. */
function Ordered<T extends ActionSpec | BranchSpec>({ title, empty, kind, at, items, line, form, before, change, act }: {
  title: string
  empty: string
  kind: "action" | "branch"
  at: { program: string; state: string }
  items: T[]
  line: (item: T, index: number) => ReactNode
  form: (item: T | undefined, onSave: Save, onCancel: () => void) => ReactNode
  before?: (data: Record<string, unknown>) => Change[]
  change: Apply
  act: (changes: Change[]) => void
}) {
  const [open, setOpen] = useState<number | "new" | null>(null)
  const close = () => setOpen(null)
  const saved = (data: Record<string, unknown>, changes: Change[]) => async () => {
    const mistake = await change([...(before?.(data) ?? []), ...changes])
    if (!mistake) close()
    return mistake
  }
  const sensors = useDrag()
  const [order, setOrder] = useState<number[] | null>(null)  // a drop, shown until the list comes back with it
  const [refused, setRefused] = useState<{ at: number; why: string } | null>(null)
  const kept = JSON.stringify(items)
  useEffect(() => setOrder(null), [kept])
  const dropped = async (e: DragEndEvent) => {
    if (!e.over || e.active.id === e.over.id) return
    const from = Number(e.active.id) - 1, to = Number(e.over.id) - 1
    setRefused(null)
    setOrder(arrayMove(items.map((_, i) => i), from, to))
    const why = await change([{ op: "remove", kind, data: { ...at, at: from } }, { op: "add", kind, data: { ...items[from], at: to } }])
    if (why) (setOrder(null), setRefused({ at: from, why }))
  }
  const shown = order ?? items.map((_, i) => i)

  return (
    <Block title={title} add={open === "new" ? undefined : () => setOpen("new")}>
      {items.length === 0 && open !== "new" && <p className="text-xs text-muted-foreground">{empty}</p>}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={dropped}>
        <SortableContext items={shown.map((i) => i + 1)} strategy={verticalListSortingStrategy}>
          {shown.map((i) => open === i ? (
            <div key={i}>{form(items[i], (data) => saved(data, [{ op: "update", kind, data: { ...at, at: i, changes: data } }])(), close)}</div>
          ) : (
            <Line key={i} id={i} refused={refused?.at === i} onEdit={() => setOpen(i)} onDelete={() => act([{ op: "remove", kind, data: { ...at, at: i } }])}>
              {line(items[i], i)}
            </Line>
          ))}
        </SortableContext>
      </DndContext>
      {refused && <Mistake text={`Not moved: ${refused.why}`} />}
      {open === "new" && form(undefined, (data) => saved(data, [{ op: "add", kind, data: { ...at, ...data } }])(), close)}
    </Block>
  )
}

// --- what a scope can use -------------------------------------------------------------------

/** What the scope you're in can use, read on its own: kept up as it changes, and as the editor
 * changes it. A program in code has none of its own. It fills the height it's given, the switch
 * for the hidden ones and the Clean button at its foot. */
export function Resources({ where }: { where: Where }) {
  const [reference, setReference] = useState<Reference | null>(null)
  const load = useCallback(async () => {
    const answer = await window.proki.tool("reference")
    if (!answer.error) setReference(answer)
  }, [])
  useEffect(() => {
    load()
    const live = setInterval(load, 5000)
    window.addEventListener(CHANGED, load)
    return () => (clearInterval(live), window.removeEventListener(CHANGED, load))
  }, [load])
  const code = reference?.programs.find((p) => p.name === where.program)?.kind === "code"
  const { specs, error, change, act } = useSpecs<GlobalSpecs | ProgramSpecs>(where.program, reference !== null && !code)
  if (!reference || (!specs && !code)) return <p className="p-3 text-xs text-muted-foreground">{error || "Loading…"}</p>
  const own = { variables: specs?.variables ?? [], signals: specs?.signals ?? [], rules: specs?.rules ?? [] }
  return (
    <div className="flex min-h-full flex-col gap-2 px-3 pt-3">
      {error && <Mistake text={error} />}
      <Kept key={`${where.scope}/${where.program}/${where.state}`} own={own} where={where} reference={reference} change={change} act={act} />
    </div>
  )
}

type Tab = Kind | "input"
const TABS: [Tab, string][] = [["input", "Inputs"], ["signal", "Signals"], ["variable", "Variables"], ["rule", "Rules"]]
const SCOPES: [Scope, string][] = [["special", "Special"], ["global", "Global"], ["program", "Program"], ["state", "State"]]

/** What a scope can use: the inputs, or one kind at a time, by the scope it's from, from the
 * widest down to this one, each opened by its line (one at a time: this one's to start). This
 * part's own are edited and added to; the rest, from elsewhere, are read. Any line can be hidden,
 * kept so in this window; the hidden ones show only on their switch, greyed. */
function Kept({ own, where, reference, change, act }: {
  own: { variables: VariableSpec[]; signals: SignalSpec[]; rules: RuleSpec[] }  // every one of the part's, at any level
  where: Where
  reference: Reference
  change: Apply
  act: (changes: Change[]) => void
}) {
  const [tab, setTab] = useState<Tab>(() => recall("programs.kind", TABS.map(([k]) => k), "signal"))
  const kind = tab === "input" ? "signal" : tab
  const scopes = SCOPES.filter(([s]) => s === "global" || (s === "special" ? kind === "variable" : s === "program" ? where.program !== null : where.state !== null))
  const [open, setOpen] = useState<Scope[]>([where.scope])  // the scopes open, any of them at once
  const [adding, setAdding] = useState<Scope | null>(null)
  const [hidden, setHidden] = useState(() => recall("programs.hidden", ["shown", "kept"], "kept") === "shown")
  const [hid, setHid]       = useState<string[]>(() => recallJson("programs.hid", []))  // each line hidden, as kind:name
  const full = (s: Spec) => (s.scope === "global" ? s.name : s.scope === "program" ? `${s.program}.${s.name}` : `${s.program}.${s.state}.${s.name}`)
  const rows = { variable: reference.variables, signal: reference.signals, rule: reference.rules }
  const valueOf = (s: Spec) => {
    const row = rows[kind].find((r) => r.name === full(s))
    return kind === "rule" ? (row as Reference["rules"][number] | undefined)?.chance : (row as { value?: unknown } | undefined)?.value
  }
  const veiled = (name: string) => hid.includes(`${kind}:${name}`)
  const veil   = (name: string) => {
    const next = veiled(name) ? hid.filter((k) => k !== `${kind}:${name}`) : [...hid, `${kind}:${name}`]
    setHid(next)
    rememberJson("programs.hid", next)
  }
  const any    = hid.filter((k) => k.startsWith(`${kind}:`)).length
  const all = [...own.variables, ...own.signals, ...own.rules]
  const found = (s: Spec) => ({ name: s.name, scope: s.scope, program: s.program, state: s.state })
  const add = (scope: Scope): Save => async (data) => {
    const mistake = await change([{ op: "add", kind, data: { ...data, program: where.program, state: scope === "state" ? where.state : null } }])
    if (!mistake) setAdding(null)
    return mistake
  }
  const of = (scope: Scope) => {
    const mine = (own[`${kind}s` as const] as Spec[]).filter((s) => s.scope === scope && (scope !== "state" || s.state === where.state) && (hidden || !veiled(full(s))))
    const taken = new Set(mine.map(full))
    const inside = scope === "program" ? `${where.program}.` : `${where.program}.${where.state}.`
    const outer = where.scope === "global" && scope !== "special"
      ? rows[kind].filter((r) => r.scope === scope && !taken.has(r.name) && (r as ObjectRow).fields)  // a table, kept by the code
      : rows[kind].filter((r) => r.scope === scope && !taken.has(r.name) && (scope === "global" || scope === "special" || r.name.startsWith(inside)))
    return { mine, outer: outer.filter((r) => hidden || !veiled(r.name)) }
  }

  return (
    <section className="flex flex-1 flex-col gap-2">
      <Names reference={reference} own={all.map((s) => s.name)} />
      <div className="flex gap-1 rounded-lg bg-muted p-1">
        {TABS.map(([k, title]) => (
          <button key={k} onClick={() => (setTab(k), setAdding(null), remember("programs.kind", k))}
                  className={cn("flex-1 rounded-md py-0.5 text-xs text-muted-foreground", tab === k && "bg-background font-medium text-foreground shadow-xs")}>
            {title}
          </button>
        ))}
      </div>
      {tab === "input" ? <Inputs reference={reference} /> : scopes.map(([scope, title]) => {
        const { mine, outer } = of(scope)
        const here = { ...where, scope }
        const shut = !open.includes(scope)
        const lines = [
          ...mine.map((s) => (
            <KeptLine key={`${s.scope}.${s.name}`} veiled={veiled(full(s))} onVeil={() => veil(full(s))} kind={kind} spec={s} where={here} value={valueOf(s)} full={full(s)}
                      type={(rows[kind].find((r) => r.name === full(s)) as { type?: Type } | undefined)?.type}
                      app={(rows[kind].find((r) => r.name === full(s)) as { app?: boolean } | undefined)?.app}
                      onSave={(data) => change([{ op: "update", kind, data: { ...found(s), changes: data } }])}
                      onDelete={() => act([{ op: "remove", kind, data: found(s) }])} />
          )),
          ...outer.map((r) => (r as ObjectRow).fields
            ? <ObjectLine key={r.name} object={r as ObjectRow} label={r.name} hidden={hidden} veiled={veiled(r.name)} onVeil={() => veil(r.name)} />
            : (
              <div key={r.name} className="group/line flex items-center gap-2 rounded-md px-1 py-1 text-xs">
                <span className={cn("flex min-w-0 flex-1 items-center gap-2", veiled(r.name) && "opacity-50")}>
                  {kind !== "rule" && <TypeIcon type={(r as { type?: Type }).type} />}
                  <span title={[r.name, hover(r)].filter(Boolean).join(" · ")} className="min-w-0 flex-1 truncate font-mono text-muted-foreground">{r.name}</span>
                  <Value value={kind === "rule" ? (r as Reference["rules"][number]).chance : (r as { value: unknown }).value} rule={kind === "rule"} name={r.name} />
                </span>
                <Veil name={r.name} veiled={veiled(r.name)} onClick={() => veil(r.name)} />
              </div>
            )),
        ]
        return (
          <div key={scope} className="flex flex-col gap-0.5">
            <div className="group flex items-center gap-1">
              <button onClick={() => (setOpen(shut ? [...open, scope] : open.filter((o) => o !== scope)), setAdding(null))}
                      aria-expanded={!shut} className="flex flex-1 items-center gap-1.5 rounded-md px-1 py-1 text-left hover:bg-background">
                <ChevronRight strokeWidth={3} className={cn("size-3.5 transition-transform", !shut && "rotate-90")} />
                <span className={cn("text-xs font-medium", shut && "text-muted-foreground")}>{title}</span>
                <span className="text-[11px] text-muted-foreground tabular-nums">{mine.length + outer.length}</span>
              </button>
              {scope !== "special" && (
                <Button size="icon-xs" variant="ghost" aria-label={`add to ${title.toLowerCase()}`} disabled={adding === scope}
                        onClick={() => (setOpen(shut ? [...open, scope] : open), setAdding(scope))}><Plus /></Button>
              )}
            </div>
            {!shut && (
              <div className="flex flex-col gap-0.5 pl-3">
                {adding === scope && <Defining kind={kind} where={here} onSave={add(scope)} onClose={() => setAdding(null)} />}
                {lines.length === 0 && <p className="px-1 text-xs text-muted-foreground">None.</p>}
                {lines}
              </div>
            )}
          </div>
        )
      })}
      <div className="sticky bottom-0 -mx-3 mt-auto flex items-center gap-2 border-t bg-background px-4 py-2 text-xs text-muted-foreground">
        {tab !== "input" && (
          <label className="flex items-center gap-2">
            <Switch size="sm" aria-label="Show hidden" checked={hidden} onCheckedChange={(on) => (setHidden(on), remember("programs.hidden", on ? "shown" : "kept"))} />
            Show hidden {any > 0 && <span className="tabular-nums">{any}</span>}
          </label>
        )}
        <Clean />
      </div>
    </section>
  )
}

/** Takes out what no automation's decision uses, asked first; what it's for on hover. */
function Clean() {
  const [failed, setFailed] = useState("")
  const clean = async () => {
    const answer = await window.proki.tool("remove_unused")
    setFailed(answer.error ?? "")
    if (!answer.error) window.dispatchEvent(new Event(CHANGED))
  }
  return (
    <Confirm title="Clean up?" action="Clean" onConfirm={clean}
             description="Every variable, signal and rule no automation decides by, directly or down a chain, is removed, with the steps that only set them. Metrics stay. This can't be undone.">
      <Button size="xs" variant="ghost" className={cn("ml-auto", failed && "text-destructive")}
              title={failed || "Removes the variables, signals and rules no automation decides by, directly or down a chain, and the steps that only set them. Metrics stay."}>
        Clean
      </Button>
    </Confirm>
  )
}

/** One of this part's own: its name (its description on hover) and its value, on a line; click
 * to see and edit it, in a panel over the page. */
type ObjectField = VarDetail & { shown?: boolean }
type ObjectRow   = VarDetail & { fields?: ObjectField[] }

/** A field's own fields: a table's or a record's, else an object's, from its type (none: neither). */
const inside = (f: ObjectRow): ObjectField[] | undefined => {
  if (f.fields) return f.fields
  const props = typeof f.type === "object" && f.type.type === "object" ? f.type.properties as Record<string, Record<string, unknown>> | undefined : undefined
  return props && Object.entries(props).map(([key, type]) => ({ name: `${f.name}.${key}`, desc: String(type.description ?? ""), type, persist: false,
                                                                  value: (f.value as Record<string, unknown> | null)?.[key] }))
}

/** A variable with fields (work, work.tasks, track): its name, `label`, (what it is, on hover),
 * click it to see what it is; open, its fields, each with its value for the record at hand, each
 * hidden as any line is (yours, kept in this window, else as the code says), shown greyed on the
 * switch, `hidden`. A field with fields of its own (work.tasks, work.plan) opens as one. */
function ObjectLine({ object, label, hidden, veiled, onVeil }: { object: ObjectRow; label: string; hidden: boolean; veiled?: boolean; onVeil: () => void }) {
  const key = `space.${object.name}.shown`  // as it was kept before: your choices stay
  const [open, setOpen]       = useState(false)
  const [viewing, setViewing] = useState(false)
  const [chosen, setChosen]   = useState<Record<string, boolean>>(() => recallJson(key, {}))
  const fields = object.fields ?? []
  const short  = (f: VarDetail) => f.name.slice(object.name.length + 1)
  const sees   = (f: ObjectField) => chosen[short(f)] ?? f.shown ?? true
  const veil   = (f: ObjectField) => {
    const next = { ...chosen, [short(f)]: !sees(f) }
    setChosen(next)
    rememberJson(key, next)
  }
  return (
    <div className="flex flex-col gap-0.5">
      <div className="group/line flex items-center gap-2 rounded-md px-1 py-1 text-xs hover:bg-background">
        <button onClick={() => setViewing(true)} className={cn("flex min-w-0 flex-1 items-center gap-2 text-left", veiled && "opacity-50")}>
          <TypeIcon type={object.type ?? "object"} />
          <span title={[object.name, hover({ desc: object.desc, type: object.type ?? "object" })].filter(Boolean).join(" · ")} className="min-w-0 flex-1 truncate font-mono font-medium">{label}</span>
        </button>
        <span className={cn("flex w-20 shrink-0 justify-end font-mono", veiled && "opacity-50")}>
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
                  className="-mx-1 inline-flex items-center gap-0.5 rounded px-1 whitespace-nowrap text-muted-foreground underline decoration-dotted underline-offset-2 hover:bg-muted hover:text-foreground">
            {fields.length} fields<ChevronRight className={cn("size-3 transition-transform", open && "rotate-90")} />
          </button>
        </span>
        <Veil name={object.name} veiled={veiled} onClick={onVeil} />
      </div>
      {open && (
        <div className="ml-[0.6875rem] flex flex-col gap-0.5 border-l pl-2">
          {fields.filter((f) => hidden || sees(f)).map((f) => inside(f)
            ? <ObjectLine key={f.name} object={{ ...f, fields: inside(f) }} label={short(f)} hidden={hidden} veiled={!sees(f)} onVeil={() => veil(f)} />
            : (
            <div key={f.name} className="group/line flex items-center gap-2 rounded-md px-1 py-1 text-xs hover:bg-background">
              <span className={cn("flex min-w-0 flex-1 items-center gap-2", !sees(f) && "opacity-50")}>
                <TypeIcon type={f.type} />
                <span title={[f.name, hover(f)].filter(Boolean).join(" · ")} className="min-w-0 flex-1 truncate font-mono text-muted-foreground">{short(f)}</span>
                <Value value={f.value} name={f.name} />
              </span>
              <Veil name={f.name} veiled={!sees(f)} onClick={() => veil(f)} />
            </div>
          ))}
          {!hidden && !fields.some(sees) && <span className="px-1 py-0.5 text-[11px] text-muted-foreground">All hidden: switch on the hidden ones to see them</span>}
        </div>
      )}
      {viewing && <Viewing object={object} onClose={() => setViewing(false)} />}
    </div>
  )
}

/** A variable the app keeps, over the page: what it is, and its fields; a record's, each with how
 * it's worked out, to change; else each with its type. */
function Viewing({ object, onClose }: { object: ObjectRow; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <DialogTitle className="flex min-w-0 items-center gap-2 font-mono">
            <TypeIcon type={object.type ?? "object"} className="size-4" /><span className="truncate">{object.name}</span>
            <Lock className="size-3.5 shrink-0 text-muted-foreground" aria-label="kept by the app" />
          </DialogTitle>
          <DialogDescription className="break-words">{object.desc || "No description"}</DialogDescription>
        </DialogHeader>
        <RecordFields record={object.name}>
          <section className="flex flex-col border-t pt-3">
            <span className="mb-1.5 text-xs font-medium">Fields</span>
            {(object.fields ?? []).map((f) => (
              <div key={f.name} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] items-center gap-3 border-b py-2 text-xs last:border-b-0">
                <span className="flex min-w-0 items-center gap-1.5"><TypeIcon type={f.type} /><code className="truncate font-medium">{f.name.slice(object.name.length + 1)}</code></span>
                <span className="text-muted-foreground">{f.desc || "–"}</span>
              </div>
            ))}
          </section>
        </RecordFields>
      </DialogContent>
    </Dialog>
  )
}

function KeptLine({ kind, spec, where, value, full, type, app, veiled, onVeil, onSave, onDelete }: {
  kind: Kind
  spec: Spec
  where: Where
  value: unknown
  full: string
  type?: Type
  app?: boolean     // the app reads it: it can't be removed, nor retyped
  veiled?: boolean  // a hidden one, shown on the switch
  onVeil: () => void
  onSave: Save
  onDelete: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className="group/line flex items-center gap-2 rounded-md px-1 py-1 text-xs hover:bg-background">
        <button onClick={() => setOpen(true)} className={cn("flex min-w-0 flex-1 items-center gap-2 text-left", veiled && "opacity-50")}>
          {kind !== "rule" && <TypeIcon type={type} />}
          <span title={[spec.name, hover({ desc: spec.desc, type })].filter(Boolean).join(" · ")} className="min-w-0 flex-1 truncate font-mono font-medium">{spec.name}</span>
          {app && <Lock className="size-3 shrink-0 text-muted-foreground" aria-label="the app reads it: kept" />}
        </button>
        <span className={cn("flex", veiled && "opacity-50")}><Value value={value} rule={kind === "rule"} name={full} /></span>
        <Veil name={full} veiled={veiled} onClick={onVeil} />
      </div>
      {open && <Defining kind={kind} spec={spec} where={where} full={full} type={type} onSave={onSave} onDelete={app ? undefined : onDelete} onClose={() => setOpen(false)} />}
    </>
  )
}

/** A line's hide button, on hover; a hidden line's show button, always there. */
function Veil({ name, veiled, onClick }: { name: string; veiled?: boolean; onClick: () => void }) {
  return (
    <Button size="icon-xs" variant="ghost" aria-label={`${veiled ? "Show" : "Hide"} ${name}`} title={veiled ? "Show it" : "Hide it"} onClick={onClick}
            className={cn("size-5 shrink-0 text-muted-foreground [&_svg]:size-3.5", !veiled && "opacity-0 group-hover/line:opacity-100 focus-visible:opacity-100")}>
      {veiled ? <Eye /> : <EyeOff />}
    </Button>
  )
}

/** A variable's, a signal's or a rule's definition (a new one's, without `spec`), over the page:
 * its name the title, its description under it, each edited in place; then the rest. */
function Defining({ kind, spec, where, full, type: worked, onSave, onDelete, onClose }: {
  kind: Kind
  spec?: Spec
  where: Where
  full?: string     // its full name (none: a new one)
  type?: Type       // its type as it's worked out (its own: as it says)
  onSave: Save
  onDelete?: () => void
  onClose: () => void
}) {
  const [name, setName] = useState(spec?.name ?? "")
  const [desc, setDesc] = useState(spec?.desc ?? "")
  const [type, setType] = useState<Type>((spec as { type?: Type } | undefined)?.type ?? "any")
  const named = { name, desc, type }
  const save: Save = async (data) => { const mistake = await onSave(data); if (!mistake) onClose(); return mistake }
  const props = { where, named, onSave: save, onCancel: onClose }
  const deep  = typeof type === "object" && (type.type === "object" || type.type === "array")  // its fields want the room
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className={cn("max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg", deep && "sm:max-w-2xl")}>
        <DialogHeader className="pr-14">
          <div className="flex items-start gap-3">
            <DialogTitle className="flex min-w-0 flex-1 items-center gap-2 font-mono">
              {kind !== "rule" && <TypeIcon type={type === "any" ? worked : type} className="size-4" />}
              <InPlace value={name} onChange={setName} code placeholder={`new ${kind}`} editing={!spec} />
            </DialogTitle>
            {kind !== "rule" && <TypeField label="" value={type} alone onChange={(t) => setType(t ?? "any")} />}
          </div>
          <DialogDescription asChild><div><InPlace value={desc} onChange={setDesc} placeholder="No description" /></div></DialogDescription>
        </DialogHeader>
        {onDelete && (
          <Confirm title="Delete it?" description="This can't be undone." onConfirm={() => (onDelete(), onClose())}>
            <Button size="icon-xs" variant="ghost" aria-label="Delete" className="absolute top-3.5 right-11"><Trash2 /></Button>
          </Confirm>
        )}
        {kind !== "rule" && <TypeInside value={type} onChange={setType} />}
        {kind === "variable" && full && <RecordFields record={full} />}
        {kind === "variable" ? <VariableForm spec={spec as VariableSpec | undefined} {...props} />
          : kind === "signal" ? <SignalForm spec={spec as SignalSpec | undefined} {...props} />
          : <RuleForm spec={spec as RuleSpec | undefined} {...props} />}
      </DialogContent>
    </Dialog>
  )
}

/** Text that's read as it is, and edited where it is: a pencil on hover, then a field. */
function InPlace({ value, onChange, code, placeholder, editing: start = false }: {
  value: string
  onChange: (value: string) => void
  code?: boolean
  placeholder: string
  editing?: boolean
}) {
  const [editing, setEditing] = useState(start)
  const done = (e: React.KeyboardEvent) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), setEditing(false))
  if (editing && code) {
    return <Input value={value} onChange={(e) => onChange(e.target.value)} autoFocus placeholder={placeholder} onBlur={() => setEditing(false)}
                  onKeyDown={done} autoCapitalize="off" autoCorrect="off" spellCheck={false} className="h-8 font-mono" />
  }
  if (editing) {
    return <Textarea value={value} onChange={(e) => onChange(e.target.value)} autoFocus placeholder={placeholder} onBlur={() => setEditing(false)}
                     onKeyDown={done} className="field-sizing-content min-h-0 resize-none text-sm" />
  }
  return (
    <span role="button" tabIndex={0} onClick={() => setEditing(true)} onKeyDown={(e) => e.key === "Enter" && setEditing(true)}
          className="group/edit inline-flex max-w-full cursor-text items-center gap-1.5">
      <span className={cn(code ? "truncate" : "min-w-0 break-words", !value && "text-muted-foreground italic")}>{value || placeholder}</span>
      <Pencil className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition group-hover/edit:opacity-100" />
    </span>
  )
}

/** The inputs: what's measured, the same everywhere. One that's on can be read by name; its
 * history (minutes) is kept as a table, for what reads its past. */
function Inputs({ reference }: { reference: Reference }) {
  const { specs, error, act } = useSpecs<GlobalSpecs>(null)
  const used = Object.fromEntries((specs?.inputs ?? []).map((i) => [i.name, i]))
  if (!specs) return <p className="px-1 text-xs text-muted-foreground">{error || "Loading…"}</p>
  return (
    <div className="flex flex-col">
      {error && <Mistake text={error} />}
      <div className="flex gap-2 px-1 pb-1 text-[11px] text-muted-foreground">
        <span className="flex-1" /><span className="w-20 text-right">Now</span><span className="w-16 text-right" title="minutes of history kept">History</span>
      </div>
      {reference.inputs.map((input) => (
        <InputLine key={input.name} name={input.name} desc={input.desc} type={input.type} value={input.value} spec={used[input.name]}
                   onBackfill={(backfill) => act([used[input.name] ? { op: "update", kind: "input", data: { name: input.name, changes: { backfill } } }
                                                                   : { op: "add", kind: "input", data: { name: input.name, backfill } }])} />
      ))}
    </div>
  )
}

function InputLine({ name, desc, type, value, spec, onBackfill }: {
  name: string
  desc: string
  type?: Type
  value: unknown
  spec?: { backfill: number | string | null }  // none: not read yet
  onBackfill: (backfill: number | string | null) => void
}) {
  const [backfill, setBackfill] = useState(spec?.backfill == null ? "" : String(spec.backfill))
  useEffect(() => setBackfill(spec?.backfill == null ? "" : String(spec.backfill)), [spec?.backfill])
  const keep = () => {
    const next = backfill.trim() === "" ? null : /^\d+(\.\d+)?$/.test(backfill.trim()) ? Number(backfill) : backfill.trim()
    if (next !== (spec?.backfill ?? null)) onBackfill(next)
  }
  return (
    <div className={cn("flex items-center gap-2 px-1 py-1 text-xs", !spec && "text-muted-foreground")} title={hover({ desc, type })}>
      <TypeIcon type={type} />
      <span title={name} className="min-w-0 flex-1 truncate font-mono">{name}</span>
      <Value value={value} name={name} />
      <Input value={backfill} onChange={(e) => setBackfill(e.target.value)} onBlur={keep} onKeyDown={(e) => e.key === "Enter" && keep()}
             placeholder="–" title="how much history is kept: 1d, 12h, or minutes" className="h-6 w-16 shrink-0 px-1.5 text-[11px]" />
    </div>
  )
}

/** What an expression can say: its syntax, what it can call, and what an action does; found by
 * what's typed. */
export const SYNTAX: [string, string][] = [
  ["a + b, a // b, a % b", "arithmetic; // divides and rounds down"],
  ["a if c else b", "a when c is true, else b"],
  ["a and b, a or b, not a", "yes or no"],
  ["x in (1, 2)", "whether x is one of them"],
  ["xs[0], xs[-1]", "an item of a list; -1 is the last"],
  ["xs[1:], xs[:3]", "a part of a list; set queue to queue[1:] pops the first"],
  ["record.field", "a field of a record"],
  ["xs.field", "a field of every item: a column"],
  ["work.tasks[i].status", "set's or add's name: a field of a record, set on its table"],
]
/** The names a field suggests: the global ones, then the scope's own. */
function Names({ reference, own }: { reference: Reference; own: string[] }) {
  const global = [
    ...reference.inputs.filter((i) => i.used).map((i) => i.name),
    ...reference.signals.filter((s) => s.scope === "global").map((s) => s.name),
    ...reference.variables.filter((v) => v.scope === "global" || v.scope === "special")
                          .flatMap((v) => [v.name, ...((v as ObjectRow).fields ?? []).map((f) => f.name)]),
    ...reference.rules.filter((r) => r.scope === "global").map((r) => r.name),
  ]
  return <datalist id={NAMES}>{[...new Set([...own, ...global])].map((n) => <option key={n} value={n} />)}</datalist>
}

// --- what the scopes share ------------------------------------------------------------------

/** A program (null: the global scope) back to the default proki ships. */
async function revert(name: string | null): Promise<string | null> {
  const answer = await window.proki.tool("reset_program", { name })
  return answer.error ?? null
}

const chance = (c: number | null | undefined) => (c == null ? "–" : `${Math.round(c * 100)}%`)

/** A value beside its name, short enough to line up: yes or no as a mark, a big number in K, M
 * or B, a long text cut, all of it on hover; a list or a record, what it holds, opened as a table. */
export function Value({ value, rule, name }: { value: unknown; rule?: boolean; name?: string }) {
  const [open, setOpen] = useState(false)
  const all = rule ? chance(value as number | null) : shown(value)
  if (!rule && !atomic(value)) return (
    <span className="flex w-20 shrink-0 justify-end font-mono">
      <Opens value={value} onOpen={() => setOpen(true)} />
      <Inspect title={name ?? "value"} value={value} open={open} onOpenChange={setOpen} />
    </span>
  )
  return (
    <span title={all} className="flex w-20 shrink-0 justify-end truncate font-mono text-muted-foreground tabular-nums">
      {typeof value === "boolean" && !rule ? <Truth value={value} /> : rule ? all : brief(value)}
    </span>
  )
}

function brief(value: unknown): string {
  if (typeof value === "number") {
    const [size, unit] = [[1e9, "B"], [1e6, "M"], [1e3, "K"]].find(([size]) => Math.abs(value) >= (size as number)) ?? [1, ""]
    return unit ? `${Math.trunc(value / (size as number))}${unit}` : shown(value)
  }
  if (typeof value === "string" && value.length > 10) return `"${value.slice(0, 8)}…"`
  return shown(value)
}

/** What a name shows on hover: its type, and what it is. */
export function hover({ desc, type }: { desc?: string; type?: Type }): string | undefined {
  return [type && type !== "any" ? said(type) : "", desc].filter(Boolean).join(" · ") || undefined
}

function Mistake({ text }: { text: string }) {
  return <Alert variant="destructive"><AlertDescription className="break-words">{text}</AlertDescription></Alert>
}

function Block({ title, add, children }: { title: string; add?: () => void; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium">{title}</h2>
        {add && <Button size="xs" variant="ghost" className="text-muted-foreground" onClick={add}><Plus /> Add</Button>}
      </div>
      {children}
    </section>
  )
}

/** A line of a list, carried by its grip: what it says, then its pencil and its bin; `refused`:
 * shaken, as a drop that wasn't kept. */
function Line({ id, refused, children, onEdit, onDelete }: { id: number; refused?: boolean; children: ReactNode; onEdit: () => void; onDelete: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: id + 1 })  // ids from 1: 0 isn't one
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }}
         className={cn("group flex items-center gap-2 rounded-lg border bg-card py-1.5 pr-3 pl-1 text-xs hover:bg-muted/50",
                       isDragging && "relative z-10 shadow-lg ring-1 ring-foreground/10", refused && "animate-shake ring-2 ring-destructive/50")}>
      <button {...attributes} {...listeners} aria-label="Move" className="cursor-grab touch-none text-muted-foreground/50 hover:text-muted-foreground">
        <GripVertical className="size-3.5" />
      </button>
      <div role="button" tabIndex={0} className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-left" onClick={onEdit}
           onKeyDown={(e) => e.key === "Enter" && onEdit()}>{children}</div>
      <div className="flex shrink-0 items-center opacity-0 group-hover:opacity-100 focus-within:opacity-100">
        <Button size="icon-xs" variant="ghost" aria-label="Edit" onClick={onEdit}><Pencil /></Button>
        <Confirm title="Delete it?" description="This can't be undone." onConfirm={onDelete}>
          <Button size="icon-xs" variant="ghost" aria-label="Delete"><Trash2 /></Button>
        </Confirm>
      </div>
    </div>
  )
}

