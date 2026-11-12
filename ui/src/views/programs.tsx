// Programs, as scopes: Global › a program › a state. Each scope shows what's in it (the
// programs, each a card in the part of your day it belongs to; a program's states; a state's
// actions and transitions); what it can use (its signals, variables or rules, from one scope at
// a time, and the inputs) is in a bubble at the window's corner, for the scope you're in.
// Click into a program to go in, the path above goes back out; a state opens in a dialog over
// the window, back to the one you came from, closed by ✕, Escape or a click around it, the
// bubble still in reach: a name picked there goes into the field you were in. Leaving a form
// you've changed asks first.
//
// Each change goes to the engine as one (`apply_changes`): checked, and kept only if every
// program still runs. A state renamed takes its new name in the transitions to it, and as the
// program's start; a transition to a state not there yet makes it.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { DndContext, closestCenter, type DragEndEvent } from "@dnd-kit/core"
import { SortableContext, arrayMove, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { ArrowLeft, ArrowRight, ChevronRight, Code, Pencil, Plus, RotateCcw, Trash2, X } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { ErrorDialog } from "@/components/error-dialog"
import { PageHeader, SearchBox } from "@/components/page"
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardFooter } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Switch } from "@/components/ui/switch"
import { GLOBAL, type ActionSpec, type BranchSpec, type Change, type GlobalSpecs, type ProgramDetail, type ProgramSpecs, type Reference, type Scope, type Where } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { ACTIONS, ActionForm, BranchForm, cleaned, contextOf, PopupFields, type Picks, StateForm, Tinted, type Save } from "@/views/program-forms"
import { ActionRows, ACTION_ROWS } from "@/views/action-rows"
import { AskJev, AskLlm, START } from "@/views/ask-actions"
import { exprText, parseExpr } from "@/lib/typed"
import { Expr } from "@/views/code"
import { Editable, Pick, Staging, typing, type Staged } from "@/views/in-place"
import { Discard } from "@/components/discard"
import { Truth } from "@/views/value-parts"
import { forgetGraph, GraphView } from "@/views/program-graph"
import { action } from "@/views/program-inspect"
import { NewProgram, ProgramDialog, TagChip } from "@/views/program-new"
import { useDrag } from "@/views/tasks"
import { friendly, humane, light } from "@/lib/friendly"
import { Apply, Block, CHANGED, FLASH, GO, Line, Path, Running, revert, useSpecs, bus } from "@/views/scope-shared"
import { Corner } from "@/views/resources"

const depth = (p: Path) => (p.program === null ? 0 : p.state === null ? 1 : 2)

/** An automation's title, as its card says it, else its name. */
const titled = (reference: Reference | null, name: string) => {
  const found = reference?.programs.find((p) => p.name === name)
  return found ? friendly(found).title : name
}

/** The scope you're in, said: "Global", else the automation's title, and its state. */
export function Scope({ where }: { where: Where }) {
  const [reference, setReference] = useState<Reference | null>(null)
  useEffect(() => {
    if (where.program === null) return
    const load = () => void window.proki.tool("reference").then((r) => !r.error && setReference(r))
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [where.program])
  return where.program === null ? "Global" : [titled(reference, where.program), where.state && humane(where.state)].filter(Boolean).join(" › ")
}

/** The programs, from `open`'s if given; `onWhere` hears the scope you're in. */
export function ProgramsView({ open = null, onWhere }: { open?: string | null; onWhere?: (where: Where) => void }) {
  const [path, setPath] = useState<Path>(() => bus.arriving ?? { program: open, state: null })
  const [deeper, setDeeper] = useState(true)  // the way the last move went: in, or out
  const [trail, setTrail] = useState<string[]>([])  // the states you came through to this one, in this program
  const [reference, setReference] = useState<Reference | null>(null)
  const [error, setError] = useState("")
  const [pending, setPending] = useState<(() => void) | null>(null)  // a move that would lose what you changed, asked first

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

  const title = (name: string) => titled(reference, name)
  const asked = (next: Path, move: () => void) => {  // a form you've changed, in what's left, asks first
    const losing = next.program !== path.program ? "form[data-dirty]" : next.state !== path.state ? "[data-panel] form[data-dirty]" : ""
    if (losing && document.querySelector(losing)) setPending(() => move)
    else move()
  }
  const go = (next: Path, replace = false) => asked(next, () => {  // replace: the same state, under another name
    const within = next.program === path.program && next.state !== null
    setTrail(!within ? [] : path.state && next.state !== path.state && !replace ? [...trail, path.state] : trail)
    setDeeper(depth(next) >= depth(path))
    setPath(next)
  })
  const back = () => asked({ ...path, state: trail.at(-1) ?? null }, () => (setTrail(trail.slice(0, -1)), setPath({ ...path, state: trail.at(-1) ?? null })))
  const going = useRef(go)
  going.current = go
  useEffect(() => {
    bus.arriving = null
    const heard = (e: Event) => (bus.arriving = null, going.current((e as CustomEvent<Path>).detail))
    window.addEventListener(GO, heard)
    return () => window.removeEventListener(GO, heard)
  }, [])

  return (
    <div className="flex h-full min-h-0 flex-col">
      {path.program !== null && <nav aria-label="Where you are" className="flex items-center gap-1 px-8 pt-6 pb-3 text-sm">
        <Crumb onClick={() => go({ program: null, state: null })}>Automations</Crumb>
        <ChevronRight aria-hidden className="size-4 text-muted-foreground" />
        <Crumb code>{title(path.program)}</Crumb>
      </nav>}
      {error && <ErrorDialog message={error} onClose={() => setError("")} />}
      <AlertDialog open={!!pending} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent size="sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Discard your changes?</AlertDialogTitle>
            <AlertDialogDescription>What you changed in the form you're editing isn't saved yet.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => (pending?.(), setPending(null))}>Discard</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <div key={path.program ?? ""}
           className={cn("min-h-0 flex-1 overflow-y-auto px-8 pb-10 animate-in fade-in-0 duration-200", path.program === null && "pt-7", deeper ? "zoom-in-95" : "zoom-in-105")}>
        {reference && (path.program === null
          ? <GlobalScope reference={reference} onGo={go} onLoad={load} />
          : <ProgramScope key={path.program} name={path.program} state={path.state} before={trail.at(-1)} reference={reference} onGo={go} onBack={back} onLoad={load} />)}
      </div>
    </div>
  )
}

/** A step of the path: one to go back to, or (no `onClick`) the page you're on, its heading. */
function Crumb({ onClick, code, children }: { onClick?: () => void; code?: boolean; children: ReactNode }) {
  if (!onClick) return <h1 aria-current="page" className={cn("max-w-[24rem] truncate px-1.5 py-0.5 font-heading text-xl font-semibold tracking-tight", code && "font-mono")}>{children}</h1>
  return <button onClick={onClick} className="max-w-[24rem] truncate rounded-md px-1.5 py-0.5 text-muted-foreground hover:bg-muted hover:text-foreground">{children}</button>
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

/** A state, in a dialog over the window: back to the one you came from (`before`), closed by ✕,
 * Escape or a click around it. The window behind is out of reach while it's open; the bubbles in
 * the corner aren't, and a bubble's panel open beside it moves it aside. Your focus goes to it as it
 * opens, and back as it closes. */
function Over({ state, before, onBack, onClose, children }: { state: string; before?: string; onBack: () => void; onClose: () => void; children: ReactNode }) {
  const heading = useRef<HTMLHeadingElement>(null)
  const last    = useRef(state)
  const closing = useRef(onClose)
  last.current    = state
  closing.current = onClose
  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && !e.defaultPrevented && !document.querySelector("[role=dialog]:not([data-panel]), [role=alertdialog]") && closing.current()
    window.addEventListener("keydown", key)
    return () => window.removeEventListener("keydown", key)
  }, [])
  useEffect(() => {
    const from   = document.activeElement as HTMLElement | null
    const behind = document.querySelector(".proki-frame")  // the window's views; what's put over it stays in reach
    behind?.setAttribute("inert", "")
    return () => {  // back where you were, else to the state's box
      behind?.removeAttribute("inert")
      const box = document.querySelector<HTMLElement>(`.react-flow__node[data-id="${window.CSS.escape(last.current)}"]`)
      ;(from?.isConnected && from !== document.body ? from : box)?.focus({ preventScroll: true })
    }
  }, [])
  useEffect(() => heading.current?.focus({ preventScroll: true }), [state])
  return createPortal(
    <div onClick={(e) => e.target === e.currentTarget && onClose()}
         className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-6 supports-backdrop-filter:backdrop-blur-[2px] motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-150 min-[1100px]:[[data-bubble]_&]:pr-[25rem]">
      <section data-panel role="dialog" aria-modal="true" aria-labelledby="state-heading"
               className="flex max-h-[min(88vh,52rem)] w-full max-w-2xl flex-col rounded-2xl border bg-background shadow-2xl motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-[0.98] motion-safe:duration-200">
        <header className="flex items-center gap-1 border-b py-2 pr-2 pl-4">
          {before && <Button size="sm" variant="ghost" className="-ml-2.5 text-muted-foreground" onClick={onBack} title={`Back to ${humane(before)}`}><ArrowLeft /> <span className="font-mono">{humane(before)}</span></Button>}
          {before && <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />}
          <h2 id="state-heading" ref={heading} tabIndex={-1} title={state} className="min-w-0 flex-1 truncate font-mono text-base font-semibold outline-none">{humane(state)}</h2>
          <Button size="icon-sm" variant="ghost" aria-label="Close the state" title="Close (Esc)" onClick={onClose}><X /></Button>
        </header>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain p-4">{children}</div>
      </section>
    </div>,
    document.body,
  )
}

function GlobalScope({ reference, onGo, onLoad }: { reference: Reference; onGo: (p: Path) => void; onLoad: () => void }) {
  const { specs, error, setError, change, act } = useSpecs<GlobalSpecs>(null, true, onLoad)
  const [creating, setCreating] = useState(false)
  const [tag, setTag]   = useState<string | null>(null)  // the tag picked: the automations that have it
  const [find, setFind] = useState("")

  const switchOn = async (name: string, on: boolean) => {
    const answer = await window.proki.tool("switch_program", { name, on })
    if (answer.error) setError(answer.error)
    onLoad()
  }
  const create: Save = async (data) => {
    forgetGraph(String(data.name))  // a name used before starts fitted
    const mistake = await change([{ op: "add", kind: "program", data }])
    if (!mistake) onGo({ program: String(data.name), state: null })
    return mistake
  }

  const uses  = new Map<string, number>()
  reference.programs.forEach((p) => p.tags.forEach((t) => uses.set(t, (uses.get(t) ?? 0) + 1)))
  const known = [...uses].sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0])).map(([t]) => t)  // the most used first
  const tags  = [...new Set([...known.slice(0, 20), ...(tag ? [tag] : [])])]
  const shown = reference.programs
    .map((p) => ({ program: p, title: friendly(p).title }))
    .filter(({ program: p, title }) => (!tag || p.tags.includes(tag)) && [title, p.name, p.desc, ...p.tags].join(" ").toLowerCase().includes(find.trim().toLowerCase()))
    .sort((x, y) => x.title.localeCompare(y.title))

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title="Automations" sub="Little helpers that work on their own.">
        {specs?.default && specs.changed && (
          <Confirm title="Reset the global settings?" description="Your changes to them go back to how they came." action="Reset"
                   onConfirm={async () => { setError((await revert(null)) ?? ""); act([]) }}>
            <Button size="sm" variant="outline" title="Reset the global settings"><RotateCcw data-icon="inline-start" /> Reset</Button>
          </Confirm>
        )}
        <Button size="sm" title="New automation" onClick={() => setCreating(true)} disabled={creating}><Plus data-icon="inline-start" /> New</Button>
        <SearchBox value={find} onChange={setFind} label="Search the automations" />
      </PageHeader>
      {error && <ErrorDialog message={error} onClose={() => setError("")} />}
      {creating && <NewProgram known={known} onCreate={create} onClose={() => setCreating(false)} />}

      <div className="flex flex-wrap gap-1.5" aria-label="Show the automations with a tag">
        {tags.map((t) => <TagChip key={t} tag={t} on={t === tag} onClick={() => setTag(t === tag ? null : t)} />)}
      </div>

      {shown.length === 0 && <p className="text-sm text-muted-foreground">No automation matches.</p>}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] gap-3">  {/* each card 270–360px wide: its least ¾ of its most */}
        {shown.map(({ program }) => (
          <ProgramCard key={program.name} program={program} tag={tag} onOpen={() => onGo({ program: program.name, state: null })}
                       onSwitch={(to) => switchOn(program.name, to)} onTag={(t) => setTag(t === tag ? null : t)} />
        ))}
      </div>
    </div>
  )
}

/** The state a program is in, its name only, behind a ball that shows how it is (see `light`): "Paused" while it's off. */
function StateLight({ program, className }: { program: { on: boolean; state: string }; className?: string }) {
  const lit = light(program)
  return (
    <span className={cn("flex min-w-0 items-center gap-2 text-xs", className)}>
      <span aria-hidden className={cn("ball", `ball-${lit}`)}><span className="ball-core" /></span>
      <span className={cn("translate-y-px truncate font-mono", lit === "off" ? "text-muted-foreground" : "text-foreground")}>{lit === "off" ? "Paused" : humane(program.state)}</span>
    </span>
  )
}

/** A program as a card: its icon, title and what it does; a switch; its tags (clicked, they pick that tag); and in the foot the state it's in,
 * lit yellow while idle, green while working, grey while off, and how many states it has. Click it to go in. */
function ProgramCard({ program, tag, onOpen, onSwitch, onTag }: { program: Running; tag: string | null; onOpen: () => void; onSwitch: (on: boolean) => void; onTag: (tag: string) => void }) {
  const { title, icon: Icon, about } = friendly(program)
  return (
    <Card size="sm" className="relative w-full max-w-[360px] cursor-pointer transition-shadow hover:ring-foreground/20 has-[[data-opens]:focus-visible]:ring-2 has-[[data-opens]:focus-visible]:ring-ring">
      <div className="flex items-start gap-3 px-(--card-spacing)">
        <span className={cn("grid size-14 shrink-0 place-items-center rounded-2xl", program.on ? "bg-primary/12 text-primary" : "bg-muted text-muted-foreground")}>
          <Icon aria-hidden className="size-6" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <button data-opens onClick={onOpen} aria-label={`${title}: see how it works`}
                    className="flex min-w-0 items-center gap-1.5 text-left font-mono text-sm leading-snug font-medium outline-none after:absolute after:inset-0 after:rounded-xl after:content-['']">
              <span className="truncate">{title}</span>
              {program.kind === "code" && <Code className="size-3.5 shrink-0 text-muted-foreground" aria-label="built in, read only" />}
            </button>
            <Switch checked={program.on} onCheckedChange={onSwitch} aria-label={`${title} on`} className="relative z-10 shrink-0" />
          </div>
          <p className="mt-1.5 line-clamp-2 min-h-[2lh] text-sm text-muted-foreground">{about}</p>
        </div>
      </div>
      <div className="relative z-10 flex min-h-5 flex-wrap items-center gap-1.5 px-(--card-spacing)">
        {program.tags.slice(0, 3).map((t) => <TagChip key={t} tag={t} on={t === tag} onClick={() => onTag(t)} />)}
        {program.tags.length > 3 && <span title={program.tags.slice(3).map((t) => `#${t}`).join(" ")} className="text-xs text-muted-foreground">…</span>}
      </div>
      <CardFooter className="mt-auto justify-between gap-2 border-t pt-3 text-xs">
        <StateLight program={program} />
        <span className="shrink-0 text-muted-foreground tabular-nums">{program.states.length} {program.states.length === 1 ? "state" : "states"}</span>
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

  if (!running) return <p className="text-sm text-muted-foreground">No program <code className="font-mono">{name}</code>.</p>
  if (!detail || (config && !specs)) return <p className="text-sm text-muted-foreground">{error || "Loading…"}</p>

  const props = { name, specs, detail, reference, change, act, setError, onGo, after: () => (loadDetail(), onLoad()) }

  return (
    <Layout
      main={<>{error && <ErrorDialog message={error} onClose={() => setError("")} />}<ProgramMain {...props} /></>}
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
  const { icon: Icon, title } = friendly(running ?? { ...detail, name })

  const switchOn = async (on: boolean) => {
    const answer = await window.proki.tool("switch_program", { name, on })
    if (answer.error) setError(answer.error)
    after()
  }
  const saveProgram = async (changes: Record<string, unknown>) => {
    const mistake = await change([{ op: "update", kind: "program", data: { name, changes } }])
    if (!mistake && typeof changes.name === "string" && changes.name !== name) onGo({ program: changes.name, state: null })
    return mistake
  }

  return (
    <>
      <div role={specs ? "button" : undefined} onClick={() => specs && setEditing(true)} title={specs ? "Its name, icon, description and tags" : undefined}
           className={cn("flex items-stretch gap-4 rounded-xl border bg-card p-4 shadow-xs", specs && "cursor-pointer hover:ring-1 hover:ring-foreground/20")}>
        <span className={cn("grid size-14 shrink-0 self-center place-items-center rounded-2xl", detail.on ? "bg-primary/12 text-primary" : "bg-muted text-muted-foreground")}>
          <Icon aria-hidden className="size-6" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col justify-center gap-2">
          <p className="line-clamp-2 text-sm">{detail.desc || <span className="text-muted-foreground">No description.</span>}</p>
          {(detail.tags.length > 0 || !specs) && (
            <div className="flex flex-wrap items-center gap-1.5">
              {detail.tags.map((t) => <TagChip key={t} tag={t} />)}
              {!specs && <Code className="size-3.5 shrink-0 text-muted-foreground" aria-label="in code, read only"><title>In code, read only</title></Code>}
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end justify-between" onClick={(e) => e.stopPropagation()}>  {/* the switch as far up as the icons are down: the room above one is the room below the others */}
          <Switch checked={detail.on} onCheckedChange={switchOn} aria-label={`${title} on`} />
          {specs && (
            <div className="-mr-1.5 -mb-1.5 flex items-center">
              {specs.default && specs.changed && (
                <Confirm title={`Reset “${title}”?`} description="Your changes to it go back to how it came." action="Reset"
                         onConfirm={async () => { setError((await revert(name)) ?? ""); act([]) }}>
                  <Button size="icon-sm" variant="ghost" aria-label={`Reset ${title}`} title="Reset"><RotateCcw /></Button>
                </Confirm>
              )}
              <Confirm title={`Delete “${title}”?`} description="The automation and its states are deleted. This can't be undone." action="Delete automation"
                       onConfirm={async () => {
                         const mistake = await change([{ op: "remove", kind: "program", data: { name } }])
                         if (mistake) setError(mistake)
                         else onGo({ program: null, state: null })
                       }}>
                <Button size="icon-sm" variant="ghost" aria-label={`Delete ${title}`} title="Delete"><Trash2 /></Button>
              </Confirm>
            </div>
          )}
        </div>
      </div>
      {editing && specs && (
        <ProgramDialog spec={{ name, title: specs.program.title ?? "", desc: specs.program.desc, icon: specs.program.icon ?? "", tags: specs.program.tags }}
                       known={[...new Set(reference.programs.flatMap((p) => p.tags))]} onSave={saveProgram} onClose={() => setEditing(false)} />
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
              {state === detail.initial && <Badge variant="outline" className="text-[11px]">start</Badge>}
              {detail.on && state === detail.state && <Badge className="text-[11px]">now</Badge>}
              <p className="text-sm">{live.desc || <span className="text-muted-foreground">No description.</span>}</p>
            </div>
          </div>
          {specs && (
            <>
              <Button size="icon-sm" variant="ghost" aria-label={`Edit the state ${humane(state)}`} title="Edit" onClick={() => setEditing(true)}><Pencil /></Button>
              <Confirm title={`Delete the state “${humane(state)}”?`} description="It, its actions and its transitions are deleted. This can't be undone." action="Delete state"
                       onConfirm={async () => {
                         const mistake = await change([{ op: "remove", kind: "state", data: { program: name, name: state } }])
                         if (mistake) setError(mistake)
                         else onGo({ program: name, state: null })
                       }}>
                <Button size="icon-sm" variant="ghost" aria-label={`Delete the state ${humane(state)}`} title="Delete"><Trash2 /></Button>
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
                         <Tinted icon={Icon} tint={tint} />
                         <span className="w-12 shrink-0 font-medium">{said}</span>
                         {a.desc ? <span className="truncate text-muted-foreground">{a.desc}</span> : <Expr className="truncate">{text}</Expr>}
                       </>
                     )
                   }}
                   form={(a, onSave, onCancel, onDirty) => <ActionForm spec={a} at={at} taken={actions.filter((b) => b !== a).map((b) => b.name)} onSave={onSave} onCancel={onCancel} onDirty={onDirty} />}
                   seen={(a, how) => <ActionSeen spec={a} at={at} {...how} />} />
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
 * go there). What doesn't hold is greyed; `alone`, the state's only one, with no conditions: always. */
function Way({ branch, live, alone, onGo }: { branch: BranchSpec; live?: ProgramDetail["states"][number]["next"][number]; alone?: boolean; onGo: (state: string) => void }) {
  return (
    <>
      <span className="grid min-w-0 flex-1 grid-cols-[0.875rem_minmax(0,10rem)_minmax(0,1fr)] items-center gap-x-2 gap-y-1 pl-1">
        {branch.desc && <span className="col-span-2 col-start-2 text-foreground">{branch.desc}</span>}
        {branch.when.length === 0 && <span className="col-start-2 text-muted-foreground">{alone ? "always" : "else"}</span>}
        {branch.when.map((w) => {
          const rule  = live?.rules.find((r) => r.name === w)
          const holds = rule ? (rule.chance == null ? null : rule.chance >= 0.5) : live?.conds.find((c) => c.expr === w)?.value
          return (
            <span key={w} className={cn("contents", holds !== true && "text-muted-foreground")}>
              <Truth value={holds} />
              <Expr className="truncate" title={w}>{w}</Expr>
              <span className="min-w-0 text-muted-foreground">{rule?.desc}</span>
            </span>
          )
        })}
      </span>
      <span className="flex w-28 shrink-0">
        <button type="button" onClick={(e) => (e.stopPropagation(), onGo(branch.goto))} aria-label={`Go to the state ${humane(branch.goto)}`}
                className="flex min-h-6 min-w-0 items-center gap-1 rounded-full border bg-background px-2 text-xs hover:border-foreground/30 hover:bg-muted">
          <ArrowRight aria-hidden className="size-3 shrink-0" /><span className="truncate font-mono">{humane(branch.goto)}</span>
        </button>
      </span>
    </>
  )
}

/** A state's actions or transitions: in order, each carried by its grip, edited or deleted, and
 * one added last. A drop kept shows at once; one refused springs back, and says why. `before`:
 * what's changed first, for what's saved. */
function Ordered<T extends ActionSpec | BranchSpec>({ title, empty, kind, at, items, line, form, seen, before, change, act }: {
  title: string
  empty: string
  kind: "action" | "branch"
  at: { program: string; state: string }
  items: T[]
  line: (item: T, index: number) => ReactNode
  form: (item: T | undefined, onSave: Save, onCancel: () => void, onDirty?: () => void) => ReactNode
  seen?: (item: T, how: { update: (changes: Record<string, unknown>) => Promise<string | null>; remove: () => void; form: ReactNode; close: () => void }) => ReactNode  // a click opens it over, instead of a form in place
  before?: (data: Record<string, unknown>) => Change[]
  change: Apply
  act: (changes: Change[]) => void
}) {
  const [open, setOpen] = useState<number | "new" | null>(null)
  const [viewing, setViewing] = useState<number | null>(null)
  const [leaving, setLeaving] = useState(false)  // asked whether to drop what's been set up
  const dirty = useRef(false)
  const close = () => setOpen(null)
  const saved = (data: Record<string, unknown>, changes: Change[]) => async () => {
    const mistake = await change([...(before?.(data) ?? []), ...changes])
    if (!mistake) close()
    return mistake
  }
  const sensors = useDrag()
  const [order, setOrder] = useState<number[] | null>(null)  // a drop, shown until the list comes back with it
  const [refused, setRefused] = useState<{ at: number; why: string } | null>(null)
  const [lit, setLit] = useState<number | null>(null)  // the one a dialog's chip came to
  useEffect(() => {
    const take = () => {
      const f = bus.flashing
      if (!f || f.kind !== kind || f.program !== at.program || f.state !== at.state) return
      bus.flashing = null
      setLit(f.at)
      setTimeout(() => setLit(null), 2400)
    }
    take()
    window.addEventListener(FLASH, take)
    return () => window.removeEventListener(FLASH, take)
  }, [kind, at.program, at.state])
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
    <Block title={title} add={open === "new" ? undefined : () => (dirty.current = false, setOpen("new"))}>
      {items.length === 0 && open !== "new" && <p className="text-xs text-muted-foreground">{empty}</p>}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={dropped}>
        <SortableContext items={shown.map((i) => i + 1)} strategy={verticalListSortingStrategy}>
          {shown.map((i) => open === i ? (
            <div key={i}>{form(items[i], (data) => saved(data, [{ op: "update", kind, data: { ...at, at: i, changes: data } }])(), close)}</div>
          ) : (
            <Line key={i} id={i} refused={refused?.at === i} lit={lit === i} named={kind === "action" ? `the action “${(items[i] as ActionSpec).name}”` : `transition ${i + 1}`}
                  plain={!!seen} onEdit={() => seen ? setViewing(i) : setOpen(i)} onDelete={() => act([{ op: "remove", kind, data: { ...at, at: i } }])}>
              {line(items[i], i)}
            </Line>
          ))}
        </SortableContext>
      </DndContext>
      {refused && <ErrorDialog message={`Not moved: ${refused.why}`} onClose={() => setRefused(null)} />}
      {seen && viewing !== null && items[viewing] && seen(items[viewing], {
        update: (changes) => change([{ op: "update", kind, data: { ...at, at: viewing, changes } }]),
        remove: () => (act([{ op: "remove", kind, data: { ...at, at: viewing } }]), setViewing(null)),
        form: form(items[viewing], (data) => change([{ op: "update", kind, data: { ...at, at: viewing, changes: data } }]).then((m) => (m || setViewing(null), m)), () => setViewing(null)),
        close: () => setViewing(null),
      })}
      {open === "new" && (() => {
        const leave = () => (dirty.current ? setLeaving(true) : close())  // what's set up isn't dropped unasked
        const made = form(undefined, (data) => saved(data, [{ op: "add", kind, data: { ...at, ...data } }])(), seen ? leave : close, () => void (dirty.current = true))
        return !seen ? made : (  // an action is made in a dialog of its own, as it's changed in one
          <>
            <Dialog open onOpenChange={(o) => !o && leave()}>
              <DialogContent className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg sm:has-[[data-wide]]:max-w-[38.5rem]" onEscapeKeyDown={typing}>
                {made}
              </DialogContent>
            </Dialog>
            <Discard open={leaving} onOpenChange={setLeaving} title="Drop this action?" description="What you've set up isn't saved yet." action="Drop it" onDrop={close} />
          </>
        )
      })()}
    </Block>
  )
}

// --- what a scope can use -------------------------------------------------------------------

/** An action, over the state's dialog: its kind, what it's for, and what it does, each part changed
 * where it is. A kind with more to it (a poke, a question) shows its form here. `update`: sends
 * the changes (the mistake, if any); `form`: the kind's own, for those. */
function ActionSeen({ spec, at, update, remove, form, close }: {
  spec: ActionSpec; at: { program: string; state: string }; update: (changes: Record<string, unknown>) => Promise<string | null>; remove: () => void; form: ReactNode; close: () => void
}) {
  const [said] = ACTIONS[spec.kind] ?? [spec.kind]
  const popup = spec.kind === "poke" || spec.kind === "ask_usr"  // laid out as its popup is, each part changed where it's read
  const [picks, setPicks] = useState<Picks>({ image: [], sound: [] })
  useEffect(() => {
    if (!popup) return
    window.proki.tool("get_picks", { id: spec.id }).then((answer) => !answer.error && setPicks({ image: answer.media.filter((m: { kind: string }) => m.kind === "image").map((m: { key: string }) => m.key),
                                                                                              sound: answer.media.filter((m: { kind: string }) => m.kind === "sound").map((m: { key: string }) => m.key) }))
  }, [spec.id, popup])
  const holds  = (k: string) => k in ACTION_ROWS || k === "ask_llm" || k === "ask_jev"  // its parts are changed where they're read, held with Save
  const inline = popup || holds(spec.kind)  // else the kind's own form, with its own Save
  const [refused, setRefused] = useState("")
  const shown    = (st: Staged) => (st.patch.kind as string | undefined) ?? spec.kind  // the kind, as changed and not kept yet
  const switchTo = async (k: string, st: Staged) => {  // between kinds held with Save: held with the rest until it; else at once
    if (holds(k) && holds(spec.kind)) return (st.put("kind", k, spec.kind), Object.entries(START[k] ?? {}).forEach(([key, v]) => st.put(key, v, spec.params[key])))
    setRefused((await send({ kind: k, params: popup && (k === "poke" || k === "ask_usr") ? cleaned(k, spec.params) : {} })) ?? "")
  }
  const send   = (patch: Record<string, unknown>) => update({ name: spec.name, desc: spec.desc, kind: spec.kind, params: spec.params, ...patch })
  const commit = (patch: Record<string, unknown>) => send({ params: cleaned(spec.kind, { ...spec.params, ...patch }) })
  const keep   = async (patch: Record<string, unknown>) => {  // everything held, at once
    const { desc, picks: picked, kind: to = spec.kind, ...held } = patch as { desc?: string; picks?: Picks; kind?: string }
    const read   = new Map((ACTION_ROWS[to] ?? []).map(([, key, how]) => [key, how]))
    const params = Object.fromEntries(Object.entries(held).map(([key, value]) => [key, !read.has(key) ? value : read.get(key) === "expr" ? parseExpr(value as string) ?? undefined : (value as string).trim() || undefined]))
    const { options } = params
    if (options === "") return "Say where the options come from."
    if (Array.isArray(options) && options.every((o) => !String(o).trim())) return "Add at least one option."
    const mistake = await send({ ...(desc === undefined ? {} : { desc }), kind: to, params: cleaned(to, { ...(to === spec.kind ? spec.params : Object.fromEntries(Object.entries(spec.params).filter(([k]) => ACTION_ROWS[to]?.some(([, key]) => key === k)))), ...params }) })
    if (mistake || !picked) return mistake
    const { image, sound } = picked as Picks
    await window.proki.tool("set_picks", { id: spec.id, keys: [...image, ...sound] })
    setPicks(picked as Picks)
    return null
  }
  return (
    <Dialog open onOpenChange={(open) => !open && close()}>
      <DialogContent className={"max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg sm:has-[[data-wide]]:max-w-[38.5rem]"} onEscapeKeyDown={typing}>
        <Staging reserve={inline} onSave={keep}>
          {(st) => (
            <>
              <DialogHeader>
                <DialogTitle className="pr-24">
                  <Pick label="Kind" value={shown(st)} arrow className="gap-2 text-base"
                        options={Object.entries(ACTIONS).map(([k, [name, Of, on]]) => [k, <><Tinted icon={Of} tint={on} />{name}</>])}
                        onPick={(k) => switchTo(k, st)} />
                </DialogTitle>
                <DialogDescription asChild>
                  <div>
                    {inline ? <Editable label="Description" long placeholder="No description" {...st.field("desc", spec.desc)} />
                            : <Editable label="Description" value={spec.desc} long placeholder="No description" onSave={(t) => send({ desc: t })} />}
                  </div>
                </DialogDescription>
              </DialogHeader>
              <Corner what="action" name={said} onDelete={() => (remove(), close())} />
              {popup ? (
                <PopupFields ask={spec.kind === "ask_usr"} kind={spec.kind} params={spec.params} commit={commit} saved={picks} picks={(st.patch.picks as Picks | undefined) ?? picks}
                             pick={(which, keys) => st.put("picks", { ...((st.patch.picks as Picks | undefined) ?? picks), [which]: keys }, picks)} />
              ) : shown(st) === "ask_llm" || shown(st) === "ask_jev" ? (() => {
                const { desc: _d, picks: _p, kind: _k, ...patch } = st.patch  // what's held of its params, over what's kept
                const params = { ...spec.params, ...patch }
                const put    = (key: string, value: unknown) => st.put(key, value, key === "context" ? { format: contextOf(spec.params.context).format, values: contextOf(spec.params.context).values } : spec.params[key])
                return shown(st) === "ask_llm" ? <AskLlm params={params} put={put} at={at} was={spec.params} /> : <AskJev params={params} put={put} was={spec.params} />
              })() : ACTION_ROWS[shown(st)] ? (
                <ActionRows kind={shown(st)} field={(key, how) => st.field(key, how === "expr" ? exprText(spec.params[key]) : String(spec.params[key] ?? ""))} />
              ) : form}
            </>
          )}
        </Staging>
        {refused && <ErrorDialog message={refused} onClose={() => setRefused("")} />}
      </DialogContent>
    </Dialog>
  )
}
