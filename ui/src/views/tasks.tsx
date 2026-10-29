// Tasks: your work as a board, like Trello. A card for each group, in the row of its most
// relevant tag (a row with no groups isn't shown). A card opens to its group: what it's
// about, its tags, and its tasks, a checklist. A task opens to what it is and your notes on it.
// Everything is edited in place, and saved as you leave the field. A card is picked up and
// carried: along its row, the others making room, or into the row of another of its tags (that
// tag comes first). A row that takes it lights up, one that won't shakes. A ready task is
// carried up or down its list the same way. The ready tasks, all they need done, stand out,
// the others wait in grey. The changes proki suggests show on the card as a count, and opened,
// each to accept or not. A ready task's ▶ works on it now: a focus session on it, its time
// counted. Reloads when the window is focused.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import {
  DndContext, DragOverlay, KeyboardSensor, PointerSensor, closestCenter, pointerWithin, useDroppable, useSensor, useSensors,
  type CollisionDetection, type DragEndEvent, type DragOverEvent, type DragStartEvent,
} from "@dnd-kit/core"
import {
  SortableContext, arrayMove, horizontalListSortingStrategy, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import {
  AlignLeft, ArrowLeft, Calendar, Check, ChevronDown, CircleHelp, Clock, Flag, GripVertical, LayoutGrid, ListChecks, Lock, Play, Plus,
  Pencil, RotateCcw, Sparkles, StickyNote, Tag, Trash2, X,
} from "lucide-react"
import { Confirm } from "@/components/confirm"
import { PageHeader } from "@/components/page"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Item, ItemActions, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item"
import { NativeSelect, NativeSelectOptGroup, NativeSelectOption } from "@/components/ui/native-select"
import { Progress } from "@/components/ui/progress"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { dayOf, dueText, endOf, type Board, type TaskGr, type Rows, type Task, type TaskOp } from "@/lib/proki"

type Change = (request: object) => Promise<number | null>  // a request to the board: the id it gives, if any

// each tag's row: the first it's in
const rowsOf = (rows: Rows) => Object.fromEntries(Object.entries(rows).reverse().flatMap(([row, tags]) => tags.map((tag) => [tag, row])))
const lines = (text: string) => text.split("\n").map((line) => line.trim()).filter(Boolean)
const minutes = (m: number) => (m < 60 ? `${m}m` : `${Math.floor(m / 60)}h${m % 60 ? ` ${m % 60}m` : ""}`)
const sortId = (id: number) => `g${id}`

// a card is picked up once the pointer's moved a little: a click still opens it
export const useDrag = () => useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
                                        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }))

// a card over another card first, else over the row the pointer's in
const landing: CollisionDetection = (args) => {
  const hits = pointerWithin(args)
  const cards = hits.filter((hit) => String(hit.id).startsWith("g"))
  return cards.length ? cards : hits.length ? hits : closestCenter(args)
}

export function TasksView({ open, onOpen }: { open: number | null; onOpen: (group: number | null) => void }) {
  const [board, setBoard] = useState<Board>({ groups: [], tasks: [], ops: [], rows: {} })
  const [showDone, setShowDone] = useState(false)
  const [error, setError] = useState("")
  const [carried, setCarried] = useState<TaskGr | null>(null)  // the card picked up
  const [over, setOver] = useState<{ row: string; takes: boolean } | null>(null)  // the row it's over
  const sensors = useDrag()

  const load = useCallback(async () => {
    const answer = await window.proki.tasks({ op: "read" })
    if (answer.error) return setError(answer.error)
    setError("")
    setBoard(answer)
  }, [])

  useEffect(() => {
    load()
    window.addEventListener("focus", load)
    return () => window.removeEventListener("focus", load)
  }, [load])

  const change: Change = async (request) => {
    const answer = await window.proki.tasks(request)
    if (answer.error) setError(answer.error)
    await load()
    return answer.id ?? null
  }

  const left = board.tasks.filter((t) => t.status === "open" && board.groups.some((p) => p.id === t.group && p.status === "open"))
  const group = board.groups.find((p) => p.id === open) ?? null
  const shown = board.groups.filter((p) => showDone || p.status === "open")
  const row = rowsOf(board.rows)
  const rowOf = (p: TaskGr) => (p.tags.length ? row[p.tags[0]] : "")  // "": no tags
  const rowsFor = (p: TaskGr) => (p.tags.length ? p.tags.map((tag) => row[tag]) : [""])  // the rows it can go in
  const rows = [...Object.keys(board.rows), ""].filter((r) => shown.some((p) => rowOf(p) === r))  // in their order, no tags last

  const target = (e: DragOverEvent | DragEndEvent) => e.over?.data.current?.row as string | undefined
  const dragged = (e: DragOverEvent) => {
    const to = target(e)
    setOver(carried && to !== undefined ? { row: to, takes: rowsFor(carried).includes(to) } : null)
  }
  const dropped = async (e: DragEndEvent) => {
    const moved = carried, to = target(e)
    setCarried(null)
    setOver(null)
    if (!moved || to === undefined || !rowsFor(moved).includes(to)) return
    const onCard = String(e.over!.id).startsWith("g") ? Number(String(e.over!.id).slice(1)) : null
    if (onCard === moved.id) return
    let before = onCard
    if (rowOf(moved) === to) {  // along its row: where it lands, the others making room
      const ids = shown.filter((p) => rowOf(p) === to).map((p) => p.id)
      const at = onCard === null ? ids.length - 1 : ids.indexOf(onCard)
      const order = arrayMove(ids, ids.indexOf(moved.id), at)
      before = order[at + 1] ?? null
    }
    const first = moved.tags.find((tag) => row[tag] === to)  // into another row: its tag there first
    if (rowOf(moved) !== to && first) await change({ op: "change", record: "work.groups", id: moved.id, tags: [first, ...moved.tags.filter((tag) => tag !== first)] })
    change({ op: "move", record: "work.groups", id: moved.id, before })
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Tasks" className="border-b px-8 pt-7 pb-5"
                  sub={<><span className="tabular-nums">{left.length}</span> to do · about {minutes(left.reduce((sum, t) => sum + t.estimate, 0))} of work</>}>
        <Field orientation="horizontal" className="w-auto">
          <Switch id="show-done" checked={showDone} onCheckedChange={setShowDone} />
          <FieldLabel htmlFor="show-done" className="font-normal text-muted-foreground">Show finished</FieldLabel>
        </Field>
      </PageHeader>

      <main className="min-h-0 flex-1 overflow-y-auto px-8 py-5">
        {error && <Alert variant="destructive" className="mb-4"><AlertDescription>{error}</AlertDescription></Alert>}
        {rows.length === 0 && (
          <Empty className="mt-6">
            <EmptyHeader>
              <EmptyMedia variant="icon"><LayoutGrid /></EmptyMedia>
              <EmptyTitle>No groups yet</EmptyTitle>
              <EmptyDescription>Add one below, or write down what you need to do with “New note”: proki plans it into tasks.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        )}
        <DndContext sensors={sensors} collisionDetection={landing} onDragStart={(e: DragStartEvent) => setCarried(e.active.data.current?.group ?? null)}
                    onDragOver={dragged} onDragEnd={dropped} onDragCancel={() => { setCarried(null); setOver(null) }}>
          <div className="flex flex-col gap-6">
            {rows.map((r) => (
              <TagRow key={r} row={r} groups={shown.filter((p) => rowOf(p) === r)} tasks={board.tasks} ops={board.ops}
                      over={over?.row === r ? over.takes : null} carrying={carried !== null} onOpen={onOpen} />
            ))}
          </div>
          <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.2, 0, 0, 1)" }}>
            {carried && <GroupTile group={carried} tasks={board.tasks.filter((t) => t.group === carried.id)}
                                   suggested={board.ops.filter((o) => o.group === carried.id).length} lifted />}
          </DragOverlay>
        </DndContext>
        <div className="mt-6 w-72">
          <Composer label="Add a group" placeholder="Name the group…"
                    onAdd={async (name) => {
                      const id = await change({ op: "add", record: "work.groups", name })
                      if (id !== null) onOpen(id)  // to tag it
                    }} />
        </div>
      </main>

      <Dialog open={group !== null} onOpenChange={(on) => !on && onOpen(null)}>
        {group && <GroupCard group={group} board={board} onChange={change} onClose={() => onOpen(null)} />}
      </Dialog>
    </div>
  )
}

// --- a row: a tag's groups --------------------------------------------------------------

function TagRow({ row, groups, tasks, ops, over, carrying, onOpen }: {
  row: string; groups: TaskGr[]; tasks: Task[]; ops: TaskOp[]; over: boolean | null; carrying: boolean; onOpen: (group: number) => void
}) {
  const { setNodeRef } = useDroppable({ id: `row:${row}`, data: { row } })
  const open = groups.filter((p) => p.status === "open").length

  return (
    <section ref={setNodeRef}
             className={cn("rounded-xl bg-muted/40 p-3 transition-[background-color,box-shadow] duration-150 dark:bg-muted/30",
                           carrying && over === null && "ring-1 ring-foreground/15",
                           over === true && "bg-primary/5 ring-2 ring-primary/50",
                           over === false && "animate-shake bg-destructive/5 ring-2 ring-destructive/50")}>
      <div className="mb-2 flex items-center gap-2 px-1">
        <h2 className={cn("text-sm font-semibold capitalize", !row && "text-muted-foreground")}>{row || "No tag"}</h2>
        <span className="text-xs text-muted-foreground tabular-nums">{open}</span>
        {over === true && <span className="text-xs font-medium text-primary">Drop it here</span>}
        {over === false && <span className="text-xs text-destructive">It can't go here: give it a tag from this row first</span>}
      </div>

      <SortableContext items={groups.map((g) => sortId(g.id))} strategy={horizontalListSortingStrategy}>
        <div className="flex min-h-24 items-stretch gap-3 overflow-x-auto pb-1">
          {groups.map((group) => (
            <SortableTile key={group.id} group={group} row={row} tasks={tasks.filter((t) => t.group === group.id)}
                          suggested={ops.filter((o) => o.group === group.id).length} onOpen={() => onOpen(group.id)} />
          ))}
        </div>
      </SortableContext>
    </section>
  )
}

function SortableTile({ group, row, tasks, suggested, onOpen }: { group: TaskGr; row: string; tasks: Task[]; suggested: number; onOpen: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: sortId(group.id), data: { row, group } })
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }} {...attributes} {...listeners}
         className={cn("shrink-0 cursor-grab touch-none rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                       isDragging && "opacity-40")}
         onClick={onOpen} onKeyDown={(e) => { listeners?.onKeyDown?.(e); if (e.key === "Enter" && !e.defaultPrevented) onOpen() }}>
      <GroupTile group={group} tasks={tasks} suggested={suggested} placeholder={isDragging} />
    </div>
  )
}

/** A group's card on the board: its name, and what's on it at a glance. */
function GroupTile({ group, tasks, suggested, lifted = false, placeholder = false }: {
  group: TaskGr; tasks: Task[]; suggested: number; lifted?: boolean; placeholder?: boolean
}) {
  const done = tasks.filter((t) => t.status === "done").length
  const left = tasks.filter((t) => t.status === "open").reduce((sum, t) => sum + t.estimate, 0) || group.estimate || 0
  const due = dueText(group.deadline)
  const finished = group.status !== "open"

  return (
    <Card size="sm" className={cn("h-full w-64 gap-3 transition-[box-shadow,transform] hover:ring-foreground/25",
                                  finished && "opacity-60",
                                  placeholder && "bg-muted shadow-none",
                                  lifted && "rotate-[1.5deg] scale-[1.03] cursor-grabbing shadow-xl ring-primary/40")}>
      <CardHeader>
        <CardTitle className={cn("leading-snug", finished && "line-through")}>{group.name}</CardTitle>
        {group.desc && <CardDescription className="line-clamp-2">{group.desc}</CardDescription>}
      </CardHeader>
      {(tasks.length > 0 || left > 0) && (
        <div className="flex items-center gap-2 px-(--card-spacing) text-xs text-muted-foreground tabular-nums">
          {tasks.length > 0 && <><Progress value={(done / tasks.length) * 100} className="h-1.5" aria-label="Tasks done" /><span>{done}/{tasks.length}</span></>}
          {left > 0 && <span className="ml-auto shrink-0" title="Time left">{tasks.length > 0 && "· "}{minutes(left)} left</span>}
        </div>
      )}
      {(due || suggested > 0) && (
        <CardFooter className="mt-auto flex-wrap gap-1.5">
          {due && <Badge variant={due === "overdue" && !finished ? "destructive" : "secondary"}><Clock data-icon="inline-start" />{due.replace("due ", "")}</Badge>}
          {suggested > 0 && <Badge className="bg-brand/15 text-brand"><Sparkles data-icon="inline-start" />{suggested} suggested</Badge>}
        </CardFooter>
      )}
    </Card>
  )
}

// --- a card, opened: the group ----------------------------------------------------------

function GroupCard({ group, board, onChange, onClose }: {
  group: TaskGr; board: Board; onChange: Change; onClose: () => void
}) {
  const tasks = board.tasks.filter((t) => t.group === group.id)
  const ops = board.ops.filter((o) => o.group === group.id)
  const done = tasks.filter((t) => t.status === "done").length
  const [hideDone, setHideDone] = useState(false)
  const [opened, setOpened] = useState<number | null>(null)  // the task whose details show
  const set = (fields: object) => onChange({ op: "change", record: "work.groups", id: group.id, ...fields })
  const finished = group.status !== "open"
  const listed = tasks.filter((t) => !hideDone || t.status !== "done")
  const sensors = useDrag()

  const dropped = (e: DragEndEvent) => {  // a ready task, where it lands in the list
    if (!e.over || e.active.id === e.over.id) return
    const ids = listed.map((t) => t.id), from = ids.indexOf(Number(e.active.id)), at = ids.indexOf(Number(e.over.id))
    const order = arrayMove(ids, from, at)
    onChange({ op: "move", record: "work.tasks", id: Number(e.active.id), before: order[at + 1] ?? null })
  }

  return (
    <DialogContent className="max-h-[88vh] gap-0 overflow-y-auto p-0 sm:max-w-3xl">
      <div className="flex items-start gap-3 px-6 pt-6 pb-4">
        <LayoutGrid className="mt-1.5 size-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1 pr-8">
          <DialogTitle className="sr-only">{group.name}</DialogTitle>
          <Editable value={group.name} multiline className="text-lg font-semibold" onSave={(name) => set({ name })} />
          {finished && <Badge variant="secondary" className="mt-1 ml-1.5 capitalize">{group.status}</Badge>}
        </div>
      </div>

      <div className="grid grid-cols-[1fr_11rem] gap-6 px-6 pb-6 max-[640px]:grid-cols-1">
        <div className="flex min-w-0 flex-col gap-6">
          <Section icon={<Tag />} title="Tags">
            <TagEditor tags={group.tags} rows={board.rows} onSave={(tags) => set({ tags })} />
          </Section>

          <Section icon={<AlignLeft />} title="Description">
            <Notes value={group.desc} placeholder="Add a more detailed description…" onSave={(desc) => set({ desc })} />
          </Section>

          <Section icon={<CircleHelp />} title="Open questions">
            <Notes value={group.questions.join("\n")} list placeholder="What only you can answer yet, one a line…"
                   onSave={(text) => set({ questions: lines(text) })} />
          </Section>

          {ops.length > 0 && <Suggestions ops={ops} tasks={tasks} onChange={onChange} />}

          <Section icon={<ListChecks />} title="Tasks" action={done > 0 && (
            <Button variant="ghost" size="xs" onClick={() => setHideDone(!hideDone)}>
              {hideDone ? `Show checked items (${done})` : "Hide checked items"}
            </Button>
          )}>
            <div className="flex items-center gap-3">
              <span className="w-8 text-right text-xs text-muted-foreground tabular-nums">{tasks.length ? Math.round((done / tasks.length) * 100) : 0}%</span>
              <Progress value={tasks.length ? (done / tasks.length) * 100 : 0} aria-label="Tasks done" />
            </div>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={dropped}>
              <SortableContext items={listed.map((t) => t.id)} strategy={verticalListSortingStrategy}>
                <div className="mt-2 flex flex-col">
                  {listed.map((task) => (
                    <TaskEntry key={task.id} task={task} tasks={tasks} opened={opened === task.id} onChange={onChange}
                               onToggle={() => setOpened(opened === task.id ? null : task.id)} />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
            <div className="mt-1">
              <Composer label="Add a task" placeholder="What's one thing to do?"
                        onAdd={(name) => onChange({ op: "add", record: "work.tasks", group: group.id, name })} />
            </div>
          </Section>
        </div>

        <aside>
          <FieldGroup className="gap-4">
            <Field>
              <FieldLabel htmlFor="group-due">Due date</FieldLabel>
              <Input id="group-due" type="date" value={dayOf(group.deadline)} onChange={(e) => set({ deadline: endOf(e.target.value) })} />
            </Field>
            <Field>
              <FieldLabel htmlFor="group-estimate">Estimate, in minutes</FieldLabel>
              <Input id="group-estimate" type="number" min={0} step={15} defaultValue={group.estimate ?? ""} key={group.estimate} placeholder="–"
                     onBlur={(e) => {
                       const estimate = e.target.value ? Number(e.target.value) : null
                       if (estimate !== group.estimate) set({ estimate })
                     }} />
            </Field>
            <Field>
              <FieldLabel>Actions</FieldLabel>
              {finished
                ? <Button variant="secondary" size="sm" className="justify-start" onClick={() => set({ status: "open" })}><RotateCcw data-icon="inline-start" /> Reopen</Button>
                : <Button variant="secondary" size="sm" className="justify-start" onClick={() => set({ status: "done" })}><Check data-icon="inline-start" /> Mark done</Button>}
              <Confirm title={`Delete “${group.name}”?`} description="The group and all its tasks are deleted. This can't be undone."
                       onConfirm={async () => { onClose(); await onChange({ op: "remove", record: "work.groups", id: group.id }) }}>
                <Button variant="ghost" size="sm" className="justify-start text-muted-foreground hover:text-destructive"><Trash2 data-icon="inline-start" /> Delete</Button>
              </Confirm>
            </Field>
          </FieldGroup>
        </aside>
      </div>
    </DialogContent>
  )
}

// --- the changes suggested, each to accept or not ---------------------------------------------

const LABEL: Record<string, string> = { name: "Name", desc: "About", estimate: "Time", deadline: "Due", done_when: "Done when", checkpoint: "Checkpoint", after: "Do first", note: "Note" }
const said = (name: string, value: unknown): string =>
  value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length) ? "nothing"
  : name === "estimate" ? minutes(Number(value))
  : name === "deadline" ? new Date(String(value)).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
  : typeof value === "boolean" ? (value ? "yes" : "no")
  : Array.isArray(value) ? value.join("; ") : String(value)

/** The ops suggested on a group's tasks, in order: an add, a change, a removal, each task
 * by its key. One can be accepted once each task it say is there, made with the board's own
 * requests: an add after another waits for it, greyed out. */
function Suggestions({ ops, tasks, onChange }: { ops: TaskOp[]; tasks: Task[]; onChange: Change }) {
  const by = Object.fromEntries(tasks.map((t) => [t.key, t]))
  const say = (op: TaskOp) => [...(op.task === null ? [] : [op.task]), ...(op.after ?? [])]
  const named = (key: string) => by[key]?.name ?? ops.find((o) => o.fields.key === key)?.fields.name ?? key

  // each op that can be, made then taken away, in order: an add's task there for the ones after it
  const accept = async (chosen: TaskOp[]) => {
    const ids: Record<string, number> = Object.fromEntries(tasks.map((t) => [t.key, t.id]))
    let left = chosen.filter((op) => say(op).every((h) => h in ids || chosen.some((o) => o.fields.key === h)))
    while (left.length) {
      const op = left.find((o) => say(o).every((h) => h in ids))
      if (!op) break
      left = left.filter((o) => o !== op)
      const after = op.after?.map((h) => ids[h])
      if (op.op === "add") {
        const id = await onChange({ op: "add", record: "work.tasks", group: op.group, ...op.fields, after: after ?? [] })
        if (id !== null && op.fields.key) ids[op.fields.key] = id
      } else if (op.op === "change") {
        await onChange({ op: "change", record: "work.tasks", id: ids[op.task!], ...op.fields, ...(after && { after }) })
      } else {
        await onChange({ op: "change", record: "work.tasks", id: ids[op.task!], status: "dropped" })
      }
      await onChange({ op: "remove", record: "ops", id: op.id })
    }
  }

  return (
    <Section icon={<Sparkles />} title={`Suggested by proki (${ops.length})`} action={
      <Button variant="ghost" size="xs" onClick={() => accept(ops)}>Accept all</Button>
    }>
      <ItemGroup className="gap-2">
        {ops.map((op) => {
          const task = op.task === null ? null : by[op.task] ?? null
          const waiting = say(op).filter((h) => !(h in by))
          const name = op.op === "add" ? String(op.fields.name ?? "") : task?.name ?? op.task
          const fields = Object.entries(op.fields).filter(([key]) => key !== "key" && (op.op !== "add" || key !== "name"))
          const after = op.after === null ? null : op.after.map(named)
          const Icon = op.op === "add" ? Plus : op.op === "change" ? Pencil : Trash2
          return (
            <Item key={op.id} variant="outline" size="sm" className={cn("items-start", waiting.length > 0 && "opacity-60")}>
              <ItemMedia variant="icon" className={cn(op.op === "add" ? "text-focused" : op.op === "remove" ? "text-destructive" : "text-shallow")}><Icon /></ItemMedia>
              <ItemContent>
                <ItemTitle className="flex-wrap">
                  <span className="font-normal text-muted-foreground">{op.op === "add" ? "Add" : op.op === "change" ? "Change" : "Drop"}</span>
                  <span className={cn(op.op === "remove" && "line-through decoration-destructive/60")}>{name}</span>
                </ItemTitle>
                {op.op === "remove" && <ItemDescription>It comes off the list. You can bring it back from the finished tasks.</ItemDescription>}
                {(fields.length > 0 || after) && (
                  <dl className="mt-1 grid grid-cols-[5.5rem_1fr] gap-x-3 gap-y-1 text-xs">
                    {fields.map(([key, value]) => (
                      <Changed key={key} label={LABEL[key] ?? key} before={op.op === "change" && task ? said(key, task[key as keyof Task]) : null} after={said(key, value)} />
                    ))}
                    {after && (
                      <Changed label={LABEL.after} before={op.op === "change" && task ? said("after", task.after.map((id) => tasks.find((t) => t.id === id)?.name)) : null}
                               after={said("after", after)} />
                    )}
                  </dl>
                )}
                {waiting.length > 0 && <ItemDescription>Waits for {waiting.map((h) => `“${named(h)}”`).join(", ")} to be accepted first</ItemDescription>}
              </ItemContent>
              <ItemActions>
                <Button size="xs" variant="secondary" disabled={waiting.length > 0} onClick={() => accept([op])}><Check data-icon="inline-start" /> Accept</Button>
                <Button size="xs" variant="ghost" onClick={() => onChange({ op: "remove", record: "ops", id: op.id })}>Skip</Button>
              </ItemActions>
            </Item>
          )
        })}
      </ItemGroup>
    </Section>
  )
}

/** A field as the suggestion would have it: what it was, struck through, and what it'd be. */
function Changed({ label, before, after }: { label: string; before: string | null; after: string }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0">
        {before !== null && <><span className="text-muted-foreground line-through">{before}</span><span aria-label="becomes" className="mx-1.5 text-muted-foreground">→</span></>}
        <span className="font-medium">{after}</span>
      </dd>
    </>
  )
}

/** A task in the checklist: ticked, renamed, carried. Clicked: what it is, and your notes. */
function TaskEntry({ task, tasks, opened, onChange, onToggle }: {
  task: Task; tasks: Task[]; opened: boolean; onChange: Change; onToggle: () => void
}) {
  const set = (fields: object) => onChange({ op: "change", record: "work.tasks", id: task.id, ...fields })
  const done = task.status === "done"
  const due = dueText(task.deadline)
  const needs = tasks.filter((t) => task.after.includes(t.id))
  const waiting = needs.filter((t) => t.status === "open")  // what it waits for
  const ready = task.status === "open" && waiting.length === 0  // the only ones you can carry
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id, disabled: !ready })

  return (
    <Collapsible open={opened} onOpenChange={onToggle} ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }}
                 className={cn("relative rounded-lg", opened && "bg-muted/60", isDragging && "z-10 bg-card shadow-lg ring-1 ring-foreground/10")}>
      <div className="group/task flex items-center gap-2 rounded-lg px-1 py-1 hover:bg-muted/60">
        <button {...attributes} {...listeners} aria-label="Move" disabled={!ready}
                className={cn("touch-none text-muted-foreground/50 opacity-0 disabled:invisible", ready && "cursor-grab group-hover/task:opacity-100 focus-visible:opacity-100")}>
          <GripVertical className="size-3.5" />
        </button>
        <Checkbox checked={done} onCheckedChange={(on) => set({ status: on ? "done" : "open" })} aria-label={`${task.name}: done`} />
        {task.checkpoint && <Flag className="size-3.5 shrink-0 text-primary" aria-label="a checkpoint" />}
        <button onClick={onToggle}
                className={cn("min-w-0 flex-1 truncate py-0.5 text-left text-sm", ready ? "font-medium" : "text-muted-foreground",
                              task.status !== "open" && "line-through")}>
          {task.name}
        </button>
        {!done && waiting.length > 0 && (
          <Badge variant="outline" title={`After: ${waiting.map((t) => t.name).join(", ")}`}><Lock data-icon="inline-start" /> after {waiting.length}</Badge>
        )}
        {ready && (
          <Button variant="ghost" size="icon-xs" aria-label="Work on this" title="Work on this: a focus session on it"
                  onClick={() => onChange({ op: "work", id: task.id })} className="text-muted-foreground opacity-0 group-hover/task:opacity-100">
            <Play />
          </Button>
        )}
        {(task.desc || task.note) && !opened && <StickyNote className="size-3.5 text-muted-foreground" aria-label="has notes" />}
        {due && <Badge variant={due === "overdue" && !done ? "destructive" : "secondary"}>{due}</Badge>}
        <Badge variant="outline" className="tabular-nums">{minutes(task.estimate)}</Badge>
        <Button variant="ghost" size="icon-xs" onClick={onToggle} aria-label={opened ? "Close" : "Open"} className="text-muted-foreground">
          <ChevronDown className={cn("transition-transform", opened && "rotate-180")} />
        </Button>
      </div>

      <CollapsibleContent>
        <FieldGroup className="gap-4 px-8 pt-1 pb-3">
          <Editable value={task.name} multiline className="text-sm font-medium" onSave={(name) => set({ name })} />
          <Field>
            <FieldLabel>Description</FieldLabel>
            <Notes value={task.desc} placeholder="What is it, exactly?" onSave={(desc) => set({ desc })} />
          </Field>
          <Field>
            <FieldLabel>Done when</FieldLabel>
            <Notes value={task.done_when.join("\n")} list placeholder="What done looks like: a check anyone could make, one a line (3 at most)…"
                   onSave={(text) => set({ done_when: lines(text).slice(0, 3) })} />
          </Field>
          <Field>
            <FieldLabel>Do these first</FieldLabel>
            <div className="flex flex-wrap items-center gap-1.5">
              {needs.map((t) => (
                <Badge key={t.id} variant="secondary" className={cn("h-6", t.status !== "open" && "line-through")}>
                  {t.name}
                  <button aria-label={`Remove ${t.name}`} className="-mr-1 rounded-full p-0.5 opacity-60 hover:bg-foreground/10 hover:opacity-100"
                          onClick={() => set({ after: task.after.filter((id) => id !== t.id) })}><X className="size-3" /></button>
                </Badge>
              ))}
              <NativeSelect size="sm" value="" className="w-56" onChange={(e) => e.target.value && set({ after: [...task.after, Number(e.target.value)] })}>
                <NativeSelectOption value="">+ A task it needs first</NativeSelectOption>
                {tasks.filter((t) => t.id !== task.id && !task.after.includes(t.id)).map((t) => <NativeSelectOption key={t.id} value={t.id}>{t.name}</NativeSelectOption>)}
              </NativeSelect>
            </div>
          </Field>
          <Field>
            <FieldLabel>Note</FieldLabel>
            <Notes value={task.note} placeholder="Your own notes: links, where you left off…" onSave={(note) => set({ note })} />
          </Field>
          <div className="flex flex-wrap items-end gap-4">
            <Field className="w-24">
              <FieldLabel htmlFor={`estimate-${task.id}`}><Clock /> Minutes</FieldLabel>
              <Input id={`estimate-${task.id}`} type="number" min={5} max={600} step={5} defaultValue={task.estimate} key={task.estimate}
                     onBlur={(e) => Number(e.target.value) > 0 && Number(e.target.value) !== task.estimate && set({ estimate: Number(e.target.value) })} />
            </Field>
            <Field className="w-40">
              <FieldLabel htmlFor={`due-${task.id}`}><Calendar /> Due</FieldLabel>
              <Input id={`due-${task.id}`} type="date" value={dayOf(task.deadline)} onChange={(e) => set({ deadline: endOf(e.target.value) })} />
            </Field>
            <Field orientation="horizontal" className="w-auto pb-2" title="A check it all works together, and what's next">
              <Checkbox id={`checkpoint-${task.id}`} checked={task.checkpoint} onCheckedChange={(on) => set({ checkpoint: on === true })} />
              <FieldLabel htmlFor={`checkpoint-${task.id}`} className="font-normal">Checkpoint</FieldLabel>
            </Field>
            <Confirm title={`Delete “${task.name}”?`} description="The task and your notes on it are deleted. This can't be undone."
                     onConfirm={() => onChange({ op: "remove", record: "work.tasks", id: task.id })}>
              <Button variant="ghost" size="icon-sm" aria-label="Delete the task" className="ml-auto text-muted-foreground hover:text-destructive"><Trash2 /></Button>
            </Confirm>
          </div>
        </FieldGroup>
      </CollapsibleContent>
    </Collapsible>
  )
}

// --- the pieces ---------------------------------------------------------------------------

function Section({ icon, title, action, children }: { icon: ReactNode; title: string; action?: ReactNode; children: ReactNode }) {
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

/** A group's tags, the most likely first, 3 at most: the first one's row is where its card is.
 * A tag moves up with its arrow, goes with its cross, and comes in from the list, by row. */
function TagEditor({ tags, rows, onSave }: { tags: string[]; rows: Rows; onSave: (tags: string[]) => void }) {
  const row = rowsOf(rows)
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tags.map((tag, i) => (
        <Badge key={tag} variant={i === 0 ? "default" : "secondary"} className="group/tag h-6"
               title={i === 0 ? "The most relevant: the card is in its row" : undefined}>
          {i > 0 && (
            <button aria-label={`${tag}: more relevant`} className="-ml-1 hidden rounded-full p-0.5 opacity-60 group-hover/tag:inline hover:bg-foreground/10 hover:opacity-100"
                    onClick={() => onSave([...tags.slice(0, i - 1), tag, tags[i - 1], ...tags.slice(i + 1)])}>
              <ArrowLeft className="size-3" />
            </button>
          )}
          {tag}
          <button aria-label={`Remove ${tag}`} className="-mr-1 rounded-full p-0.5 opacity-60 hover:bg-foreground/10 hover:opacity-100" onClick={() => onSave(tags.filter((t) => t !== tag))}><X className="size-3" /></button>
        </Badge>
      ))}
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

/** A line of text that's edited where it is: saved as you leave it, or with Enter. Escape: as it was. */
function Editable({ value, onSave, className, multiline = false }: {
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
function Notes({ value, placeholder, onSave, list = false }: { value: string; placeholder: string; onSave: (value: string) => void; list?: boolean }) {
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
function Composer({ label, placeholder, onAdd }: { label: string; placeholder: string; onAdd: (name: string) => unknown }) {
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
