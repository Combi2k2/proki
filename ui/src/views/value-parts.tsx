// What a table of a value is made of: whether a value fits a cell, how a cell says it, the cue that opens a list or a record, and the plain value changed where it's read
// (yes or no as its tick and cross, text or a number typed over).

import { useState } from "react"
import { Check, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { parsed } from "@/views/field-parts"
import { Editable, HELD } from "@/views/in-place"
import { shown } from "@/views/program-inspect"

/** Whether a value fits a cell as it is: not a list, not a record (an empty one says "none"). */
export const atomic = (value: unknown) => value === null || typeof value !== "object" || Object.keys(value).length === 0

/** Whether a value is a list or a record, empty or not (what opens in a table, never typed in). */
export const collection = (value: unknown) => value !== null && typeof value === "object"

export const isRecord = (value: unknown): value is Record<string, unknown> => !atomic(value) && !Array.isArray(value)
export const WRAP = "[overflow-wrap:anywhere]"  // a long word breaks into the next line, never over the next cell

/** A value as a cell says it, as Python writes it: text quoted, True or False, a dash for none. */
export function plain(value: unknown): string {
  if (value !== null && typeof value === "object") return "–"
  if (typeof value === "string") return `"${value}"`
  if (typeof value === "boolean") return value ? "True" : "False"
  return shown(value)
}

/** What a list or a record holds, to open: "3 items", "4 fields". */
export function holds(value: unknown): string {
  if (Array.isArray(value)) return value.length === 1 ? "1 item" : `${value.length} items`
  const n = Object.keys(value as object).length
  return n === 1 ? "1 field" : `${n} fields`
}

/** A cue to open what's too big for a line: […] for a list, {…} for a record, its brackets in its
 * type's colour, the dots as a value's; what it holds on hover. */
export function Opens({ value, onOpen, className }: { value: unknown; onOpen: () => void; className?: string }) {
  const list = Array.isArray(value)
  return (
    <button type="button" title={holds(value)} onClick={(e) => (e.stopPropagation(), onOpen())} style={{ color: `var(--type-${list ? "list" : "object"})` }}
            className={cn(HELD, "inline-flex items-center whitespace-nowrap", className)}>
      {list ? "[" : "{"}{Object.keys(value as object).length > 0 && <span className="text-muted-foreground">…</span>}{list ? "]" : "}"}
    </button>
  )
}

/** Whether something holds: a green tick, a red cross, a dash when it isn't known. */
export function Truth({ value }: { value: unknown }) {
  if (value === true)  return <Check aria-label="true" className="size-3.5 shrink-0 text-added" />
  if (value === false) return <X aria-label="false" className="size-3.5 shrink-0 text-destructive" />
  return <span aria-label="unknown" className="w-3.5 shrink-0 text-center text-muted-foreground">–</span>
}

/** Yes or no, as its mark; clicked, both marks show in a line and a click on one sets it. `changed`: lit, not kept yet. */
export function Flag({ value, onPut, changed, boxed }: { value: unknown; onPut: (value: boolean) => void; changed?: boolean; boxed?: boolean }) {
  const [open, setOpen] = useState(false)
  if (!open) return (
    <button type="button" aria-label={`${value === true ? "true" : value === false ? "false" : "unknown"}, change`} onClick={() => setOpen(true)}
            className={cn("inline-flex min-w-4 cursor-pointer justify-center border-b border-dotted border-transparent pb-px", boxed ? HELD : "hover:border-muted-foreground", changed && "border-solid border-changed border-b-2 hover:border-changed")}>
      <Truth value={value} />
    </button>
  )
  return (
    <span onMouseLeave={() => setOpen(false)} className="inline-flex items-center gap-1">
      {[true, false].map((on) => (
        <button key={String(on)} type="button" aria-pressed={value === on} aria-label={on ? "true" : "false"} onClick={() => (setOpen(false), value !== on && onPut(on))}
                className={cn("rounded-sm p-0.5", value !== on && "opacity-40 hover:opacity-100")}><Truth value={on} /></button>
      ))}
    </span>
  )
}

/** A plain value changed where it's read: text or a number is clicked and typed over (yes or no is picked from its two
 * marks); a change goes to `onPut`. `changed`: lit, not kept yet. */
export function Scalar({ value, string, flag, onPut, changed, editing, boxed }: { value: unknown; string?: boolean; flag?: boolean; onPut: (value: unknown) => Promise<string | null>; changed?: boolean; editing?: boolean; boxed?: boolean }) {
  if (typeof value === "boolean" || flag) return <Flag value={value} changed={changed} boxed={boxed} onPut={(on) => void onPut(on)} />
  const text = value === null || value === undefined ? "" : typeof value === "string" || typeof value === "object" ? JSON.stringify(value) : shown(value)
  const save = async (typed: string) => {
    const was = parsed(typed)
    const sent = typed.trim() === "" ? null : string && typeof was !== "string" ? typed : was
    return collection(sent) ? "One value here: a list or a record opens as a table" : onPut(sent)
  }
  return <Editable label="Value" code value={text} onSave={save} changed={changed} editing={editing} boxed={boxed} className={cn("text-xs whitespace-pre-wrap", WRAP)} />
}
