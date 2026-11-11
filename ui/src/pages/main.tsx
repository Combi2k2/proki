// The main window: everyday views first, then the advanced ones (automations, time reports and every kind of record);
// Help, Settings and Support at the foot. The tray opens it on one of them ("navigate"), the engine on a
// group's card too (#tasks/12), or an automation (#programs/bedtime), and remembers nothing else: each view loads
// what it shows. In its corner, on every view, bubbles, each opening a panel over the window and over the dialogs
// in it: what the automations can use, for the one you're in, else everywhere.
// The first time it opens, the welcome over it (Settings shows it again).

import { Fragment, lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { AppWindow, Blocks, ChartLine, CircleHelp, Image, HeartHandshake, Lightbulb, ListTodo, Settings, Sun, Table2, Workflow, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Welcome } from "@/components/welcome"
import prokiMark from "../assets/logo/proki.svg"
import { GLOBAL, mount, type View, type Where } from "@/lib/proki"
import { recall, remember } from "@/lib/remember"
import { cn } from "@/lib/utils"

// each view loaded when first opened: the charts, graphs and editors only by the views that show them
const AppsView       = lazy(() => import("@/views/apps").then((m)       => ({ default: m.AppsView })))
const ManualView     = lazy(() => import("@/views/manual").then((m)     => ({ default: m.ManualView })))
const MediaView      = lazy(() => import("@/views/media").then((m)      => ({ default: m.MediaView })))
const MetricsView    = lazy(() => import("@/views/metrics").then((m)    => ({ default: m.MetricsView })))
const NotesView      = lazy(() => import("@/views/notes").then((m)      => ({ default: m.NotesView })))
const ProgramsView   = lazy(() => import("@/views/programs").then((m)   => ({ default: m.ProgramsView })))
const Resources      = lazy(() => import("@/views/resources").then((m)  => ({ default: m.Resources })))
const Scope          = lazy(() => import("@/views/programs").then((m)   => ({ default: m.Scope })))
const SettingsView   = lazy(() => import("@/views/settings").then((m)   => ({ default: m.SettingsView })))
const SupportView    = lazy(() => import("@/views/support").then((m)    => ({ default: m.SupportView })))
const TablesView     = lazy(() => import("@/views/tables").then((m)     => ({ default: m.TablesView })))
const TasksView      = lazy(() => import("@/views/tasks").then((m)      => ({ default: m.TasksView })))
const TodayView      = lazy(() => import("@/views/today").then((m)      => ({ default: m.TodayView })))

type Entry = { view: View; title: string; icon: typeof Sun; tint: string }  // tint: its icon's colour
const SECTIONS: { head?: string; items: Entry[] }[] = [
  { items: [
    { view: "today",    title: "Today",       icon: Sun,       tint: "text-orange-500 dark:text-orange-400" },
    { view: "tasks",    title: "Tasks",       icon: ListTodo,  tint: "text-blue-600 dark:text-blue-400" },
    { view: "notes",    title: "Notes",       icon: Lightbulb, tint: "text-yellow-500 dark:text-yellow-300" },
    { view: "media",    title: "Media",       icon: Image,     tint: "text-pink-500 dark:text-pink-400" },
  ] },
  { head: "Insight", items: [
    { view: "apps",     title: "Apps",        icon: AppWindow, tint: "text-violet-600 dark:text-violet-400" },
    { view: "metrics",  title: "Metrics",     icon: ChartLine, tint: "text-cyan-600 dark:text-cyan-400" },
  ] },
  { head: "Advanced", items: [
    { view: "programs", title: "Automations", icon: Workflow,  tint: "text-emerald-600 dark:text-emerald-400" },
    { view: "tables",   title: "Tables",      icon: Table2,    tint: "text-indigo-500 dark:text-indigo-400" },
  ] },
]
const LAST: Entry[] = [  // at the sidebar's foot
  { view: "manual",     title: "Help",       icon: CircleHelp,     tint: "text-sky-500 dark:text-sky-400" },
  { view: "settings",   title: "Settings",   icon: Settings,       tint: "text-zinc-500 dark:text-zinc-400" },
  { view: "support",    title: "Support",    icon: HeartHandshake, tint: "text-rose-500 dark:text-rose-400" },
]

/** A view's button in the sidebar: its icon and title (only its icon, narrow). */
function Item({ view: v, title, icon: Icon, tint, at, onGo }: Entry & { at: View; onGo: (to: View) => void }) {
  return (
    <Button
      onClick={() => onGo(v)}
      variant={at === v ? "secondary" : "ghost"}
      title={title}
      aria-label={title}
      className={cn("h-8 w-full justify-start gap-2.5 px-2.5 text-left font-normal [-webkit-app-region:no-drag] max-[760px]:size-9 max-[760px]:justify-center max-[760px]:p-0 max-[760px]:has-data-[icon=inline-start]:p-0",
                    at === v ? "font-medium" : "text-muted-foreground hover:text-foreground")}
      aria-current={at === v ? "page" : undefined}
    >
      <Icon data-icon="inline-start" className={tint} />
      <span className="max-[760px]:hidden">{title}</span>
    </Button>
  )
}

type Bubble = { id: string; title: string; icon: typeof Sun; about: ReactNode; panel: ReactNode }  // about: under its title

/** The bubbles at the window's corner, each opening its panel above them, over the window and its
 * dialogs (a dialog open leaves it in reach: it stays lit, and clicking it doesn't close the dialog): one open at a time, none when the app opens. Escape in it closes it. */
function Bubbles({ bubbles }: { bubbles: Bubble[] }) {
  const [open, setOpen] = useState<string | null>(null)
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({})
  const it      = bubbles.find((b) => b.id === open)
  useEffect(() => {  // gone to a place in an automation: shut, to show it
    const shut = () => setOpen(null)
    window.addEventListener("proki:flash", shut)
    return () => window.removeEventListener("proki:flash", shut)
  }, [])
  useEffect(() => {  // a dialog open makes room for it
    if (!it) return
    document.documentElement.dataset.bubble = it.id
    return () => void delete document.documentElement.dataset.bubble
  }, [it?.id])
  return createPortal(<>
    <div data-bubble-panel className="pointer-events-auto fixed right-4 bottom-4 z-[60] flex items-center gap-2">
      {bubbles.map(({ id, title, icon: Icon }) => (
        <button key={id} ref={(b) => void (buttons.current[id] = b)} onClick={() => setOpen(open === id ? null : id)}
                aria-label={title} title={title} aria-expanded={open === id} aria-controls={`bubble-${id}`}
                className="grid size-11 place-items-center rounded-full border bg-background text-muted-foreground shadow-lg transition-[scale,background-color,color] duration-150 ease-out hover:bg-muted hover:text-foreground active:scale-[0.96] aria-expanded:bg-foreground aria-expanded:text-background">
          <Icon aria-hidden className="size-5" />
        </button>
      ))}
    </div>
    {it && (
      <section id={`bubble-${it.id}`} data-bubble-panel aria-labelledby={`bubble-${it.id}-title`} tabIndex={-1}
               onWheel={(e) => e.stopPropagation()}  // a dialog over the window locks its scroll; this panel stays in reach
               onKeyDown={(e) => e.key === "Escape" && !e.defaultPrevented && (e.preventDefault(), setOpen(null), buttons.current[it.id]?.focus())}
               className="pointer-events-auto fixed right-4 bottom-[4.5rem] z-[60] flex h-[min(38rem,calc(100dvh-6rem))] w-[min(23rem,calc(100vw-2rem))] origin-bottom-right flex-col overflow-hidden rounded-2xl border bg-background shadow-2xl outline-none motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-[0.96] motion-safe:duration-200">
        <header className="flex items-center gap-1 border-b py-2.5 pr-2 pl-4">
          <div className="min-w-0 flex-1">
            <h2 id={`bubble-${it.id}-title`} className="text-sm font-medium">{it.title}</h2>
            <p className="truncate text-xs text-muted-foreground">{it.about}</p>
          </div>
          <Button size="icon-sm" variant="ghost" aria-label={`Close ${it.title.toLowerCase()}`} title="Close (Esc)" onClick={() => setOpen(null)}><X /></Button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-color:var(--border)_transparent] [scrollbar-width:thin]">{it.panel}</div>
      </section>
    )}
  </>, document.body)
}

/** What a view opens at: a group's card (a number), or an automation (its name). */
const opening = (card?: string) => (!card ? null : /^\d+$/.test(card) ? Number(card) : card)

function Main() {
  const [first, card] = location.hash.slice(1).split("/")  // the page it opens at, by its path: its view, then what in it
  const [view, setView] = useState<View>((first as View) || "today")
  const [opened, setOpened] = useState<number | string | null>(opening(card))  // a card, or an automation, to open
  const [where, setWhere] = useState<Where>(GLOBAL)
  const [welcome, setWelcome] = useState(() => recall("proki-welcomed", ["yes", "no"] as const, "no") === "no")  // the welcome, not seen through yet
  useEffect(() => void import("@/views/known").then((m) => m.keepLearning()), [])
  useEffect(() => {
    window.proki.onNavigate((path) => {
      const [to, card] = path.split("/")
      setView(to as View)
      setOpened(opening(card))
    })
  }, [])
  const go = (to: View, card: number | string | null = null) => (setView(to), setOpened(card))
  const at = useRef(view)
  at.current = view
  useEffect(() => {  // an automation's scope gone to from another page: the automations, opened there
    const heard = (e: Event) => at.current !== "programs" && go("programs", (e as CustomEvent<{ program: string | null }>).detail.program)
    window.addEventListener("proki:go", heard)
    return () => window.removeEventListener("proki:go", heard)
  }, [])
  useEffect(() => {  // your suggestions waiting, sent: now, when you're back online, and every ten minutes
    const send = () => void window.proki.tool("send_suggestions")
    send()
    const every = setInterval(send, 600_000)
    window.addEventListener("online", send)
    return () => (clearInterval(every), window.removeEventListener("online", send))
  }, [])
  const scope = view === "programs" ? where : GLOBAL  // what the automations can use, where you are; out of them, everywhere
  const bubbles: Bubble[] = [
    { id: "resources", title: "Resources", icon: Blocks, about: <Suspense><Scope where={scope} /></Suspense>, panel: <Suspense><Resources where={scope} /></Suspense> },
  ]

  return (
    <div className="proki-frame flex h-screen gap-0 bg-muted p-2">
      <nav aria-label="Main navigation" data-tauri-drag-region className="proki-sidebar mr-2 flex w-[228px] shrink-0 flex-col gap-1 rounded-[14px] border border-black/[0.07] px-2.5 pt-10 pb-2.5 dark:border-white/[0.06] [-webkit-app-region:drag] max-[760px]:w-[58px] max-[760px]:items-center max-[760px]:px-1.5">
        <div className="mb-6 flex items-center gap-2.5 px-2.5 text-[15px] font-semibold tracking-[-0.03em] max-[760px]:px-0">
          <img src={prokiMark} alt="" className="size-[22px] dark:invert" />
          <span className="max-[760px]:hidden">Proki</span>
        </div>
        {SECTIONS.map(({ head, items }) => (
          <Fragment key={head ?? ""}>
            {head && <p className="mt-6 mb-1 px-2.5 text-xs text-muted-foreground max-[760px]:hidden">{head}</p>}
            {head && <div aria-hidden className="my-3 h-px w-6 bg-border min-[760px]:hidden" />}
            {items.map((item) => <Item key={item.view} {...item} at={view} onGo={go} />)}
          </Fragment>
        ))}
        <div className="mt-auto flex w-full flex-col gap-1 max-[760px]:items-center">
          {LAST.map((item) => <Item key={item.view} {...item} at={view} onGo={go} />)}
        </div>
      </nav>
      <div className={cn("proki-sheet relative min-w-0 flex-1 rounded-[14px] border border-black/[0.07] bg-background", view === "programs" || view === "tasks" || view === "today" || view === "tables" ? "overflow-hidden" : "overflow-y-auto")}>
        <Suspense>
        {view === "today" && <TodayView onGo={(to, card) => go(to, card ?? null)} />}
        {view === "tasks" && <TasksView open={typeof opened === "number" ? opened : null} onOpen={setOpened} />}
        {view === "notes" && <NotesView onGo={(to, card) => go(to, card ?? null)} />}
        {view === "apps" && <AppsView />}
        {view === "metrics" && <MetricsView />}
        {view === "programs" && <ProgramsView key={String(opened)} open={typeof opened === "string" ? opened : null} onWhere={setWhere} />}
        {view === "media" && <MediaView />}
        {view === "tables" && <TablesView />}
        {view === "manual" && <ManualView onGo={go} />}
        {view === "support" && <SupportView />}
        {view === "settings" && <SettingsView onWelcome={() => setWelcome(true)} />}
        </Suspense>
      </div>
      {!welcome && <Bubbles bubbles={bubbles} />}  {/* the welcome over them, none; after it, shut */}
      {welcome && <Welcome onDone={(settings) => {
        setWelcome(false)
        remember("proki-welcomed", "yes")
        if (settings) go("settings")
      }} />}
    </div>
  )
}

mount(<Main />)
