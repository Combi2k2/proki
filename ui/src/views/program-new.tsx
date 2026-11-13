// A new automation, in a dialog laid out as its card is (and an automation's own, changed there): its icon on the left, its title and what it
// does beside it, its tags under them. Its name is its title said as a word; it starts in "idle".
// Tags are typed with the ones already in use offered, each kept as a chip.

import { useState } from "react"
import { DynamicIcon, type IconName } from "lucide-react/dynamic"
import { Plus, RotateCcw, X } from "lucide-react"
import { ErrorDialog } from "@/components/error-dialog"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"
import { Editable, Staging, typing } from "@/views/in-place"
import { IconPicker } from "@/views/icon-picker"
import type { Save } from "@/views/program-forms"


/** A boxed field, like the search box: what's typed in it is held by the caller; `LABEL` names it above. */
const FIELD = "h-8 text-sm"
const LABEL = "text-xs text-muted-foreground"
const ROOM = "min-h-24"  // a description keeps room for four lines

/** A tag as a grey chip, `#tag`: clicked (given `onClick`) it picks that tag; `on` it is the one picked; `onRemove` adds a ×. `mark`: added (green) or
 * taken out (red, struck through, `onRestore` puts it back) in a dialog, not kept yet. */
export function TagChip({ tag, on, mark, onClick, onRemove, onRestore }: { tag: string; on?: boolean; mark?: "added" | "removed"; onClick?: () => void; onRemove?: () => void; onRestore?: () => void }) {
  const look = cn("inline-flex h-5 items-center gap-1 rounded-md px-1.5 font-mono text-xs whitespace-nowrap select-none",
                  mark === "added" ? "bg-added/20 text-foreground ring-1 ring-added/50" : mark === "removed" ? "bg-removed/15 text-muted-foreground line-through" : "bg-muted text-muted-foreground",
                  on && "text-foreground ring-1 ring-foreground/30")
  return (
    <span className={look}>
      {onClick ? <button type="button" aria-pressed={on} onClick={onClick}>#{tag}</button> : <>#{tag}</>}
      {onRemove && <button type="button" aria-label={`Remove ${tag}`} onClick={onRemove} className="-mr-0.5 rounded p-0.5 opacity-60 hover:opacity-100"><X className="size-2.5" /></button>}
      {onRestore && <button type="button" aria-label={`Put ${tag} back`} title="Put it back" onClick={onRestore} className="-mr-0.5 rounded p-0.5 no-underline opacity-80 hover:opacity-100"><RotateCcw className="size-2.5" /></button>}
    </span>
  )
}

/** A tag as it's kept: lower case, words joined by dashes ("" if nothing is left). */
const tagged = (text: string) => text.trim().replace(/^#+/, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")

/** A title said as a name: "Stretch breaks" → "stretch_breaks" ("" if nothing is left). */
export const slug = (title: string) => {
  const said = title.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")
  return /^\d/.test(said) ? `p_${said}` : said
}

/** Tags as chips in a row, each with its ×, and a `+ tag` that lists the `known` ones to pick, or finds or makes one by what's typed. `was`: the
 * tags as kept, to mark what's added and what's taken out. */
export function TagsField({ value, known, was, onChange }: { value: string[]; known: string[]; was?: string[]; onChange: (tags: string[]) => void }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState("")
  const typed  = tagged(text)
  const offers = known.filter((t) => !value.includes(t) && (!typed || t.includes(typed))).sort((x, y) => Number(y.startsWith(typed)) - Number(x.startsWith(typed))).slice(0, 8)  // those that begin with it first
  const gone   = (was ?? []).filter((t) => !value.includes(t))
  const add = (tag: string) => {
    const kept = tagged(tag)
    if (kept && !value.includes(kept)) onChange([...value, kept])
    setOpen(false)
  }
  const item = "flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left font-mono text-xs hover:bg-muted"
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {value.map((t) => <TagChip key={t} tag={t} mark={was && !was.includes(t) ? "added" : undefined} onRemove={() => onChange(value.filter((v) => v !== t))} />)}
      {gone.map((t) => <TagChip key={t} tag={t} mark="removed" onRestore={() => onChange([...value, t])} />)}
      <Popover open={open} onOpenChange={(to) => (setOpen(to), setText(""))}>
        <PopoverTrigger asChild>
          <button type="button" aria-label="Add a tag" className="h-5 cursor-pointer rounded-md border border-dashed px-2 text-xs text-muted-foreground hover:bg-muted">+ tag</button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-56 gap-1 p-1">
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder="Find or add a tag" aria-label="Find or add a tag" autoFocus className="h-7 text-xs"
                 onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add(typed || offers[0] || ""))} autoCapitalize="off" autoCorrect="off" spellCheck={false} />
          {offers.map((t) => <button key={t} type="button" onClick={() => add(t)} className={item}>#{t}</button>)}
          {typed && !known.includes(typed) && !value.includes(typed) && <button type="button" onClick={() => add(typed)} className={item}><span className="text-muted-foreground">Add</span> #{typed}</button>}
          {!offers.length && !typed && <p className="px-2 py-1 text-xs text-muted-foreground">Type a tag to add.</p>}
        </PopoverContent>
      </Popover>
    </div>
  )
}

/** The dialog that makes a new automation: `known` the tags already in use; `onCreate` makes it (the mistake, if any). */
export function NewProgram({ known, onCreate, onClose }: { known: string[]; onCreate: Save; onClose: () => void }) {
  const [title, setTitle]     = useState("")
  const [desc, setDesc]       = useState("")
  const [icon, setIcon]       = useState("")
  const [tags, setTags]       = useState<string[]>([])
  const [hint, setHint]       = useState("")   // what's missing, by the field
  const [refused, setRefused] = useState("")   // what the engine said
  const create = async () => {
    const name = slug(title)
    if (!name) return setHint("Give it a title.")
    setHint("")
    setRefused((await onCreate({ name, title: title.trim(), desc: desc.trim(), icon, initial: "idle", tags })) ?? "")
  }
  return (
    <Dialog open onOpenChange={(to) => !to && onClose()}>
      <DialogContent className="sm:max-w-md" onEscapeKeyDown={typing}>
        <DialogHeader className="sr-only">
          <DialogTitle>New automation</DialogTitle>
          <DialogDescription>Its icon, title, what it does and its tags.</DialogDescription>
        </DialogHeader>
        <div className="flex items-end gap-3 pr-8">
          <IconPicker value={icon} onPick={setIcon} label="Choose an icon">
            <button type="button" className={cn("grid size-14 shrink-0 place-items-center rounded-2xl", icon ? "bg-primary/12 text-primary hover:ring-2 hover:ring-primary/30" : "border border-dashed text-muted-foreground hover:bg-muted")}>
              {icon ? <DynamicIcon name={icon as IconName} className="size-6" /> : <Plus aria-hidden className="size-5" />}
            </button>
          </IconPicker>
          <label className="flex min-w-0 flex-1 flex-col gap-1">
            <span className={LABEL}>Display name</span>
            <Input value={title} onChange={(e) => (setTitle(e.target.value), setHint(""))} placeholder="Stretch breaks" autoFocus onKeyDown={(e) => e.key === "Enter" && create()} className={FIELD} />
          </label>
        </div>
        {hint && <p className="-mt-2 text-xs text-destructive">{hint}</p>}
        <label className="flex flex-col gap-1">
          <span className={LABEL}>Description</span>
          <Textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="What does it do for you?" className={cn(ROOM, "resize-none text-sm")} />
        </label>
        <div className="flex flex-col gap-1.5">
          <span className={LABEL}>Tags</span>
          <TagsField value={tags} known={known} onChange={setTags} />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button type="button" size="sm" onClick={create}>Create</Button>
        </div>
      </DialogContent>
      {refused && <ErrorDialog message={refused} onClose={() => setRefused("")} />}
    </Dialog>
  )
}

/** An automation's own dialog: its icon at the left, its display name and its code name on one line, its description under them, its tags;
 * changed where they're read, held and marked until Save. `onSave` gets what changed (the mistake, if any). */
export function ProgramDialog({ spec, known, onSave, onClose }: {
  spec: { name: string; title: string; desc: string; icon: string; tags: string[] }
  known: string[]
  onSave: (changes: Record<string, unknown>) => Promise<string | null>
  onClose: () => void
}) {
  const keep = async (patch: Record<string, unknown>) => {
    const changes = { ...patch }
    for (const key of ["title", "desc"]) if (typeof changes[key] === "string") changes[key] = (changes[key] as string).trim()
    if ("name" in changes) {
      const name = slug(String(changes.name))
      if (!name) return "The code name needs a word."
      changes.name = name
    }
    return onSave(changes)
  }
  const said = spec.title || spec.name
  return (
    <Dialog open onOpenChange={(to) => !to && onClose()}>
      <DialogContent className="sm:max-w-lg" onEscapeKeyDown={typing}>
        <DialogHeader className="sr-only">
          <DialogTitle>{said}</DialogTitle>
          <DialogDescription>Its icon, names, description and tags.</DialogDescription>
        </DialogHeader>
        <Staging onSave={keep} reserve={false}>
          {(st) => {
            const icon = (st.patch.icon as string | undefined) ?? spec.icon
            const tags = (st.patch.tags as string[] | undefined) ?? spec.tags
            return (
              <>
                <div className="flex items-end gap-3 pr-8">
                  <IconPicker value={icon} onPick={(name) => st.put("icon", name, spec.icon)} label="Choose an icon">
                    <button type="button" className={cn("grid size-14 shrink-0 place-items-center rounded-2xl", icon ? "bg-primary/12 text-primary hover:ring-2 hover:ring-primary/30" : "border border-dashed text-muted-foreground hover:bg-muted",
                                                        st.lit("icon") && "ring-2 ring-changed")}>
                      {icon ? <DynamicIcon name={icon as IconName} className="size-6" /> : <Plus aria-hidden className="size-5" />}
                    </button>
                  </IconPicker>
                  <label className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className={LABEL}>Display name</span>
                    <Editable label="Display name" {...st.field("title", spec.title)} placeholder="Untitled" className="text-sm" />
                  </label>
                  <label className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className={LABEL}>Code name</span>
                    <Editable label="Code name" {...st.field("name", spec.name)} className="font-mono text-sm" />
                  </label>
                </div>
                <label className="flex flex-col gap-1">
                  <span className={LABEL}>Description</span>
                  <Editable label="Description" long {...st.field("desc", spec.desc)} placeholder="No description." className="text-sm" />
                </label>
                <div className="flex flex-col gap-1.5">
                  <span className={LABEL}>Tags</span>
                  <TagsField value={tags} known={known} was={spec.tags} onChange={(next) => st.put("tags", next, spec.tags)} />
                </div>
                {st.dirty && (  // there once something's changed: Save and Cancel, at the foot
                  <div className="flex justify-end gap-2 border-t pt-3">
                    <Button type="button" variant="ghost" size="sm" onClick={st.cancel}>Cancel</Button>
                    <Button type="button" size="sm" onClick={st.save}>Save</Button>
                  </div>
                )}
                {st.error && <ErrorDialog message={st.error} onClose={st.dismiss} />}
              </>
            )
          }}
        </Staging>
      </DialogContent>
    </Dialog>
  )
}
