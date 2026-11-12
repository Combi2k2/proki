// A transition: the card a state shows it as, and the dialog that changes it.

import { useEffect, useRef, useState } from "react"
import { DndContext, closestCenter } from "@dnd-kit/core"
import { SortableContext, arrayMove, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { ArrowRight, GripVertical, Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { humane } from "@/lib/friendly"
import { type BranchSpec, type ProgramDetail } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { Expr } from "@/views/code"
import { Mark, Pill, SOURCES, TAG } from "@/views/fields"
import { Editable, Pick, Staging, type Staged } from "@/views/in-place"
import { NAMES } from "@/views/action-rows"
import { useLeave } from "@/views/scope-shared"
import { useDrag } from "@/views/tasks"
import { Truth } from "@/views/value-parts"

type Live = ProgramDetail["states"][number]["next"][number]
type Save = (data: Record<string, unknown>) => Promise<string | null>

/** What a condition (or a rule's name) is now: its rule, if it is one, and whether it holds (a rule: more likely than not; null: not known). */
function heldOf(live: Live | undefined, w: string) {
  const rule = live?.rules.find((r) => r.name === w)
  return { rule, holds: rule ? (rule.chance == null ? null : rule.chance >= 0.5) : live?.conds.find((c) => c.expr === w)?.value }
}

/** A transition as its state's card: what it's for, each condition under it marked whether it holds now, and where it goes (click that: go there). What doesn't hold
 * is greyed; `alone`, the state's only one, with no conditions: always. */
export function Way({ branch, live, alone, onGo }: { branch: BranchSpec; live?: Live; alone?: boolean; onGo: (state: string) => void }) {
  return (
    <>
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        {branch.desc && <span className="truncate text-foreground" title={branch.desc}>{branch.desc}</span>}
        <span className="grid grid-cols-[0.875rem_minmax(0,1fr)] items-center gap-x-2 gap-y-1 pl-4">
          {branch.when.length === 0 && <span className="col-span-2 text-muted-foreground">{alone ? "always" : "else"}</span>}
          {branch.when.map((w) => {
            const { holds } = heldOf(live, w)
            return (
              <span key={w} className={cn("contents", holds !== true && "text-muted-foreground")}>
                <Truth value={holds} />
                <Expr className="truncate" title={w}>{w}</Expr>
              </span>
            )
          })}
        </span>
      </span>
      <span className="flex w-32 shrink-0 justify-end">
        <button type="button" onClick={(e) => (e.stopPropagation(), onGo(branch.goto))} aria-label={`Go to the state ${humane(branch.goto)}`}
                className="flex min-h-7 min-w-0 items-center gap-1 rounded-lg border bg-background px-2.5 text-xs hover:border-foreground/30 hover:bg-muted">
          <ArrowRight aria-hidden className="size-3 shrink-0" /><span className="truncate font-mono">{humane(branch.goto)}</span>
        </button>
      </span>
    </>
  )
}

const COLS = "grid grid-cols-[5rem_minmax(0,1fr)_2.5rem] items-center gap-3"
const KINDS = [["expr", "An expression that holds or not"], ["rule", "A rule, more likely than not to fire"]] as const
const chip  = (kind: string) => kind === "rule" ? <Pill by="rule" /> : <span className={cn(TAG, SOURCES.expr.chip)}><Mark icon={SOURCES.expr.icon} />expr</span>

/** A condition's row: a grip to move it by, its parts in the table's columns, a bin as you point at it. `mark`: added, or changed, and not kept yet. */
function ConditionRow({ id, mark, children, onDelete }: { id: number; mark?: "added" | "changed"; children: React.ReactNode; onDelete: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Translate.toString(transform), transition }}
         className={cn("group/row relative border-t hover:bg-muted/50", mark === "added" && "bg-added/10", mark === "changed" && "bg-changed/10", isDragging && "opacity-40")}>
      <button type="button" {...attributes} {...listeners} aria-label="Move the condition" className="absolute top-1/2 left-1.5 -translate-y-1/2 cursor-grab touch-none text-muted-foreground hover:text-foreground">
        <GripVertical className="size-3.5" />
      </button>
      <div className={cn(COLS, "py-1.5 pr-9 pl-7")}>{children}</div>
      <Button type="button" size="icon-xs" variant="ghost" aria-label="Take the condition out" title="Take it out" onClick={onDelete}
              className="absolute top-1/2 right-1.5 -translate-y-1/2 text-destructive opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100"><Trash2 /></Button>
    </div>
  )
}

/** A transition, changed in a dialog: where it goes, and when (all of its conditions must hold; none: else). Nothing is kept until Save. `spec`: none, for a new one.
 * `onSave`: takes the transition (the mistake, if any); `onCancel`: leaves a new one; `onDirty`: told of the first change. */
export function TransitionForm({ spec, at, index, states, live, onSave, onCancel, onDirty }: {
  spec?: BranchSpec
  at: { program: string; state: string }
  index: number
  states: string[]
  live?: Live
  onSave: Save
  onCancel: () => void
  onDirty?: () => void
}) {
  const was = spec?.when ?? []
  const [rules, setRules] = useState<string[]>([])
  useEffect(() => void window.proki.tool("reference").then((r) => !r.error && setRules(r.rules.map((x: { name: string }) => x.name))), [])
  const keep = (patch: Record<string, unknown>) => onSave({
    goto: ((patch.goto as string | undefined) ?? spec?.goto ?? states[0] ?? "").trim(),
    when: ((patch.when as string[] | undefined) ?? was).map((w) => w.trim()).filter(Boolean),
    desc: (patch.desc as string | undefined) ?? spec?.desc ?? "",
  })
  return (
    <Staging onSave={keep} onCancel={spec ? undefined : onCancel}>
      {(st) => <Body st={st} spec={spec} at={at} index={index} states={states} live={live} rules={rules} onDirty={onDirty} />}
    </Staging>
  )
}

function Body({ st, spec, at, index, states, live, rules, onDirty }: {
  st: Staged; spec?: BranchSpec; at: { program: string; state: string }; index: number; states: string[]; live?: Live; rules: string[]; onDirty?: () => void
}) {
  const was  = spec?.when ?? []
  const sensors = useDrag()
  const [blank, setBlank] = useState<number[]>([])  // rows picked as a rule, with none chosen yet
  const last = useRef(was.length)                   // the row just added, opened to type in
  const hold = (key: string, value: unknown, kept: unknown) => (onDirty?.(), st.put(key, value, kept))
  const when = (st.patch.when as string[] | undefined) ?? was
  const goto = (st.patch.goto as string | undefined) ?? spec?.goto ?? states[0] ?? ""
  const set  = (next: string[]) => hold("when", next, was)
  const put  = (i: number, text: string) => set(when.map((x, j) => (j === i ? text : x)))
  const gone = (i: number) => (setBlank(blank.filter((b) => b !== i).map((b) => (b > i ? b - 1 : b))), set(when.filter((_, j) => j !== i)))
  const leave = useLeave((e) => e.over && e.active.id !== e.over.id && (setBlank([]), set(arrayMove(when, Number(e.active.id) - 1, Number(e.over.id) - 1))), (e) => gone(Number(e.active.id) - 1))
  const kindOf = (w: string, i: number) => rules.includes(w) || !!heldOf(live, w).rule || blank.includes(i) ? "rule" : "expr"
  return (
    <>
      <DialogHeader>
        <DialogTitle className="pr-24 font-mono break-all">{at.program}.{at.state}.transitions[{index}]</DialogTitle>
        <DialogDescription asChild>
          <div><Editable label="Description" long clamp placeholder="No description" {...st.field("desc", spec?.desc ?? "")} onType={(t) => hold("desc", t, spec?.desc ?? "")} /></div>
        </DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 border-t pt-4 text-xs">
        <span className="font-medium">Goto</span>
        <span>
          <Pick label="Goto" value={goto} arrow changed={"goto" in st.patch}
                options={(states.includes(goto) ? states : [...states, goto]).filter(Boolean).map((s) => [s, <span key={s} className="font-mono">{humane(s)}</span>])}
                onPick={(s) => hold("goto", s, spec?.goto ?? states[0] ?? "")}
                className="rounded-md border bg-muted px-3 py-1 font-mono text-xs no-underline hover:no-underline">
            <span className="font-mono">{humane(goto) || "a state"}</span>
          </Pick>
        </span>
        <span className="font-medium">When</span>
        <span className="flex h-6 items-center justify-between">
          <span className="text-muted-foreground">all must hold</span>
          <Button type="button" size="xs" variant="ghost" className="-mr-2 text-muted-foreground" onClick={() => (last.current = when.length, set([...when, ""]))}><Plus /> Condition</Button>
        </span>
      </div>
      <section className="flex flex-col gap-1.5 text-xs">
        <div ref={leave.ref} className="rounded-md border">
          <div className={cn(COLS, "bg-muted/40 py-1 pr-9 pl-7 text-muted-foreground")}><span>Type</span><span>Condition</span><span className="text-center">Now</span></div>
          <DndContext sensors={sensors} collisionDetection={closestCenter} {...leave.props}>
            <SortableContext items={when.map((_, i) => i + 1)} strategy={verticalListSortingStrategy}>
              {when.map((w, i) => {
                const kind = kindOf(w, i)
                const { rule, holds } = heldOf(live, w)
                return (
                  <ConditionRow key={i} id={i + 1} mark={i >= was.length ? "added" : w !== was[i] ? "changed" : undefined} onDelete={() => gone(i)}>
                    <Pick label="Type" value={kind} options={KINDS.map(([k, means]) => [k, <span key={k} className="inline-flex items-center gap-2">{chip(k)}<span className="text-muted-foreground">{means}</span></span>])}
                          onPick={(k) => (setBlank(k === "rule" ? [...blank, i] : blank.filter((b) => b !== i)), put(i, ""), (last.current = i))} arrow>{chip(kind)}</Pick>
                    {kind === "rule" ? (
                      <span className="flex min-w-0 items-center gap-2">
                        <Pick label="Rule" value={w} arrow options={rules.map((n) => [n, <span key={n} className="font-mono">{n}</span>])}
                              onPick={(n) => (setBlank(blank.filter((b) => b !== i)), put(i, n))}><Expr>{w || "Pick a rule"}</Expr></Pick>
                        <span className="truncate text-muted-foreground">{rule?.desc}</span>
                      </span>
                    ) : (
                      <Editable key={`${i}-${kind}`} label="Condition" code long clamp boxed list={NAMES} placeholder="answer == 0" className="w-full" value={w} changed={i < was.length && w !== was[i]} editing={w === "" && i === last.current}
                                onSave={async (t) => (put(i, t), null)} onType={(t) => put(i, t)} />
                    )}
                    <span className="flex justify-center"><Truth value={holds} /></span>
                  </ConditionRow>
                )
              })}
            </SortableContext>
            {leave.ghost((id) => <>{chip(kindOf(when[id - 1] ?? "", id - 1))}<Expr className="truncate">{when[id - 1]}</Expr></>)}
          </DndContext>
          {when.length === 0 && <p className="px-2 py-1.5 text-muted-foreground">None: it's the way out when no other holds.</p>}
        </div>
      </section>
    </>
  )
}
