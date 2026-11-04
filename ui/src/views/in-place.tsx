// Text changed where it's read: no input box until you click it.

import { useState } from "react"
import { cn } from "@/lib/utils"

const PLAIN = { autoCapitalize: "off", autoCorrect: "off", spellCheck: false } as const  // names and formulas, as typed

/** A dialog's Escape while you're typing in it: the text put back, the dialog left open. */
export const typing = (e: Event) => void (document.activeElement?.matches("input, textarea") && e.preventDefault())

/** Text read as it is; given `onSave`, underlined as you point at it, and clicked (`editing`: from
 * the start), changed where it is: Enter or leaving it saves (the mistake, if any, under it),
 * Escape puts it back. */
export function Editable({ label, value, onSave, code, list, long, placeholder = "–", title, editing, className }: {
  label: string
  value: string
  onSave?: (text: string) => Promise<string | null | undefined>
  code?: boolean
  list?: string     // the names it suggests, as a page's list of them
  long?: boolean    // a few lines, Shift-Enter between them
  placeholder?: string
  title?: string    // why it can't be changed, when it can't
  editing?: boolean
  className?: string
}) {
  const [text, setText]   = useState<string | null>(editing ? value : null)  // null: not being changed
  const [error, setError] = useState("")
  const look = cn("min-w-0 break-words", code && "font-mono", className)
  if (!onSave) return <span title={title} className={cn(look, !value && "text-muted-foreground")}>{value || placeholder}</span>
  const done = async () => {
    if (text === null) return
    if (text === value) return setText(null)
    const mistake = await onSave(text)
    setError(mistake ?? "")
    if (!mistake) setText(null)
  }
  const keys = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) (e.preventDefault(), done())
    if (e.key === "Escape") (e.preventDefault(), e.stopPropagation(), setText(null), setError(""))
  }
  if (text === null) return (
    <button type="button" onClick={() => setText(value)} title="Click to change" aria-label={`${label}: ${value || placeholder}, change`}
            className={cn(look, "max-w-full cursor-text rounded-sm text-left decoration-muted-foreground decoration-dotted underline-offset-4 hover:underline", !value && "text-muted-foreground")}>
      {value || placeholder}
    </button>
  )
  const field = { "aria-label": label, value: text, autoFocus: true, placeholder, onBlur: done, onKeyDown: keys, ...(code && PLAIN),
                  className: cn(look, "w-full border-0 border-b border-ring bg-transparent p-0 outline-none", long && "field-sizing-content resize-none") }
  return (
    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
      {long ? <textarea {...field} onChange={(e) => setText(e.target.value)} />
            : <input {...field} list={list} onChange={(e) => setText(e.target.value)} />}
      {error && <span className="font-sans text-[11px] font-normal break-words text-destructive">{error}</span>}
    </span>
  )
}
