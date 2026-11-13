// The pieces a group's dialog and a task's are made of: a section, text changed where it is, a list of short texts to add to one at a time, the tags, a box to add a name.

import { useEffect, useRef, useState, type ReactNode } from "react"
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core"
import { SortableContext, arrayMove, horizontalListSortingStrategy, sortableKeyboardCoordinates, useSortable } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { Plus, Trash2, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { NativeSelect, NativeSelectOptGroup, NativeSelectOption } from "@/components/ui/native-select"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import type { Rows } from "@/lib/proki"

// each tag's row: the first it's in
export const rowsOf = (rows: Rows) => Object.fromEntries(Object.entries(rows).reverse().flatMap(([row, tags]) => tags.map((tag) => [tag, row])))
export const lines = (text: string) => text.split("\n").map((line) => line.trim()).filter(Boolean)

// a card is picked up once the pointer's moved a little: a click still opens it
export const useDrag = () => useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
                                        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }))

export function Section({ icon, title, action, children }: { icon: ReactNode; title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className="mb-2 flex items-center gap-3 [&_svg]:size-4 [&_svg]:text-muted-foreground">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
        <span className="ml-auto">{action}</span>
      </div>
      <div className="pl-7">{children}</div>
    </section>
  )
}

/** A group's tags, the most likely first, 3 at most: the first one's row is where its card is. A tag is carried along the line to put it where it goes, taken
 * out with its cross, and brought in from the list, by row. */
export function TagEditor({ tags, rows, onSave }: { tags: string[]; rows: Rows; onSave: (tags: string[]) => void }) {
  const row = rowsOf(rows)
  const sensors = useDrag()
  const dropped = (e: DragEndEvent) => e.over && e.active.id !== e.over.id && onSave(arrayMove(tags, tags.indexOf(String(e.active.id)), tags.indexOf(String(e.over.id))))
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={dropped}>
        <SortableContext items={tags} strategy={horizontalListSortingStrategy}>
          {tags.map((tag, i) => <SortableTag key={tag} tag={tag} first={i === 0} onRemove={() => onSave(tags.filter((t) => t !== tag))} />)}
        </SortableContext>
      </DndContext>
      {tags.length < 3 && (
        <NativeSelect size="sm" value="" className="w-40" onChange={(e) => e.target.value && onSave([...tags, e.target.value])}>
          <NativeSelectOption value="">+ Add a tag</NativeSelectOption>
          {Object.entries(rows).map(([name, inRow]) => (
            <NativeSelectOptGroup key={name} label={name}>
              {inRow.filter((tag) => row[tag] === name && !tags.includes(tag)).map((tag) => <NativeSelectOption key={tag} value={tag}>{tag}</NativeSelectOption>)}
            </NativeSelectOptGroup>
          ))}
        </NativeSelect>
      )}
    </div>
  )
}

/** A tag as a chip that's carried: the first, the most relevant, is filled. */
function SortableTag({ tag, first, onRemove }: { tag: string; first: boolean; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: tag })
  return (
    <Badge ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }} {...attributes} {...listeners} variant={first ? "default" : "secondary"}
           title={first ? "The most relevant: the card is in its row. Drag a tag to put it first." : "Drag to put it where it belongs"}
           className={cn("h-6 cursor-grab touch-none", isDragging && "z-10 opacity-60 shadow-md")}>
      {tag}
      <button aria-label={`Remove ${tag}`} onPointerDown={(e) => e.stopPropagation()} className="-mr-1 rounded-full p-0.5 opacity-60 hover:bg-foreground/10 hover:opacity-100" onClick={onRemove}><X className="size-3" /></button>
    </Badge>
  )
}

/** Short texts, a row each: one changed where it is (Enter or leaving saves), one taken out with its bin, and one added at a time, up to `max`. */
export function ItemList({ items, add, placeholder, max, onSave }: { items: string[]; add: string; placeholder: string; max?: number; onSave: (items: string[]) => void }) {
  return (
    <div className="flex flex-col gap-0.5">
      {items.map((item, i) => (
        <div key={`${i}-${item}`} className="group/item flex items-start gap-1.5">
          <span aria-hidden className="mt-2.5 size-1 shrink-0 rounded-full bg-muted-foreground" />
          <Editable value={item} multiline className="text-sm" onSave={(t) => onSave(items.map((x, j) => (j === i ? t : x)))} />
          <Button variant="ghost" size="icon-xs" aria-label={`Take out “${item}”`} title="Take it out" onClick={() => onSave(items.filter((_, j) => j !== i))}
                  className="mt-0.5 text-muted-foreground opacity-0 group-hover/item:opacity-100 focus-visible:opacity-100 hover:text-destructive"><Trash2 /></Button>
        </div>
      ))}
      {(max === undefined || items.length < max) && <Composer label={add} placeholder={placeholder} onAdd={(t) => onSave([...items, t])} />}
    </div>
  )
}

/** A line of text that's edited where it is: saved as you leave it, or with Enter. Escape: as it was. */
export function Editable({ value, onSave, className, multiline = false }: {
  value: string; onSave: (value: string) => void; className?: string; multiline?: boolean
}) {
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  const save = () => (text.trim() && text.trim() !== value ? onSave(text.trim()) : setText(value))
  const keys = (e: React.KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault()
      e.currentTarget.blur()
    }
    if (e.key === "Escape") {
      e.stopPropagation()  // not the card: only the edit
      setText(value)
      setTimeout(() => (document.activeElement as HTMLElement)?.blur())
    }
  }
  const style = cn("w-full min-w-0 rounded-md bg-transparent px-1.5 py-0.5 outline-none hover:bg-muted/70 focus:bg-background focus:ring-2 focus:ring-ring/40", className)

  return multiline ? (
    <textarea value={text} rows={1} onChange={(e) => setText(e.target.value)} onBlur={save} onKeyDown={keys}
              className={cn(style, "field-sizing-content resize-none")} />
  ) : (
    <input value={text} onChange={(e) => setText(e.target.value)} onBlur={save} onKeyDown={keys}
           className={cn(style, "field-sizing-content max-w-full")} />
  )
}

/** Free text, like a card's description: shown as it is (`list`: a line each, as a list), and a
 * box to write in once clicked. */
export function Notes({ value, placeholder, onSave, list = false }: { value: string; placeholder: string; onSave: (value: string) => void; list?: boolean }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(value)
  useEffect(() => setText(value), [value])
  const save = () => {
    setEditing(false)
    if (text !== value) onSave(text.trim())
  }

  if (!editing) {
    return (
      <button onClick={() => setEditing(true)}
              className={cn("w-full rounded-lg px-3 py-2 text-left text-sm whitespace-pre-wrap",
                            value ? "hover:bg-muted/70" : "min-h-14 bg-muted/60 text-muted-foreground hover:bg-muted")}>
        {!value ? placeholder : list ? (
          <ul className="flex list-disc flex-col gap-0.5 pl-4">{lines(value).map((line, i) => <li key={i}>{line}</li>)}</ul>
        ) : value}
      </button>
    )
  }
  return (
    <div className="flex flex-col gap-2">
      <Textarea autoFocus value={text} placeholder={placeholder} onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save()
                  if (e.key === "Escape") {
                    e.stopPropagation()
                    setText(value)
                    setEditing(false)
                  }
                }}
                className="min-h-24" />
      <div className="flex items-center gap-1">
        <Button size="sm" onClick={save}>Save</Button>
        <Button size="sm" variant="ghost" onClick={() => { setText(value); setEditing(false) }}>Cancel</Button>
        <span className="ml-auto text-[11px] text-muted-foreground">⌘ Enter to save</span>
      </div>
    </div>
  )
}

/** "+ Add a …": a box to name a new one. Enter adds it and stays open for the next. */
export function Composer({ label, placeholder, onAdd }: { label: string; placeholder: string; onAdd: (name: string) => unknown }) {
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState("")
  const box = useRef<HTMLTextAreaElement>(null)
  const add = async () => {
    if (name.trim()) await onAdd(name.trim())
    setName("")
    box.current?.focus()
  }

  if (!adding) {
    return <Button variant="ghost" className="w-full justify-start text-muted-foreground" onClick={() => setAdding(true)}><Plus data-icon="inline-start" /> {label}</Button>
  }
  return (
    <div className="flex flex-col gap-2">
      <Textarea ref={box} autoFocus rows={2} value={name} placeholder={placeholder} onChange={(e) => setName(e.target.value)}
                onBlur={() => !name.trim() && setAdding(false)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault()
                    add()
                  }
                  if (e.key === "Escape") {
                    e.stopPropagation()
                    setName("")
                    setAdding(false)
                  }
                }}
                className="min-h-0 resize-none bg-card" />
      <div className="flex items-center gap-1">
        <Button size="sm" onMouseDown={(e) => e.preventDefault()} onClick={add}>{label}</Button>
        <Button size="icon-sm" variant="ghost" aria-label="Cancel" onClick={() => { setName(""); setAdding(false) }}><X /></Button>
      </div>
    </div>
  )
}
