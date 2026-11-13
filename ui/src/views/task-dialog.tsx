// A task, opened over its group's dialog: what it is, what done looks like, what it waits for, your notes; and, at the side, its time, its day, whether it's a checkpoint, and done or deleted.

import { AlignLeft, Check, CircleHelp, Link2, ListChecks, RotateCcw, StickyNote, Trash2, X } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Pick } from "@/views/in-place"
import { cn } from "@/lib/utils"
import { dayOf, endOf, type Task } from "@/lib/proki"
import { AutoSaveText, ItemList, Notes, Section } from "@/views/task-parts"

/** A task over its group's dialog, each part changed where it is and saved as you leave it (`onChange`: a request to the board). */
export function TaskDialog({ task, tasks, onChange, onClose }: { task: Task; tasks: Task[]; onChange: (request: object) => Promise<unknown>; onClose: () => void }) {
  const set   = (fields: object) => onChange({ op: "change", record: "work.tasks", id: task.id, ...fields })
  const done  = task.status === "done"
  const needs = tasks.filter((t) => task.after.includes(t.id))
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent over className="max-h-[88vh] gap-0 overflow-y-auto p-0 sm:max-w-2xl">
        <div className="flex items-start gap-3 px-6 pt-6 pb-4">
          <ListChecks className="mt-1.5 size-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0 flex-1 pr-8">
            <DialogTitle className="sr-only">{task.name}</DialogTitle>
            <DialogDescription className="sr-only">What it is, what done looks like, what it waits for, and your notes on it.</DialogDescription>
            <AutoSaveText label="Task name" value={task.name} multiline className="text-lg font-semibold" onSave={(name) => set({ name })} />
            {task.status !== "open" && <Badge variant="secondary" className="mt-1 ml-1.5 capitalize">{task.status}</Badge>}
          </div>
        </div>

        <div className="grid grid-cols-[1fr_10rem] gap-6 px-6 pb-6 max-[640px]:grid-cols-1">
          <div className="flex min-w-0 flex-col gap-6">
            <Section icon={<AlignLeft />} title="Description">
              <Notes value={task.desc} placeholder="What is it, exactly?" onSave={(desc) => set({ desc })} />
            </Section>

            <Section icon={<CircleHelp />} title="Done when">
              <ItemList items={task.done_when} max={3} add="Add a check" placeholder="What done looks like: a check anyone could make…"
                        onSave={(items) => set({ done_when: items.slice(0, 3) })} />
            </Section>

            <Section icon={<Link2 />} title="Dependencies">
              <div className="flex flex-wrap items-center gap-1.5">
                {needs.map((t) => (
                  <Badge key={t.id} variant="secondary" className={cn("h-6", t.status !== "open" && "line-through")}>
                    {t.name}
                    <button aria-label={`Remove ${t.name}`} className="-mr-1 rounded-full p-0.5 opacity-60 hover:bg-foreground/10 hover:opacity-100"
                            onClick={() => set({ after: task.after.filter((id) => id !== t.id) })}><X className="size-3" /></button>
                  </Badge>
                ))}
                <Pick label="Add a dependency" value="" arrow onPick={(id) => set({ after: [...task.after, Number(id)] })}
                      options={tasks.filter((t) => t.id !== task.id && !task.after.includes(t.id)).map((t) => [String(t.id), t.name])}>
                  + A task it needs first
                </Pick>
              </div>
            </Section>

            <Section icon={<StickyNote />} title="Note">
              <Notes value={task.note} placeholder="Your own notes: links, where you left off…" onSave={(note) => set({ note })} />
            </Section>
          </div>

          <aside>
            <FieldGroup className="gap-4">
              <Field>
                <FieldLabel htmlFor={`due-${task.id}`}>Due date</FieldLabel>
                <Input id={`due-${task.id}`} type="date" value={dayOf(task.deadline)} onChange={(e) => set({ deadline: endOf(e.target.value) })} className="w-full" />
              </Field>
              <Field>
                <FieldLabel htmlFor={`estimate-${task.id}`}>Estimate, in minutes</FieldLabel>
                <Input id={`estimate-${task.id}`} type="number" min={5} max={600} step={5} defaultValue={task.estimate} key={task.estimate}
                       onBlur={(e) => Number(e.target.value) > 0 && Number(e.target.value) !== task.estimate && set({ estimate: Number(e.target.value) })} />
              </Field>
              <Field orientation="horizontal" className="w-auto" title="A check it all works together, and what's next">
                <Checkbox id={`checkpoint-${task.id}`} checked={task.checkpoint} onCheckedChange={(on) => set({ checkpoint: on === true })} />
                <FieldLabel htmlFor={`checkpoint-${task.id}`} className="font-normal">Checkpoint</FieldLabel>
              </Field>
              <Field>
                <FieldLabel>Actions</FieldLabel>
                {done
                  ? <Button variant="secondary" size="sm" className="justify-start" onClick={() => set({ status: "open" })}><RotateCcw data-icon="inline-start" /> Reopen</Button>
                  : <Button variant="secondary" size="sm" className="justify-start" onClick={() => set({ status: "done" })}><Check data-icon="inline-start" /> Mark done</Button>}
                <Confirm title={`Delete “${task.name}”?`} description="The task and your notes on it are deleted. This can't be undone."
                         onConfirm={async () => { onClose(); await onChange({ op: "remove", record: "work.tasks", id: task.id }) }}>
                  <Button variant="ghost" size="sm" className="justify-start text-muted-foreground hover:text-destructive"><Trash2 data-icon="inline-start" /> Delete</Button>
                </Confirm>
              </Field>
            </FieldGroup>
          </aside>
        </div>
      </DialogContent>
    </Dialog>
  )
}
