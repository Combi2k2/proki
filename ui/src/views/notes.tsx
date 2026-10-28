// Notes: what you noted down, by the bucket @notes sorted it into. Ideas and thoughts are kept
// here: edit one in place, move it to the other bucket, delete it, or add one, into the tab's
// bucket or the unsorted ones ("Sort it later", sorted with the others). The unsorted ones have
// their tab too: each note with when @notes sorts it and jev's guess, to edit, sort now, file
// yourself (a todo too) or delete. Todos go on to the task planner: each says where it went
// (its group's card, a click opens it), or that the planner has yet to take it.

import { useCallback, useEffect, useState } from "react"
import { ArrowRight, ArrowRightLeft, Clock, Inbox, Lightbulb, ListTodo, MessageCircle, Trash2 } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { ago, type Bucket, type Note, type View } from "@/lib/proki"

type Kept = "Idea" | "Thought"
type Shown = "Unsorted" | "Todo" | Kept

const KEPT: Record<Shown, { title: string; other: Kept | null; placeholder: string; empty: string; icon: typeof Lightbulb }> = {
  "Unsorted": { title: "Unsorted", other: null, placeholder: "A note, for @notes to sort…", icon: Inbox,
             empty: "Notes waiting to be sorted." },
  "Todo": { title: "Todos", other: null, placeholder: "Something to do, for the planner…", icon: ListTodo,
            empty: "Notes sorted as todos land here, for the planner to make tasks of." },
  "Idea": { title: "Ideas", other: "Thought", placeholder: "An idea worth keeping…", icon: Lightbulb,
            empty: "Notes sorted as ideas land here." },
  "Thought": { title: "Thoughts", other: "Idea", placeholder: "A thought, to let it go…", icon: MessageCircle,
               empty: "Notes sorted as thoughts land here." },
}

export function NotesView({ onGo }: { onGo: (to: View, card?: number) => void }) {
  const [buckets, setBuckets] = useState<Record<Bucket, Note[]>>({ "Unsorted": [], "Todo": [], "Idea": [], "Thought": [] })
  const [groups, setGroups] = useState<Record<number, string>>({})  // each group's name, by its id: where a todo went
  const [bucket, setBucket] = useState<Shown>("Idea")
  const [text, setText] = useState("")
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    const answer = await window.proki.notes({ op: "read" })
    if (answer.error) return setError(answer.error)
    setError("")
    setBuckets(answer)
    const board = await window.proki.tasks({ op: "read" })
    if (!board.error) setGroups(Object.fromEntries(board.groups.map((g: { id: number; name: string }) => [g.id, g.name])))
  }, [])

  useEffect(() => {
    load()
    window.addEventListener("focus", load)
    return () => window.removeEventListener("focus", load)
  }, [load])

  const change = async (request: object) => {
    const answer = await window.proki.notes(request)
    if (answer.error) setError(answer.error)
    load()
  }

  const keep = async (into: Bucket = bucket) => {
    if (!text.trim()) return
    await change({ op: "add", bucket: into, text: text.trim() })
    setText("")
  }

  const shown = [...buckets[bucket]].reverse()  // newest first
  const { title, other, placeholder, empty, icon: Icon } = KEPT[bucket]
  const waiting = buckets.Todo.filter((n) => !n.link).length

  return (
    <div className="mx-auto max-w-2xl px-8 pt-7 pb-8">
      <PageHeader title="Notes & ideas" className="mb-5"
                  sub={waiting > 0 ? `${waiting} todo${waiting > 1 ? "s" : ""} waiting for the planner` : "Write it down, sort it later."} />

      <Tabs value={bucket} onValueChange={(v) => setBucket(v as Shown)} className="mb-4">
        <TabsList>
          {(Object.keys(KEPT) as Shown[]).map((b) => (
            <TabsTrigger key={b} value={b}>{KEPT[b].title} <span className="text-muted-foreground tabular-nums">{buckets[b].length}</span></TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Card size="sm" className="mb-6">
        <CardContent className="flex flex-col gap-2">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder}
                    onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && keep()} className="min-h-20 resize-none" />
          <div className="flex justify-end gap-2">
            {bucket !== "Unsorted" && <Button size="sm" variant="ghost" onClick={() => keep("Unsorted")} disabled={!text.trim()}
                    title="Unsorted, sorted with the others">Sort it later</Button>}
            <Button size="sm" onClick={() => keep()} disabled={!text.trim()}>Keep it</Button>
          </div>
        </CardContent>
      </Card>

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
      {shown.length === 0 ? (
        <Empty className="mt-6">
          <EmptyHeader>
            <EmptyMedia variant="icon"><Icon /></EmptyMedia>
            <EmptyTitle>{bucket === "Unsorted" ? "Nothing to sort" : `No ${title.toLowerCase()} yet`}</EmptyTitle>
            <EmptyDescription>{empty}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="flex flex-col gap-3">
          {shown.map((note) => other
            ? <NoteCard key={note.id} note={note} bucket={bucket as Kept} other={other} onChange={change} />
            : bucket === "Todo"
              ? <TodoCard key={note.id} note={note} groups={groups} onChange={change} onGo={onGo} />
              : <UnsortedCard key={note.id} note={note} onChange={change} />)}
        </div>
      )}
    </div>
  )
}

/** A note's text, edited where it is: saved as you leave it. */
function NoteText({ note, bucket, onChange }: { note: Note; bucket: Bucket; onChange: (request: object) => void }) {
  const [text, setText] = useState(note.text)
  useEffect(() => setText(note.text), [note.text])

  return (
    <CardContent>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => text.trim() && text !== note.text && onChange({ op: "change", bucket, id: note.id, text: text.trim() })}
        className="field-sizing-content min-h-0 resize-none border-transparent bg-transparent px-0 shadow-none focus-visible:ring-0 dark:bg-transparent"
      />
    </CardContent>
  )
}

function NoteCard({ note, bucket, other, onChange }: { note: Note; bucket: Kept; other: Kept; onChange: (request: object) => void }) {
  return (
    <Card size="sm" className="group gap-1">
      <NoteText note={note} bucket={bucket} onChange={onChange} />
      <CardFooter className="gap-1 border-none bg-transparent pt-0 pb-3">
        <span className="mr-auto text-xs text-muted-foreground">{ago(note.at)}</span>
        <Button variant="ghost" size="xs" onClick={() => onChange({ op: "move", id: note.id, from: bucket, to: other })}
                className="text-muted-foreground opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 max-[760px]:opacity-100">
          <ArrowRightLeft /> {KEPT[other].title.slice(0, -1)}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="Delete note" onClick={() => onChange({ op: "remove", bucket, id: note.id })}
                className="text-muted-foreground opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 max-[760px]:opacity-100 hover:text-destructive">
          <Trash2 />
        </Button>
      </CardFooter>
    </Card>
  )
}

/** A todo: where it went, a click opens it (a group's card, by its name), or the planner's still to take it. */
function TodoCard({ note, groups, onChange, onGo }: { note: Note; groups: Record<number, string>; onChange: (request: object) => void;
                                                     onGo: (to: View, card?: number) => void }) {
  const [to, card] = note.link ? note.link.split("/") : []
  const id = /^\d+$/.test(card ?? "") ? Number(card) : undefined
  return (
    <Card size="sm" className="group gap-1">
      <NoteText note={note} bucket="Todo" onChange={onChange} />
      <CardFooter className="gap-1 border-none bg-transparent pt-0 pb-3">
        <span className="mr-auto text-xs text-muted-foreground">{ago(note.at)}{!note.link && " · for the planner"}</span>
        {note.link && (
          <Button variant="ghost" size="xs" onClick={() => onGo(to as View, id)} title="Open where it went">
            <ArrowRight /> {to === "tasks" && id !== undefined ? groups[id] ?? "its group" : note.link}
          </Button>
        )}
        <Button variant="ghost" size="icon-sm" aria-label="Delete note" onClick={() => onChange({ op: "remove", bucket: "Todo", id: note.id })}
                className="text-muted-foreground opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 max-[760px]:opacity-100 hover:text-destructive">
          <Trash2 />
        </Button>
      </CardFooter>
    </Card>
  )
}

/** A note not sorted yet: when @notes sorts it, and jev's guess (once it has asked). Sort it now,
 *  file it yourself, or delete it. */
function UnsortedCard({ note, onChange }: { note: Note; onChange: (request: object) => void }) {
  const due = note.sorts_at ? new Date(note.sorts_at) : null
  const now = due !== null && due.getTime() <= Date.now()
  return (
    <Card size="sm" className="group gap-1">
      <NoteText note={note} bucket="Unsorted" onChange={onChange} />
      <CardFooter className="flex-wrap gap-1 border-none bg-transparent pt-0 pb-3">
        <span className="mr-auto flex items-center gap-2 text-xs text-muted-foreground">
          {ago(note.at)}
          {due && (
            <span className={cn("flex items-center gap-1", now && "text-foreground")}
                  title={note.due ? "its own time" : "with the others"}>
              <Clock className="size-3" /> {now ? "sorted when you're next free" : `sorted ${when(due)}`}
            </span>
          )}
          {note.guess && <span>· jev: {note.guess}{note.conf != null && ` (${Math.round(note.conf * 100)}%)`}</span>}
        </span>
        {!now && (
          <Button variant="ghost" size="xs" onClick={() => onChange({ op: "change", bucket: "Unsorted", id: note.id, due: new Date().toISOString() })}
                  className="text-muted-foreground opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 max-[760px]:opacity-100">Sort now</Button>
        )}
        <select value="" aria-label="file it" onChange={(e) => e.target.value && onChange({ op: "move", id: note.id, from: "Unsorted", to: e.target.value })}
                className="h-6 rounded-md bg-transparent px-1 text-xs text-muted-foreground opacity-0 outline-none group-hover:opacity-100 group-focus-within:opacity-100 max-[760px]:opacity-100 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50">
          <option value="">File as…</option>
          {(["Todo", "Idea", "Thought"] as const).map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <Button variant="ghost" size="icon-sm" aria-label="Delete note" onClick={() => onChange({ op: "remove", bucket: "Unsorted", id: note.id })}
                className="text-muted-foreground opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 max-[760px]:opacity-100 hover:text-destructive">
          <Trash2 />
        </Button>
      </CardFooter>
    </Card>
  )
}

/** A time to come: "at 16:30" today, "tomorrow at 04:00", else its day. */
function when(t: Date): string {
  const time = t.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
  const days = Math.round((new Date(t).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86_400_000)
  if (days === 0) return `at ${time}`
  if (days === 1) return `tomorrow at ${time}`
  return `on ${t.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })} at ${time}`
}
