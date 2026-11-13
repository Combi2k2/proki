// Notes: what you noted down, by the bucket @notes sorted it into, each bucket a table: its title, its
// content, when, and where it went. A click opens the note: its title, its content (shown as markdown,
// changed where it is), where it went and when; there you move it, sort it now, file it yourself or
// delete it. "New" makes one: its bucket, title and content. Each bucket has its icon and colour. Todos go
// on to the task planner: each says where it went (the link, a click opens it), or that the planner has
// yet to take it.

import { useCallback, useEffect, useState } from "react"
import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { ArrowRightLeft, Clock, Inbox, Lightbulb, Link2, ListTodo, MessageCircle, Plus } from "lucide-react"
import { PageHeader, SearchBox } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { ago, type Bucket, type Note, type View } from "@/lib/proki"
import { Editable, Pick, typing } from "@/views/in-place"
import { Corner } from "@/views/resources"

type Kept = "Idea" | "Thought"
type Shown = "Unsorted" | "Todo" | Kept
type Change = (request: object) => void

const KEPT: Record<Shown, { title: string; other: Kept | null; placeholder: string; empty: string; icon: typeof Lightbulb; tint: string }> = {
  "Unsorted": { title: "Unsorted", other: null, placeholder: "A note, for @notes to sort…", icon: Inbox, tint: "text-slate-500 dark:text-slate-400",
             empty: "Notes waiting to be sorted." },
  "Todo": { title: "Todos", other: null, placeholder: "Something to do, for the planner…", icon: ListTodo, tint: "text-sky-600 dark:text-sky-400",
            empty: "Notes sorted as todos land here, for the planner to make tasks of." },
  "Idea": { title: "Ideas", other: "Thought", placeholder: "An idea worth keeping…", icon: Lightbulb, tint: "text-amber-500 dark:text-amber-400",
            empty: "Notes sorted as ideas land here." },
  "Thought": { title: "Thoughts", other: "Idea", placeholder: "A thought, to let it go…", icon: MessageCircle, tint: "text-violet-600 dark:text-violet-400",
               empty: "Notes sorted as thoughts land here." },
}

/** What markdown looks like here: the text as it comes, a little set apart. */
const MARKDOWN = cn("text-sm [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-xs",
                    "[&_h1]:text-base [&_h1]:font-semibold [&_h2]:font-semibold [&_h3]:font-semibold [&_li]:my-0.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-1 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-2",
                    "[&_table]:text-xs [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_ul]:list-disc [&_ul]:pl-5 [&>:first-child]:mt-0 [&>:last-child]:mb-0")

export function NotesView({ onGo }: { onGo: (to: View, card?: number) => void }) {
  const [buckets, setBuckets] = useState<Record<Bucket, Note[]>>({ "Unsorted": [], "Todo": [], "Idea": [], "Thought": [] })
  const [bucket, setBucket] = useState<Shown>("Idea")
  const [opened, setOpened] = useState<number | null>(null)  // the note whose dialog is open
  const [making, setMaking] = useState(false)  // the dialog to make a note is open
  const [find, setFind] = useState("")
  const [error, setError] = useState("")

  const load = useCallback(async () => {
    const answer = await window.proki.notes({ op: "read" })
    if (answer.error) return setError(answer.error)
    setError("")
    setBuckets(answer)
  }, [])

  useEffect(() => {
    load()
    window.addEventListener("focus", load)
    return () => window.removeEventListener("focus", load)
  }, [load])

  const change: Change = async (request) => {
    const answer = await window.proki.notes(request)
    if (answer.error) setError(answer.error)
    load()
  }

  const words = find.trim().toLowerCase()
  const shown = [...buckets[bucket]].reverse().filter((n) => !words || `${n.title} ${n.text}`.toLowerCase().includes(words))  // newest first
  const { title, empty, icon: Icon } = KEPT[bucket]
  const waiting = buckets.Todo.filter((n) => !n.link).length
  const note = shown.find((n) => n.id === opened)

  return (
    <div className="mx-auto max-w-5xl px-8 pt-7 pb-8 *:mx-auto *:max-w-4xl">
      <PageHeader title="Notes & ideas" className="mb-5"
                  sub={waiting > 0 ? `${waiting} todo${waiting > 1 ? "s" : ""} waiting for the planner` : "Write it down, sort it later."}>
        <Button size="sm" title="New note" onClick={() => setMaking(true)}><Plus data-icon="inline-start" /> New</Button>
        <SearchBox value={find} onChange={setFind} label="Search the notes" />
      </PageHeader>

      <Tabs value={bucket} onValueChange={(v) => (setBucket(v as Shown), setOpened(null))} className="mb-4">
        <TabsList>
          {(Object.keys(KEPT) as Shown[]).map((b) => (
            <TabsTrigger key={b} value={b}>{KEPT[b].title} <span className="text-muted-foreground tabular-nums">{buckets[b].length}</span></TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
      {shown.length === 0 ? (
        <Empty className="mt-6">
          <EmptyHeader>
            <EmptyMedia variant="icon"><Icon /></EmptyMedia>
            <EmptyTitle>{words ? "No note matches" : bucket === "Unsorted" ? "Nothing to sort" : `No ${title.toLowerCase()} yet`}</EmptyTitle>
            <EmptyDescription>{words ? "Try another word." : empty}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="rounded-md border">
          <Table className="table-fixed text-xs">
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="w-40">Title</TableHead>
                <TableHead>Content</TableHead>
                <TableHead className="w-28">Time</TableHead>
                <TableHead className="w-28">Link</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shown.map((n) => (
                <TableRow key={n.id} className="cursor-pointer" onClick={() => setOpened(n.id)}>
                  <TableCell className={cn("truncate font-medium", !n.title && "font-normal text-muted-foreground")}><Icon aria-label={KEPT[bucket].title.slice(0, -1) || bucket} className={cn("mr-1.5 inline size-3.5 align-text-bottom", KEPT[bucket].tint)} /><button type="button" className="rounded-sm text-left" aria-label={`Open note: ${n.title || "No title"}`} onClick={(e) => { e.stopPropagation(); setOpened(n.id) }}>{n.title || "No title"}</button></TableCell>
                  <TableCell className="truncate text-muted-foreground" title={n.text}>{n.text.replace(/\s+/g, " ")}</TableCell>
                  <TableCell className="truncate text-muted-foreground">{ago(n.at)}</TableCell>
                  <TableCell className="truncate">
                    {n.link && <button type="button" onClick={(e) => (e.stopPropagation(), go(n.link!, onGo))} title="Open where it went"
                                       className="max-w-full truncate font-mono underline decoration-muted-foreground decoration-dotted underline-offset-4 hover:decoration-solid">{n.link}</button>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {note && <NoteDialog note={note} bucket={bucket} onChange={change} onGo={onGo} onClose={() => setOpened(null)} />}
      {making && <NewNote bucket={bucket} onMake={async (request) => { await change({ op: "add", ...request }); setBucket(request.bucket as Shown); setMaking(false) }} onClose={() => setMaking(false)} />}
    </div>
  )
}

/** A link a note keeps, followed: a page's path ("tasks/12": that page, that card). */
const go = (link: string, onGo: (to: View, card?: number) => void) => {
  const [to, card] = link.split("/")
  onGo(to as View, /^\d+$/.test(card ?? "") ? Number(card) : undefined)
}

/** A note's content, as markdown; a click changes it, in a box: Save (⌘ Enter) keeps it, Cancel (Escape) puts it back. */
function Content({ note, bucket, onChange }: { note: Note; bucket: Bucket; onChange: Change }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(note.text)
  useEffect(() => setText(note.text), [note.text])
  const save = () => {
    setEditing(false)
    if (text.trim() && text !== note.text) onChange({ op: "change", bucket, id: note.id, text: text.trim() })
    else setText(note.text)
  }
  if (!editing) return (
    <button type="button" onClick={() => setEditing(true)} title="Click to change" aria-label="Content, change"
            className={cn("w-full rounded-md px-1 py-1 text-left hover:bg-muted/60", MARKDOWN)}>
      <Markdown remarkPlugins={[remarkGfm]}>{note.text}</Markdown>
    </button>
  )
  return (
    <div className="flex flex-col gap-2">
      <Textarea autoFocus value={text} aria-label="Content" onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save()
                  if (e.key === "Escape") (e.preventDefault(), e.stopPropagation(), setText(note.text), setEditing(false))
                }} className="field-sizing-content max-h-72 min-h-24 font-mono text-xs" />
      <div className="flex items-center gap-1">
        <Button size="sm" onClick={save}>Save</Button>
        <Button size="sm" variant="ghost" onClick={() => (setText(note.text), setEditing(false))}>Cancel</Button>
        <span className="ml-auto text-[11px] text-muted-foreground">⌘ Enter to save · markdown</span>
      </div>
    </div>
  )
}

/** A note over its table: its bucket's icon and its title, with the bin and the close in the corner; its content, as markdown; the link it keeps; when. Move it, sort it now, file it, from the foot. */
function NoteDialog({ note, bucket, onChange, onGo, onClose }: {
  note: Note; bucket: Shown; onChange: Change; onGo: (to: View, card?: number) => void; onClose: () => void
}) {
  const { other, icon: Icon, tint } = KEPT[bucket]
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg" onEscapeKeyDown={typing}>
        <DialogHeader className="pr-20">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Icon aria-label={bucket} className={cn("size-4 shrink-0", tint)} />
            <Editable label="Title" value={note.title} placeholder="No title" clamp onSave={async (t) => (onChange({ op: "change", bucket, id: note.id, title: t.trim() }), null)} />
          </DialogTitle>
          <DialogDescription className="sr-only">Its title, its content, its link and when.</DialogDescription>
        </DialogHeader>
        <Corner what="note" name={note.title || "untitled"} onDelete={() => (onClose(), onChange({ op: "remove", bucket, id: note.id }))} />
        <hr />
        <Content note={note} bucket={bucket} onChange={onChange} />
        <hr />
        <div className="flex flex-col gap-2 text-xs">
          <div className="flex items-center gap-2">
            <Link2 aria-label="Link" className="size-3.5 shrink-0 text-muted-foreground" />
            {note.link
              ? <button type="button" onClick={() => go(note.link!, onGo)} title="Open where it went"
                        className="min-w-0 truncate font-mono underline decoration-muted-foreground decoration-dotted underline-offset-4 hover:decoration-solid">{note.link}</button>
              : <span className="text-muted-foreground">{bucket === "Todo" ? "None yet: for the planner" : "None"}</span>}
          </div>
          <div className="flex items-center gap-2" title={new Date(note.at).toLocaleString()}>
            <Clock aria-label="Time" className="size-3.5 shrink-0 text-muted-foreground" />
            {ago(note.at)}
            {note.guess && <span className="text-muted-foreground">· jev: {note.guess}{note.conf != null && ` (${Math.round(note.conf * 100)}%)`}</span>}
          </div>
        </div>
        {(other || bucket === "Unsorted") && (
          <div className="flex flex-wrap items-center justify-end gap-2">
            {other && <Button size="sm" variant="ghost" onClick={() => (onClose(), onChange({ op: "move", id: note.id, from: bucket, to: other }))}><ArrowRightLeft data-icon="inline-start" /> {KEPT[other].title.slice(0, -1)}</Button>}
            {bucket === "Unsorted" && <Button size="sm" variant="ghost" onClick={() => onChange({ op: "change", bucket, id: note.id, due: new Date().toISOString() })}>Sort now</Button>}
            {bucket === "Unsorted" && (
              <select value="" aria-label="file it" onChange={(e) => e.target.value && (onClose(), onChange({ op: "move", id: note.id, from: "Unsorted", to: e.target.value }))}
                      className="h-7 rounded-md border bg-transparent px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
                <option value="">File as…</option>
                {(["Todo", "Idea", "Thought"] as const).map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

/** A note to make, laid out as a note is: its bucket's icon and its title, a divider, its content, and which bucket (`bucket`: the tab you're in). Nothing is kept until Keep it. */
function NewNote({ bucket, onMake, onClose }: { bucket: Shown; onMake: (request: { bucket: string; title: string; text: string }) => Promise<void>; onClose: () => void }) {
  const [into, setInto]   = useState<Shown>(bucket)
  const [title, setTitle] = useState("")
  const [text, setText]   = useState("")
  const { icon: Icon, tint, placeholder } = KEPT[into]
  const make = () => text.trim() && onMake({ bucket: into, title: title.trim(), text: text.trim() })
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg" onEscapeKeyDown={typing}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 pr-8 text-base">
            <Icon aria-hidden className={cn("size-4 shrink-0", tint)} />
            <Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" aria-label="Title" className="h-8 text-sm" />
          </DialogTitle>
          <DialogDescription className="sr-only">Its bucket, its title and its content.</DialogDescription>
        </DialogHeader>
        <hr />
        <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} aria-label="Content"
                  onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && make()} className="field-sizing-content max-h-72 min-h-28 font-mono text-xs" />
        <hr />
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">Bucket</span>
          <Pick label="Bucket" value={into} arrow onPick={(v) => setInto(v as Shown)}
                options={(Object.keys(KEPT) as Shown[]).map((b) => { const B = KEPT[b].icon; return [b, <><B className={cn("size-3.5", KEPT[b].tint)} />{KEPT[b].title.replace(/s$/, "")}</>] })} />
          <span className="ml-auto text-[11px] text-muted-foreground">⌘ Enter to keep · markdown</span>
          <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={make} disabled={!text.trim()}>Keep it</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
