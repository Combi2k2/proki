// Programs as anyone would say them: a title, an icon, what it does for you in a line, each as the
// program says it of itself (an icon by its name).
// What it leaves out is made up: its name said, an icon its tags pick.

import { createElement, type ComponentType } from "react"
import type { LucideProps } from "lucide-react"
import { DynamicIcon, iconNames, type IconName } from "lucide-react/dynamic"

type Icon = ComponentType<LucideProps>
type Known = { title: string; icon: Icon; about: string }

const drawn = new Map<string, Icon>()
/** The icon named `name`, one component for each name. */
function pictured(name: IconName): Icon {
  if (!drawn.has(name)) drawn.set(name, (props: LucideProps) => createElement(DynamicIcon, { ...props, name }))
  return drawn.get(name)!
}

/** A name, said: "call_family" → "Call family". */
export const humane = (name: string) => (name.charAt(0).toUpperCase() + name.slice(1)).replace(/[_.-]+/g, " ")
/** A program's name, as a title: "task_planner" → "Task Planner". */
const titled = (name: string) => name.split(/[_.-]+/).filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")

/** A program, as anyone would say it. */
export function friendly(program: { name: string; title?: string; desc: string; icon?: string; tags: string[] }): Known {
  const named = (iconNames as string[]).includes(program.icon ?? "") ? program.icon as IconName : null
  return { title: program.title || titled(program.name), icon: pictured(named ?? (program.tags.includes("focus") ? "brain" : "circle-help")), about: program.desc }
}

const RESTING = new Set(["idle", "on", "waiting", "watching", "looking", "tracking", "tracked"])

/** A program's light: off, error (given `error`), idle (waiting for its moment) or active (in a state, doing something). */
export const light = (program: { on: boolean; state: string; error?: boolean }): "off" | "idle" | "active" | "error" =>
  (!program.on ? "off" : program.error ? "error" : RESTING.has(program.state) ? "idle" : "active")

/** What a program is doing now, in words, and whether it's busy (not waiting for its moment). */
export function doing(program: { on: boolean; state: string }): { text: string; busy: boolean } {
  if (!program.on) return { text: "Paused", busy: false }
  if (RESTING.has(program.state)) return { text: "Ready, waiting for its moment", busy: false }
  return { text: humane(program.state), busy: true }
}
