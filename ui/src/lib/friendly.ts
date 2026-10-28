// Programs as anyone would say them: a title, an icon, what it does for you in a line, and the
// part of your day it belongs to, each as the program says it of itself (an icon by its name).
// What it leaves out is made up: its name said, an icon its tags pick.

import { createElement, type ComponentType } from "react"
import type { LucideProps } from "lucide-react"
import { DynamicIcon, iconNames, type IconName } from "lucide-react/dynamic"

export type Area = "focus" | "day" | "tasks" | "notes" | "background"

export const AREAS: { id: Area; title: string; about: string }[] = [
  { id: "focus", title: "Focus", about: "Help staying on what matters" },
  { id: "day", title: "Your day", about: "Gentle rhythms for mornings and evenings" },
  { id: "tasks", title: "Tasks", about: "Picking and tracking what you work on" },
  { id: "notes", title: "Notes", about: "Catching thoughts before they slip away" },
  { id: "background", title: "Behind the scenes", about: "Quiet helpers the others rely on" },
]

export type Icon = ComponentType<LucideProps>
type Known = { title: string; icon: Icon; about: string; area: Area }

const drawn = new Map<string, Icon>()
/** The icon named `name`, one component for each name. */
function pictured(name: IconName): Icon {
  if (!drawn.has(name)) drawn.set(name, (props: LucideProps) => createElement(DynamicIcon, { ...props, name }))
  return drawn.get(name)!
}

const AREA_OF_TAG: Record<string, Area> = {
  focus: "focus", day: "day", background: "background", session: "focus", morning: "day", evening: "day", sleep: "day", habit: "day", habits: "day", workday: "day",
  family: "day", tasks: "tasks", notes: "notes", tracking: "background", time: "background",
}

/** A name, said: "call_family" → "Call family". */
export const humane = (name: string) => (name.charAt(0).toUpperCase() + name.slice(1)).replace(/[_.-]+/g, " ")
/** A program's name, as a title: "task_planner" → "Task Planner". */
export const titled = (name: string) => name.split(/[_.-]+/).filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")

/** A program, as anyone would say it. */
export function friendly(program: { name: string; title?: string; desc: string; icon?: string; tags: string[] }): Known {
  const area  = program.tags.map((t) => AREA_OF_TAG[t]).find(Boolean) ?? "day"
  const named = (iconNames as string[]).includes(program.icon ?? "") ? program.icon as IconName : null
  return { title: program.title || titled(program.name), icon: pictured(named ?? (program.tags.includes("focus") ? "brain" : "circle-help")),
           area, about: program.desc }
}

const RESTING = new Set(["idle", "on", "waiting", "watching", "looking", "tracking", "tracked"])

/** What a program is doing now, in words, and whether it's busy (not waiting for its moment). */
export function doing(program: { on: boolean; state: string }): { text: string; busy: boolean } {
  if (!program.on) return { text: "Paused", busy: false }
  if (RESTING.has(program.state)) return { text: "Ready, waiting for its moment", busy: false }
  return { text: humane(program.state), busy: true }
}
