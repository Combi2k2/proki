// What a program's views share: how a state, a way out and a value read.

import type { BranchDetail } from "@/lib/proki"

/** What's clicked in a diagram: a state, or one of its ways out. */
export type Inspected = { kind: "state"; state: string } | { kind: "way"; state: string; index: number } | null

export const SYMBOL = { gt: ">", ge: "≥", lt: "<", le: "≤", eq: "=", ne: "≠" }

/** A value as it reads best: numbers to 2 places, text in quotes, unknown as a dash. */
export function shown(value: unknown): string {
  if (value === null || value === undefined) return "–"
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2)
  if (typeof value === "string") return JSON.stringify(value)
  if (Array.isArray(value)) return value.length === 1 ? "1 item" : `${value.length} items`
  if (typeof value === "object") return `{${Object.keys(value).join(", ")}}`
  return String(value)
}

export const minutes = (m: number) => (m < 1 ? `${Math.round(m * 60)} s` : `${m % 1 ? m.toFixed(1) : m} min`)
export const isElse = (b: BranchDetail) => b.conds.length === 0 && b.rules.length === 0

/** What a way out's capsule says: its first condition or rule, and how many more. */
export function summary(b: BranchDetail): string {
  if (isElse(b)) return "else"
  const all = [...b.conds.map((c) => c.expr), ...b.rules.map((r) => r.name)]
  return all.length > 1 ? `${all[0]} +${all.length - 1}` : all[0]
}

/** An action's kind and a few words: {"set": {"name": "x", ...}} → "set x". */
export function action(entry: unknown): { kind: string; text: string } {
  if (typeof entry === "string") return { kind: entry.split(" ")[0], text: entry.split(" ").slice(1).join(" ") }
  if (!entry || typeof entry !== "object") return { kind: "?", text: String(entry) }
  const [kind, params] = Object.entries(entry as Record<string, Record<string, unknown>>)[0] ?? ["?", {}]
  const context = params?.context
  const said = typeof context === "string" ? context : (context as { format?: string } | undefined)?.format
  const fields = params?.fields as Record<string, unknown> | undefined
  const text = params?.name !== undefined
    ? `${params.name}${fields ? ` {${Object.keys(fields).join(", ")}}` : params.expr !== undefined ? ` · ${params.expr}` : ""}`
    : said ?? (params?.view as string | undefined) ?? ""
  return { kind, text: params?.when ? `${text} · when ${params.when}` : text }
}
