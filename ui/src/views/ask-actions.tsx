// The LLM and jev actions, laid out as their source chips' dialogs are: a prompt or a question in a box of its own, rows of shaded boxes,
// a question's kind as tabs. Each takes its params and `put`, one key's new value (undefined: taken out), kept where the dialog keeps them.

import { useEffect, useState, type ReactNode } from "react"
import { DndContext, closestCenter, type DragEndEvent } from "@dnd-kit/core"
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import type { Type } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { TemplateBox } from "@/views/code"
import { ANSWERS, Criteria, KindTabs, TypeField, TypeIcon } from "@/views/fields"
import { Editable, Pick, typing } from "@/views/in-place"
import { NAMES, RowFields } from "@/views/action-rows"
import { contextOf } from "@/views/program-forms"
import { useDrag } from "@/views/tasks"

type Params = Record<string, unknown>
type Put    = (key: string, value: unknown) => void
type Where  = { program: string; state: string }

/** What a new action of each kind starts with. */
export const START: Record<string, Params> = {
  ask_usr: { result: "answer" },
  ask_llm: { result: "answer" },
  ask_jev: { questions: [{ type: "choice", question: "", criteria: { "": "" }, result: "answer" }] },
}

const LABELS = "8rem"  // the width of every row's label, so the boxes line up
const BOX = "w-full min-w-0 rounded-md bg-muted px-2 py-1.5 text-xs"

/** A number as typed: empty or not a number, none. */
const number = (t: string) => (t.trim() === "" || Number.isNaN(Number(t)) ? undefined : Number(t))

/** The rows every question has: where its answer goes, and how long it waits (a number, in seconds). */
function Waiting({ params, put, wait, save = true }: { params: Params; put: Put; wait: number; save?: boolean }) {
  const rows: [string, string, "text"][] = [...(save ? [["Save to", "result", "text"] as [string, string, "text"]] : []), ["Timeout", "timeout", "text"]]
  return (
    <RowFields rows={rows} label={LABELS} hints={{ result: "answer", timeout: String(wait) }} boxes={{ timeout: "w-14 flex-none text-center" }}
               aside={(key) => key === "timeout" ? <span className="py-1.5 text-muted-foreground">seconds</span> : null}
               field={(key) => {
                 const set = (t: string) => put(key, key === "timeout" ? number(t) : t.trim() || undefined)
                 return { value: String(params[key] ?? ""), onSave: async (t) => (set(t), null), onType: set }
               }} />
  )
}

/** The names a text's {slots} call for, each once, as Python reads a format string ("{h:.1f}": h). */
const slotsOf = (format: string) => [...new Set([...format.matchAll(/\{([^{}:!\n]*)(?:[:!][^{}\n]*)?\}/g)].map((m) => m[1].trim()).filter(Boolean))]

/** A text with {slots}, then what each stands for: a row a slot it has, the expression to type. */
function Prompt({ label, params, put, placeholder, min }: { label: string; params: Params; put: Put; placeholder: string; min: string }) {
  const { format, values } = contextOf(params.context)
  const exprs = new Map(values)
  const hold  = (f: string, kept: Map<string, string>) => put("context", { format: f, values: slotsOf(f).map((n): [string, string] => [n, kept.get(n) ?? ""]) })
  const names = slotsOf(format)
  return (
    <>
      <TemplateBox label={label} value={format} onChange={(e) => hold(e.target.value, exprs)} placeholder={placeholder} className={min} />
      {names.length > 0 && (
        <div className="flex flex-col gap-2 text-xs">
          <span className="text-muted-foreground">where</span>
          <RowFields rows={names.map((n): [string, string, "expr"] => [n, n, "expr"])} label={LABELS} joiner="is" hints={Object.fromEntries(names.map((n) => [n, "expression"]))}
                     field={(n) => { const set = (t: string) => hold(format, new Map(exprs).set(n, t.trim())); return { value: exprs.get(n) ?? "", onSave: async (t) => (set(t), null), onType: set } }} />
        </div>
      )}
    </>
  )
}

/** The type of the variable an answer is saved to, by its name as the state reads it (its own, its program's, then a global one): what the LLM
 * answers. It's set on the variable. */
function Answered({ name, at }: { name: string; at: Where }) {
  const [found, setFound] = useState<{ name: string; type: Type } | null>(null)
  useEffect(() => {
    let gone = false
    const names = name.includes(".") ? [name] : [`${at.program}.${at.state}.${name}`, `${at.program}.${name}`, name]
    ;(async () => {
      for (const n of names) {
        const answer = await window.proki.tool("evaluate", { expr: n })
        if (!answer.error) return gone || setFound({ name: n, type: answer.type ?? "any" })
      }
      if (!gone) setFound(null)
    })()
    return () => { gone = true }
  }, [name, at.program, at.state])
  if (!name.trim()) return null
  const text = !found || found.type === "any"
  return (
    <div className="flex flex-col gap-1.5 text-xs">
      <span className="font-medium">It answers<span className="ml-1.5 font-normal text-muted-foreground">
        {found ? (text ? "text: give the variable a type for more" : `as ${found.name} is typed; change it on the variable`) : "text, until the variable is made"}</span></span>
      {found && !text && <TypeField label="" value={found.type} fixed />}
    </div>
  )
}

/** The parts of an action's dialog, under a line from its title and description. */
const Parts = ({ children, wide }: { children: ReactNode; wide?: boolean }) => <div data-wide={wide || undefined} className="flex flex-col gap-4 border-t pt-4">{children}</div>

/** A question to the LLM: its prompt, where its answer goes, and how long it waits. */
export function AskLlm({ params, put, at }: { params: Params; put: Put; at: Where }) {
  return (
    <Parts>
      <Prompt label="Prompt" params={params} put={put} placeholder="How many hours will this take?" min="min-h-24" />
      <Waiting params={params} put={put} wait={10} />
      <Answered name={String(params.result ?? "")} at={at} />
    </Parts>
  )
}

type Question = { type: "noul" | "choice" | "score"; question: string; criteria?: Record<string, string | null> | string; result: string }

/** A question's row: a grip to move it by, its parts in `cols`, a click to open it, a trash as you point at it (none: it can't go). */
function QuestionRow({ id, cols, children, onOpen, onDelete }: { id: number; cols: string; children: ReactNode; onOpen: () => void; onDelete?: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }}
         className={cn("group/row relative border-b bg-background last:border-b-0 hover:bg-muted/50", isDragging && "z-10 shadow-lg ring-1 ring-foreground/10")}>
      <button type="button" {...attributes} {...listeners} aria-label="Move the question" className="absolute top-1/2 left-1.5 -translate-y-1/2 cursor-grab touch-none text-muted-foreground hover:text-foreground">
        <GripVertical className="size-3.5" />
      </button>
      <button type="button" onClick={onOpen} className={cn(cols, "w-full py-2 pr-9 pl-7 text-left")}>{children}</button>
      {onDelete && (
        <Button type="button" size="icon-xs" variant="ghost" aria-label="Take the question out" title="Take it out" onClick={onDelete}
                className="absolute top-1/2 right-1.5 -translate-y-1/2 text-destructive opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100"><Trash2 /></Button>
      )}
    </div>
  )
}

/** Questions to jev, asked at once about what its context says: a table of them, each a row (its kind, its question, where its answer goes) opened to change. */
export function AskJev({ params, put }: { params: Params; put: Put }) {
  const questions = (params.questions as Question[] | undefined) ?? []
  const [open, setOpen] = useState<number | null>(null)
  const edit = (i: number, change: Partial<Question>) => put("questions", questions.map((q, j) => (j !== i ? q : { ...q, ...change })))
  const kind = (i: number, type: Question["type"]) => edit(i, { type, criteria: type === "noul" ? undefined : questions[i].criteria ?? { "": "" } })
  const free = () => { const taken = new Set(questions.map((q) => q.result)); let n = 1; while (taken.has(`answer${n}`)) n++; return `answer${n}` }
  const COLS    = "grid grid-cols-[4.5rem_minmax(0,1fr)_7rem] items-center gap-3"
  const sensors = useDrag()
  const moved   = (e: DragEndEvent) => e.over && e.active.id !== e.over.id && put("questions", arrayMove(questions, Number(e.active.id) - 1, Number(e.over.id) - 1))
  const q    = open === null ? undefined : questions[open]
  return (
    <Parts wide>
      <Prompt label="Context" params={params} put={put} placeholder="{h:.1f} h shallow so far. Start a session?" min="min-h-16" />
      <div className="flex flex-col gap-1.5 border-t pt-4 text-xs">
        <div className="flex h-6 items-center justify-between">
          <span className="font-medium">Questions</span>
          <Button type="button" size="xs" variant="ghost" className="-mr-2 text-muted-foreground"
                  onClick={() => (put("questions", [...questions, { type: "noul", question: "", result: free() }]), setOpen(questions.length))}><Plus /> Question</Button>
        </div>
        <div className="rounded-md border">
          <div className={cn(COLS, "border-b bg-muted/40 py-1 pr-9 pl-7 text-muted-foreground")}><span>Kind</span><span>Question</span><span>Saved to</span></div>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={moved}>
            <SortableContext items={questions.map((_, i) => i + 1)} strategy={verticalListSortingStrategy}>
              {questions.map((x, i) => (
                <QuestionRow key={i} id={i + 1} cols={COLS} onOpen={() => setOpen(i)} onDelete={questions.length === 1 ? undefined : () => put("questions", questions.filter((_, j) => j !== i))}>
                  <span className="font-mono">{x.type}</span>
                  <span className={cn("truncate", !x.question && "text-muted-foreground")}>{x.question || "No question"}</span>
                  <span className="truncate font-mono">{x.result}</span>
                </QuestionRow>
              ))}
            </SortableContext>
          </DndContext>
        </div>
      </div>
      <Waiting params={params} put={put} wait={10} save={false} />
      {q && open !== null && (
        <Dialog open onOpenChange={(to) => !to && setOpen(null)}>
          <DialogContent over className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg" onEscapeKeyDown={typing}>
            <DialogHeader>
              <DialogTitle className="text-sm">Question {open + 1}</DialogTitle>
              <DialogDescription className="sr-only">Its kind, what it asks, and where its answer goes.</DialogDescription>
            </DialogHeader>
            <KindTabs kind={q.type} kinds={["noul", "choice", "score"]} onPick={(k) => kind(open, k as Question["type"])} />
            <TemplateBox label="Question" value={q.question} onChange={(e) => edit(open, { question: e.target.value })} placeholder={q.type === "noul" ? "Is it urgent?" : "What is it?"} className="min-h-10" />
            {q.type !== "noul" && (
              <div className="flex flex-col gap-1.5 text-xs">
                <span className="flex items-center gap-2 font-medium">{q.type === "score" ? "Marks" : "Options"}
                  <Pick label="Options from" value={typeof q.criteria === "string" ? "expr" : "list"} arrow options={[["list", "A list"], ["expr", "From an expression"]]}
                        onPick={(v) => edit(open, { criteria: v === "expr" ? "" : { "": "" } })} />
                </span>
                {typeof q.criteria === "string"
                  ? <Editable label="Options" code long clamp list={NAMES} placeholder="track.labels" className={BOX} value={q.criteria} onSave={async (t) => (edit(open, { criteria: t }), null)} onType={(t) => edit(open, { criteria: t })} />
                  : <Criteria key={`${open}-${q.type}`} criteria={q.criteria ?? {}} onSet={(criteria) => edit(open, { criteria })}
                              {...(q.type === "score" ? { label: "Marks", placeholder: "1" } : {})} />}
              </div>
            )}
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-3 text-xs">
              <div className="flex flex-col gap-1.5">
                <span className="font-medium">Answer schema</span>
                <div className="flex flex-col gap-0.5 rounded-md border p-2 font-mono">
                  {ANSWERS[q.type].map(([key, type]) => <span key={key} className="flex items-center gap-2 truncate"><TypeIcon type={type} />{key.replace(/^res/, q.result || "answer")}</span>)}
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="font-medium">Save answer to</span>
                <Editable label="Save answer to" code list={NAMES} placeholder="answer" className={cn(BOX, "h-fit")} value={q.result} onSave={async (t) => (edit(open, { result: t.trim() }), null)} onType={(t) => edit(open, { result: t.trim() })} />
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </Parts>
  )
}
