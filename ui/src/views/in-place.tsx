// Text changed where it's read: no input box until you click it.

import { createContext, useContext, useState, type ReactNode } from "react"
import { Check, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { colour, useKnown } from "@/views/code"

const PLAIN = { autoCapitalize: "off", autoCorrect: "off", spellCheck: false } as const  // names and formulas, as typed

/** A dialog's Escape while you're typing in it: the text put back, the dialog left open. */
export const typing = (e: Event) => void (document.activeElement?.matches("input, textarea") && e.preventDefault())

/** Text read as it is; given `onSave`, underlined as you point at it, and clicked (`editing`: from
 * the start), changed where it is: Enter or leaving it saves (the mistake, if any, under it),
 * Escape puts it back. */
export function Editable({ label, value, onSave, code, list, long, placeholder = "–", title, editing, changed, className }: {
  label: string
  value: string
  onSave?: (text: string) => Promise<string | null | undefined>
  code?: boolean
  list?: string     // the names it suggests, as a page's list of them
  long?: boolean    // a few lines, Shift-Enter between them
  placeholder?: string
  title?: string    // why it can't be changed, when it can't
  editing?: boolean
  changed?: boolean // changed in a dialog, not kept yet
  className?: string
}) {
  useKnown()
  const [text, setText]   = useState<string | null>(editing ? value : null)  // null: not being changed
  const [error, setError] = useState("")
  const look = cn("min-w-0 break-words", code && "font-mono", className)
  const read = !value ? placeholder : code ? colour(value) : value
  if (!onSave) return <span title={title} className={cn(look, !value && "text-muted-foreground")}>{read}</span>
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
            className={cn(look, "max-w-full cursor-text rounded-sm text-left decoration-muted-foreground decoration-dotted underline-offset-4 hover:underline", !value && "text-muted-foreground", changed && CHANGED)}>
      {read}
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

/** The look of what's been changed and not kept yet: a blue line under it (a field with a line of its
 * own: that line, blue). A row added is light green; one taken out leaves a red arrow where it was. */
export const CHANGED      = "underline decoration-solid decoration-changed decoration-2 underline-offset-4"
export const CHANGED_LINE = "border-solid border-changed hover:border-solid hover:border-changed focus:border-changed focus-visible:border-changed"

/** What a dialog's edits have changed, held until Save: each by its field, the value it would have. */
export type Staged = {
  patch: Record<string, unknown>
  put: (key: string, value: unknown, was: unknown) => void  // a value back to `was` is no change
  lit: (key: string) => boolean                             // changed, not kept yet
  field: (key: string, was: string, on?: boolean) => { value: string; changed?: boolean; onSave?: (text: string) => Promise<null> }  // an Editable's props
}
const Stage = createContext<Staged | null>(null)
export const useStaged = () => useContext(Stage)

/** Around a dialog's parts: what's changed in them is held, marked, and kept on Save or dropped on
 * Cancel, both at the bottom, shown once something's changed (`reserve`: never, when nothing in it can
 * change). `onSave`: the changes together (the mistake, if any). `children` may take what's held. */
export function Staging({ onSave, reserve = true, onCancel, children }: {
  onSave: (patch: Record<string, unknown>) => Promise<string | null>
  reserve?: boolean
  onCancel?: () => void  // something new: its bar is always there, and Cancel leaves
  children: ReactNode | ((staged: Staged) => ReactNode)
}) {
  const [patch, setPatch] = useState<Record<string, unknown>>({})
  const [error, setError] = useState("")
  const put = (key: string, value: unknown, was: unknown) => {
    setError("")
    setPatch((now) => {
      const { [key]: _, ...rest } = now
      return JSON.stringify(value) === JSON.stringify(was) ? rest : { ...rest, [key]: value }
    })
  }
  const keep = async () => {
    const mistake = await onSave(patch)
    setError(mistake ?? "")
    if (!mistake) setPatch({})
  }
  const staged: Staged = {
    patch, put, lit: (key) => key in patch,
    field: (key, was, on = true) => !on ? { value: was } : {
      value: (patch[key] as string | undefined) ?? was, changed: key in patch,
      onSave: async (text) => (put(key, text, was), null),
    },
  }
  const dirty = Object.keys(patch).length > 0
  return (
    <Stage.Provider value={staged}>
      {typeof children === "function" ? children(staged) : children}
      {reserve && (dirty || onCancel || error) && (  // there only once there's something to keep: the dialog grows to hold it
        <div className="sticky -bottom-4 z-10 -mx-4 -mb-4 flex flex-col gap-1.5 bg-popover px-4 pt-2 pb-4">
          {error && <span className="text-xs break-words text-destructive">{error}</span>}
          <div className="flex justify-end gap-2">
            <Button type="button" size="sm" variant="ghost" onClick={() => (onCancel ? onCancel() : (setPatch({}), setError("")))}>Cancel</Button>
            <Button type="button" size="sm" onClick={keep}>Save</Button>
          </div>
        </div>
      )}
    </Stage.Provider>
  )
}

/** A value picked from a list: read as it is, with an arrow as you point at it; clicked, the list opens
 * and a choice is `onPick`ed. `changed`: lit, not kept yet. `children`: how the value reads (its label,
 * else). No `onPick`: read only. */
export function Pick({ label, value, options, onPick, changed, className, children }: {
  label: string
  value: string
  options: [string, ReactNode][]  // each value, and how it reads
  onPick?: (value: string) => void
  changed?: boolean
  className?: string
  children?: ReactNode
}) {
  const [open, setOpen] = useState(false)
  const shown = children ?? options.find(([v]) => v === value)?.[1] ?? value
  if (!onPick) return <span className={cn("inline-flex items-center gap-1.5", className)}>{shown}</span>
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button type="button" aria-label={`${label}: ${value}, change`}
                className={cn("group/pick inline-flex max-w-full min-w-0 cursor-pointer items-center gap-1 rounded-sm text-left decoration-muted-foreground decoration-dotted underline-offset-4 hover:underline", changed && CHANGED, className)}>
          <span className="inline-flex min-w-0 items-center gap-1.5">{shown}</span>
          <ChevronDown aria-hidden className="size-3.5 shrink-0 text-muted-foreground opacity-0 group-hover/pick:opacity-100 group-data-[state=open]/pick:opacity-100" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto min-w-36 gap-0 p-1">
        {options.map(([v, text]) => (
          <button key={v} type="button" onClick={() => (setOpen(false), v !== value && onPick(v))}
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs hover:bg-muted">
            <span className="inline-flex min-w-0 flex-1 items-center gap-1.5">{text}</span>
            {v === value && <Check aria-hidden className="size-3.5 text-muted-foreground" />}
          </button>
        ))}
      </PopoverContent>
    </Popover>
  )
}

/** The name of a row in a dialog's list of them, a column of its own; what it is on hover. */
export const Term = ({ children, hint }: { children: ReactNode; hint?: string }) => <dt title={hint} className="text-muted-foreground">{children}</dt>
