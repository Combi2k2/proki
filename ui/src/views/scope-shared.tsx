// What the automations' page and the Resources panel share: the kinds of a spec, the events that tell one part another changed, the way to a
// scope from any page, and the small parts both draw.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { useSortable } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Pencil, Plus, Trash2 } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { type Change, type Reference, type RuleSpec, type SignalSpec, type VariableSpec } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { typing } from "@/views/in-place"

export type Path = { program: string | null; state: string | null }

export type Kind = "variable" | "signal" | "rule"

export type Spec = VariableSpec | SignalSpec | RuleSpec

export type Apply = (changes: Change[]) => Promise<string | null>

export type Running = Reference["programs"][number]

export const CHANGED = "proki:changed"  // a change kept: each part showing one reads it again

export const RESOURCE = "proki:resource"  // a resource opened from the panel: the resource dialogs open now close

/** A panel line; its hide button grows out at its end as you point at it. */
export const LINE = "group/line relative flex cursor-pointer items-center gap-2 rounded-md px-1 py-1 text-xs hover:bg-background"

export const takeover = () => window.dispatchEvent(new Event(RESOURCE))

export const GO      = "proki:go"       // the way to a scope, from any page: its detail, the path


/** The automations' page at `path`: there now, or opened there. */
export const goTo = (path: Path) => (bus.arriving = path, window.dispatchEvent(new CustomEvent(GO, { detail: path })))

/** Specs of a part (a program's, or the global scope's: null), and `change`: sent at once,
 * null when kept, else the mistake. */
export function useSpecs<T>(name: string | null, enabled = true, onChanged?: () => void) {
  const [specs, setSpecs] = useState<T | null>(null)
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    if (!enabled) return
    const answer = await window.proki.tool("program_specs", { name })
    if (answer.error) return setError(answer.error)
    setSpecs(answer as T)
  }, [name, enabled])

  useEffect(() => {
    load()
    window.addEventListener(CHANGED, load)
    return () => window.removeEventListener(CHANGED, load)
  }, [load])

  const change: Apply = async (changes) => {
    const answer = await window.proki.tool("apply_changes", { changes })
    if (answer.error) return answer.error
    setError("")
    window.dispatchEvent(new Event(CHANGED))  // this one too
    onChanged?.()
    return null
  }
  const act = async (changes: Change[]) => setError((await change(changes)) ?? "")
  return { specs, error, setError, change, act }
}

// --- global ---------------------------------------------------------------------------------

/** A way into a state with one of its actions or ways out lit, as a chip of a dialog asks. */
type Flash = { program: string; state: string; kind: "action" | "branch"; at: number }

export const bus: { arriving: Path | null; flashing: Flash | null } = { arriving: null, flashing: null }  // where you're going on the automations' page as it opens; the action or way out to light there

export const FLASH = "proki:flash"

/** A program (null: the global scope) back to the default proki ships. */
export async function revert(name: string | null): Promise<string | null> {
  const answer = await window.proki.tool("reset_program", { name })
  return answer.error ?? null
}


/** The one way to add something to a list, in a dialog and in the side panel alike. */
export function AddButton({ onClick, disabled, label = "Add" }: { onClick: () => void; disabled?: boolean; label?: string }) {
  return <Button size="xs" variant="ghost" className="-mr-2 text-muted-foreground" aria-label={label} disabled={disabled} onClick={onClick}><Plus /> Add</Button>
}

export function Block({ title, add, children }: { title: string; add?: () => void; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">{title}</h2>
        {add && <AddButton onClick={add} />}
      </div>
      {children}
    </section>
  )
}

/** A line of a list, carried by its grip: what it says (click it to edit), then its pencil and its
 * bin; `named`, what it is, as its buttons say it; `refused`: shaken, as a drop that wasn't kept;
 * `lit`: flashed, as a dialog's chip comes to it. */
export function Line({ id, named, refused, lit, plain, children, onEdit, onDelete }: {
  id: number; named: string; refused?: boolean; lit?: boolean; plain?: boolean; children: ReactNode; onEdit: () => void; onDelete: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: id + 1 })  // ids from 1: 0 isn't one
  const box = useRef<HTMLDivElement | null>(null)
  useEffect(() => void (lit && box.current?.scrollIntoView({ block: "nearest", behavior: "smooth" })), [lit])
  return (
    <div ref={(el) => void (setNodeRef(el), box.current = el)} style={{ transform: CSS.Translate.toString(transform), transition }}
         className={cn("group flex items-center gap-2 rounded-lg border bg-card py-1.5 pr-3 pl-1 text-xs hover:bg-muted/50",
                       isDragging && "relative z-10 shadow-lg ring-1 ring-foreground/10", refused && "animate-shake ring-2 ring-destructive/50",
                       lit && "animate-[flash_2.4s_ease-out] ring-2 ring-brand/60")}>
      <button {...attributes} {...listeners} aria-label={`Move ${named}`} className="cursor-grab touch-none text-muted-foreground hover:text-foreground">
        <GripVertical className="size-3.5" />
      </button>
      <div className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-left" onClick={onEdit}>{children}</div>
      <div className="flex shrink-0 items-center opacity-0 group-hover:opacity-100 focus-within:opacity-100">
        {!plain && <Button size="icon-sm" variant="ghost" aria-label={`Edit ${named}`} title="Edit" onClick={onEdit}><Pencil /></Button>}
        <Confirm title={`Delete ${named}?`} description="This can't be undone." action="Delete" onConfirm={onDelete}>
          <Button size="icon-sm" variant="ghost" aria-label={`Delete ${named}`} title="Delete"><Trash2 /></Button>
        </Confirm>
      </div>
    </div>
  )
}

/** A row of Linked's, opened over the dialog. */
export function Detail({ title, about, wide, onClose, children }: { title: ReactNode; about?: string; wide?: boolean; onClose: () => void; children?: ReactNode }) {
  return (
    <Dialog open onOpenChange={(to) => !to && onClose()}>
      <DialogContent className={wide ? "sm:max-w-xl" : "sm:max-w-md"}
                     onEscapeKeyDown={typing}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-sm">{title}</DialogTitle>
          {about && <DialogDescription>{about}</DialogDescription>}
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  )
}
