// The names the app knows, drawn in expressions in the colours the resource panel gives them.

import type { Reference, Type } from "@/lib/proki"
import { knowing } from "@/views/code"
import { kindOf } from "@/views/fields"

const RULE = "var(--color-rose-300)"  // a rule has no type: its own tint, as what reads by a rule

/** The names of a reference, each in its type's colour (a rule's in its own), as they're said in full and as a program says them. */
export function learn(r: Reference) {
  const typed = (t: Type | undefined) => `var(--type-${kindOf(t ?? "any")})`
  const rows: [string, string][] = [
    ...r.inputs.map((i): [string, string] => [i.name, typed(i.type)]),
    ...r.signals.map((s): [string, string] => [s.name, typed(s.type)]),
    ...r.variables.flatMap((v) => [[v.name, typed(v.type)] as [string, string], ...(((v as { fields?: { name: string; type?: Type }[] }).fields ?? []).map((f): [string, string] => [f.name, typed(f.type)]))]),
    ...r.rules.map((x): [string, string] => [x.name, RULE]),
  ]
  const short = rows.filter(([name]) => name.includes(".")).map(([name, colour]): [string, string] => [name.split(".").at(-1)!, colour])
  knowing([...short, ...rows])  // the full ones win over a short one of the same name
}

/** Learn them now, and again as anything changes. */
export function keepLearning() {
  const load = () => void window.proki.tool("reference").then((r) => !r.error && learn(r))
  load()
  window.addEventListener("proki:changed", load)
}
