// The main window: everyday views first, then the advanced ones (automations, time reports and every kind of record);
// Help, Settings and Contribute at the foot. The tray opens it on one of them ("navigate"), the engine on a
// group's card too (#tasks/12), or an automation (#programs/bedtime), and remembers nothing else: each view loads
// what it shows. At its right edge, on every view, a drawer: what the automations can use, for the one you're in.

import { Fragment, useEffect, useState } from "react"
import { AppWindow, ChartLine, CircleHelp, Image, HeartHandshake, Lightbulb, ListTodo, PanelRightClose, PanelRightOpen, Settings, Sun, Table2, Workflow } from "lucide-react"
import { Button } from "@/components/ui/button"
import prokiMark from "../../logo/proki.svg"
import { mount, type View } from "@/lib/proki"
import { recall, remember } from "@/lib/remember"
import { cn } from "@/lib/utils"
import { AppsView } from "@/views/apps"
import { ContributeView } from "@/views/contribute"
import { ManualView } from "@/views/manual"
import { MediaView } from "@/views/media"
import { MetricsView } from "@/views/metrics"
import { NotesView } from "@/views/notes"
import { friendly } from "@/lib/friendly"
import { GLOBAL, ProgramsView, Resources, type Where } from "@/views/programs"
import { SettingsView } from "@/views/settings"
import { TablesView } from "@/views/tables"
import { TasksView } from "@/views/tasks"
import { TodayView } from "@/views/today"

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
  { view: "contribute", title: "Contribute", icon: HeartHandshake, tint: "text-rose-500 dark:text-rose-400" },
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

/** What the automations can use, at the window's edge: for the scope you're in, in the editor,
 * else the global one's. Shut, a handle to open it; kept as you left it. */
function Drawer({ where, open, onOpen }: { where: Where; open: boolean; onOpen: (open: boolean) => void }) {
  const [names, setNames] = useState<Record<string, string>>({})
  useEffect(() => {
    if (open) window.proki.tool("reference").then((r) => !r.error && setNames(Object.fromEntries(r.programs.map((p) => [p.name, friendly(p).title]))))
  }, [open])
  if (!open) return (
    <Button size="icon-sm" variant="ghost" onClick={() => onOpen(true)} aria-label="Show what automations can use" title="Signals, variables, rules and inputs"
            className="absolute top-3 right-3 z-10 text-muted-foreground [-webkit-app-region:no-drag]">
      <PanelRightOpen />
    </Button>
  )
  const at = where.program === null ? "Everywhere" : [names[where.program] ?? where.program, where.state].filter(Boolean).join(" › ")
  return (
    <aside aria-label="What automations can use" className="ml-2 flex w-[20rem] shrink-0 flex-col rounded-[14px] border border-black/[0.07] bg-background motion-safe:animate-in motion-safe:slide-in-from-right-4 motion-safe:fade-in-0 max-[900px]:w-[16rem]">
      <header className="flex items-center gap-2 border-b px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-medium">What automations use</h2>
          <p className="truncate text-xs text-muted-foreground">{at}</p>
        </div>
        <Button size="icon-sm" variant="ghost" aria-label="Hide" onClick={() => onOpen(false)}><PanelRightClose /></Button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain [scrollbar-color:var(--border)_transparent] [scrollbar-width:thin]">
        <Resources where={where} />
      </div>
    </aside>
  )
}

/** What a view opens at: a group's card (a number), or an automation (its name). */
const opening = (card?: string) => (!card ? null : /^\d+$/.test(card) ? Number(card) : card)

function Main() {
  const [first, card] = location.hash.slice(1).split("/")  // the page it opens at, by its path: its view, then what in it
  const [view, setView] = useState<View>((first as View) || "today")
  const [appearance, setAppearance] = useState(() => recall("proki-appearance", ["system", "light", "dark"] as const, "dark"))
  const [opened, setOpened] = useState<number | string | null>(opening(card))  // a card, or an automation, to open
  const [where, setWhere] = useState<Where>(GLOBAL)
  const [drawer, setDrawer] = useState(() => recall("proki-drawer", ["open", "shut"] as const, "shut") === "open")
  useEffect(() => {
    window.proki.onNavigate((path) => {
      const [to, card] = path.split("/")
      setView(to as View)
      setOpened(opening(card))
    })
  }, [])
  const go = (to: View, card: number | string | null = null) => {
    setView(to)
    setOpened(card)
    if (to !== "programs") setWhere(GLOBAL)
  }
  useEffect(() => {  // your suggestions waiting, sent: now, when you're back online, and every ten minutes
    const send = () => void window.proki.tool("send_suggestions")
    send()
    const every = setInterval(send, 600_000)
    window.addEventListener("online", send)
    return () => (clearInterval(every), window.removeEventListener("online", send))
  }, [])
  const keep = (open: boolean) => (setDrawer(open), remember("proki-drawer", open ? "open" : "shut"))

  useEffect(() => {
    const root = document.documentElement
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () => root.classList.toggle("dark", appearance === "dark" || (appearance === "system" && systemDark.matches))
    apply()
    systemDark.addEventListener("change", apply)
    return () => systemDark.removeEventListener("change", apply)
  }, [appearance])

  return (
    <div className="proki-frame flex h-screen gap-0 bg-muted p-2">
      <nav aria-label="Main navigation" data-tauri-drag-region className="proki-sidebar mr-2 flex w-[228px] shrink-0 flex-col gap-1 rounded-[14px] border border-black/[0.07] px-2.5 pt-10 pb-2.5 dark:border-white/[0.06] [-webkit-app-region:drag] max-[760px]:w-[58px] max-[760px]:items-center max-[760px]:px-1.5">
        <div className="mb-6 flex items-center gap-2.5 px-2.5 text-[15px] font-semibold tracking-[-0.03em] max-[760px]:px-0">
          <img src={prokiMark} alt="" className="size-[22px] dark:invert" />
          <span className="max-[760px]:hidden">proki</span>
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
        {view === "today" && <TodayView onGo={(to, card) => go(to, card ?? null)} />}
        {view === "tasks" && <TasksView open={typeof opened === "number" ? opened : null} onOpen={setOpened} />}
        {view === "notes" && <NotesView onGo={(to, card) => go(to, card ?? null)} />}
        {view === "apps" && <AppsView />}
        {view === "metrics" && <MetricsView />}
        {view === "programs" && <ProgramsView key={String(opened)} open={typeof opened === "string" ? opened : null} onWhere={setWhere} />}
        {view === "media" && <MediaView />}
        {view === "tables" && <TablesView />}
        {view === "manual" && <ManualView onGo={go} />}
        {view === "contribute" && <ContributeView />}
        {view === "settings" && <SettingsView appearance={appearance} onAppearance={(value) => { setAppearance(value); remember("proki-appearance", value) }} />}
        {!drawer && view === "programs" && <Drawer where={where} open={false} onOpen={keep} />}
      </div>
      {drawer && view === "programs" && <Drawer where={where} open onOpen={keep} />}
    </div>
  )
}

mount(<Main />)
