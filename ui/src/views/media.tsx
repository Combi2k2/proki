// Media: the pictures and sounds a popup can show and play, each on its own tab.
//
// Pictures are a grid and sounds a list, yours first, a page at a time as you scroll, grouped by
// the folder they came from, one group open at a time. Add your own files, or a folder of them,
// with the buttons or by dropping them anywhere on the page: each is copied into proki's data
// folder, named as its file was (a folder's: after the folder, "stickers/happy"). Rename one with its pencil: its key, what pokes and
// pools know it by, stays. Delete one with its bin (a second click confirms), or "Select"
// several and delete them at once: they're out at once, and gone for good a week later. One
// a poke, a question or a pool still uses stays, and says so.
//
// `MediaPicker` is the same grid or list in a window, to choose a poke's or a question's
// pictures or sounds.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { Check, FolderPlus, ImagePlus, ListChecks, Pause, Pencil, Play, Trash2, X } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { PageHeader } from "@/components/page"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ButtonGroup } from "@/components/ui/button-group"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { fileUrl, type MediaItem } from "@/lib/proki"
import { cn } from "@/lib/utils"

const PAGE = 60  // loaded at a time
const KINDS = [["image", "Pictures"], ["sound", "Sounds"]] as const
type Kind = (typeof KINDS)[number][0]

/** A library file, by its path on disk. */
export const file = fileUrl

/** The library, a page at a time (of `kind`): what's loaded, how many in all, and `more` to load the next page. */
function useLibrary(kind: Kind) {
  const [items, setItems] = useState<MediaItem[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState("")
  const loading = useRef(false)

  const load = useCallback(async (from: number) => {
    if (loading.current) return
    loading.current = true
    const answer = await window.proki.tool("get_media", { kind, offset: from, limit: PAGE })
    loading.current = false
    if (answer.error) return setError(answer.error)
    setItems((shown) => (from === 0 ? answer.media : [...shown, ...answer.media]))
    setTotal(answer.total)
  }, [kind])

  useEffect(() => {
    load(0)
  }, [load])

  const drop = (keys: string[]) => {
    setItems((shown) => shown.filter((i) => !keys.includes(i.key)))
    setTotal((n) => n - keys.length)
  }
  const rename = (key: string, name: string) => setItems((shown) => shown.map((i) => (i.key === key ? { ...i, name } : i)))
  return { items, total, error, reload: () => load(0), more: () => load(items.length), drop, rename }
}

export function MediaView() {
  const [kind, setKind] = useState<Kind>("image")
  const library = useLibrary(kind)
  const [selected, setSelected] = useState<string[] | null>(null)  // selecting, to delete
  const [status, setStatus] = useState("")
  const [dropping, setDropping] = useState(false)

  const add = async (paths: string[]) => {
    const keys: string[] = []
    for (const path of paths) {
      const answer = await window.proki.tool("add_media", { path })
      if (answer.error) return setStatus(`${path.split("/").pop()}: ${answer.error}`)
      keys.push(...(answer.keys ?? [answer.key!]))
    }
    setStatus(keys.length ? `Added ${count(keys.length)}.` : "")
    library.reload()
  }

  const remove = async (keys: string[]) => {
    const answer = await window.proki.tool("remove_media", { keys })
    if (answer.error) return setStatus(answer.error)
    library.drop(answer.removed)
    const kept = Object.values(answer.kept)
    setStatus([answer.removed.length ? `Deleted ${count(answer.removed.length)}: gone for good in a week.` : "",
               kept.length ? `${kept.length === 1 ? "One stays" : `${kept.length} stay`}: ${kept.join(" · ")}` : ""].filter(Boolean).join(" "))
    setSelected(null)
    library.reload()
  }

  const rename = async (key: string, name: string) => {
    const answer = await window.proki.tool("rename_media", { key, name })
    if (answer.error) return setStatus(answer.error)
    library.rename(key, name.trim())
    setStatus("")
  }

  useEffect(() => {  // files dropped come as paths, from the window
    const stop = window.proki.onDrop((kind, paths) => {
      setDropping(kind === "over")
      if (kind === "drop") add(paths)
    })
    return () => void stop.then((unlisten) => unlisten())
  }, [kind])  // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (keys: string[], key: string) => (keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key])

  return (
    <div className="relative mx-auto max-w-5xl px-8 pt-7 pb-8">
      <PageHeader title="Pictures & sounds" className="mb-5"
                  beside={<Tabs value={kind} onValueChange={(k) => { setKind(k as Kind); setSelected(null) }}>
                    <TabsList>{KINDS.map(([k, label]) => <TabsTrigger key={k} value={k}>{label}</TabsTrigger>)}</TabsList>
                  </Tabs>}
                  sub={<span className="tabular-nums">{library.total} in your library</span>}>
        {selected ? (
          <>
            <span className="text-xs text-muted-foreground">{selected.length} selected</span>
            <Button size="sm" variant="ghost" onClick={() => setSelected(null)}><X /> Cancel</Button>
            <Confirm title={`Delete ${count(selected.length)}?`} description="They're gone for good in a week." onConfirm={() => remove(selected)}>
              <Button size="sm" variant="destructive" disabled={!selected.length}><Trash2 /> Delete</Button>
            </Confirm>
          </>
        ) : (
          <>
            <Button size="sm" variant="outline" onClick={() => setSelected([])}><ListChecks /> Select</Button>
            <UploadButton onFiles={add} />
          </>
        )}
      </PageHeader>
      {(status || library.error) && <p className="mb-3 text-sm text-muted-foreground">{status || library.error}</p>}

      <Groups kind={kind} items={library.items}>
        {(item) => {
          const Item = kind === "image" ? Tile : Row
          return (
            <Item key={item.key} item={item}
                  chosen={selected ? selected.includes(item.key) : undefined}
                  onChoose={selected ? () => setSelected((s) => s && toggle(s, item.key)) : undefined}
                  onRename={(name) => rename(item.key, name)}
                  onRemove={() => remove([item.key])} />
          )
        }}
      </Groups>
      {library.items.length < library.total && <More onSeen={library.more} />}

      {dropping && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm">
          <p className="rounded-xl border-2 border-dashed border-primary px-8 py-6 text-sm font-medium">Drop pictures or sounds to add them</p>
        </div>
      )}
    </div>
  )
}

/** A window over the library of `kind`, to tick the keys a poke or a question draws from. */
export function MediaPicker({ kind, keys, onDone, onClose }: {
  kind: "image" | "sound"
  keys: string[]
  onDone: (keys: string[]) => void
  onClose: () => void
}) {
  const library = useLibrary(kind)
  const [chosen, setChosen] = useState(keys)
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{kind === "image" ? "Pictures" : "Sounds"}</DialogTitle>
          <DialogDescription>
            Tick the ones it may {kind === "image" ? "show" : "play"}: one is drawn each time. Add your own on the Media page.
          </DialogDescription>
        </DialogHeader>
        <div className="-mx-2 min-h-0 flex-1 overflow-y-auto px-2">
          <Groups kind={kind} items={library.items}>
            {(item) => {
              const Item = kind === "image" ? Tile : Row
              return (
                <Item key={item.key} item={item} chosen={chosen.includes(item.key)}
                      onChoose={() => setChosen((c) => (c.includes(item.key) ? c.filter((k) => k !== item.key) : [...c, item.key]))} />
              )
            }}
          </Groups>
          {library.items.length < library.total && <More onSeen={library.more} />}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{chosen.length} chosen</span>
          <div className="flex-1" />
          {chosen.length > 0 && <Button size="sm" variant="ghost" onClick={() => setChosen([])}>Clear</Button>}
          <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={() => onDone(chosen)}>Done</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

const EXTENSIONS = ["gif", "png", "jpg", "jpeg", "webp", "mp3", "wav", "ogg"]

function UploadButton({ onFiles }: { onFiles: (paths: string[]) => void }) {
  return (
    <ButtonGroup>
      <Button size="sm" onClick={async () => onFiles(await window.proki.pickFiles(EXTENSIONS))}><ImagePlus /> Add</Button>
      <Button size="sm" variant="outline" onClick={async () => { const at = await window.proki.pickFolder(); if (at) onFiles([at]) }}><FolderPlus /> Add a folder</Button>
    </ButtonGroup>
  )
}

/** The items by the folder they came from ("bugcat/sad": bugcat), else yours or proki's, in
 * the order they come; one group open at a time, the first at first. */
function Groups({ kind, items, children }: { kind: Kind; items: MediaItem[]; children: (item: MediaItem) => ReactNode }) {
  const groups = new Map<string, MediaItem[]>()
  for (const item of items) {
    const name = item.name.includes("/") ? item.name.split("/")[0] : item.added_by === "you" ? "Yours" : "Proki's"
    groups.set(name, [...(groups.get(name) ?? []), item])
  }
  const [open, setOpen] = useState<string | null>(null)
  const shown = open === "" || (open && groups.has(open)) ? open : [...groups.keys()][0] ?? ""  // one gone (another tab): the first
  return (
    <Accordion type="single" collapsible value={shown} onValueChange={(v) => setOpen(v)} className="gap-2">
      {[...groups].map(([name, held]) => (
        <AccordionItem key={name} value={name} className="rounded-xl border not-last:border-b">
          <AccordionTrigger className="items-center px-3 hover:no-underline">
            <span className="flex items-center gap-2">{name}<span className="text-xs font-normal text-muted-foreground tabular-nums">{held.length}</span></span>
          </AccordionTrigger>
          <AccordionContent className="h-auto px-3">
            <Items kind={kind}>{held.map(children)}</Items>
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  )
}

/** The library's items as `kind` shows them: pictures a grid, sounds a list. */
function Items({ kind, children }: { kind: Kind; children: ReactNode }) {
  return kind === "image"
    ? <div className="grid grid-cols-[repeat(auto-fill,minmax(104px,1fr))] gap-3">{children}</div>
    : <div className="divide-y rounded-xl border bg-card">{children}</div>
}

type ItemProps = {
  item: MediaItem
  chosen?: boolean                     // ticking: whether it's ticked
  onChoose?: () => void                // ticking: a click toggles it (none: it's dimmed, it can't be ticked)
  onRename?: (name: string) => void    // not ticking: its pencil
  onRemove?: () => void                // not ticking: its bin, a second click confirms
}

/** A picture: a tile, its name under it. */
function Tile({ item, chosen, onChoose, onRename, onRemove }: ItemProps) {
  const ticking = chosen !== undefined
  return (
    <div role={onChoose ? "button" : undefined} onClick={onChoose} title={item.name}
         className={cn("group relative flex flex-col gap-1.5 rounded-xl border bg-card p-2 transition-colors",
                       onChoose && "cursor-pointer hover:border-foreground/30",
                       ticking && !onChoose && "opacity-40",
                       chosen && "border-primary ring-2 ring-primary/30")}>
      <img src={file(item.file) || undefined} alt="" loading="lazy" className="aspect-square w-full rounded-md bg-muted/60 object-contain" />
      <Name item={item} onRename={ticking ? undefined : onRename} />
      {item.added_by === "you" && <Badge variant="secondary" className="absolute top-3 left-3 px-1.5 text-[10px]">yours</Badge>}
      {chosen && <span className="absolute top-3 right-3 rounded-full bg-primary p-0.5 text-primary-foreground"><Check className="size-3" /></span>}
      {!ticking && onRemove && <Bin onRemove={onRemove} className="absolute top-3 right-3" />}
    </div>
  )
}

/** A sound: a row, its play button, its name, whose it is. */
function Row({ item, chosen, onChoose, onRename, onRemove }: ItemProps) {
  const ticking = chosen !== undefined
  return (
    <div role={onChoose ? "button" : undefined} onClick={onChoose}
         className={cn("group flex items-center gap-3 px-3 py-2",
                       onChoose && "cursor-pointer hover:bg-muted/50",
                       ticking && !onChoose && "opacity-40")}>
      {ticking && (
        <span className={cn("flex size-4 shrink-0 items-center justify-center rounded border",
                            chosen && "border-primary bg-primary text-primary-foreground")}>
          {chosen && <Check className="size-3" />}
        </span>
      )}
      <PlayButton item={item} />
      <Name item={item} onRename={ticking ? undefined : onRename} className="flex-1 text-sm" />
      {item.added_by === "you" && <Badge variant="secondary" className="px-1.5 text-[10px]">yours</Badge>}
      {!ticking && onRemove && <Bin onRemove={onRemove} />}
    </div>
  )
}

/** An item's name, without the folder its group says. With `onRename`: its pencil (on hover)
 * makes it a field, the whole name in it, Enter or leaving it saves, Escape doesn't. */
function Name({ item, onRename, className }: { item: MediaItem; onRename?: (name: string) => void; className?: string }) {
  const [editing, setEditing] = useState(false)
  const done = (name: string | null) => {
    setEditing(false)
    if (name !== null && name.trim() && name.trim() !== item.name) onRename?.(name)
  }
  if (editing) {
    return (
      <Input autoFocus defaultValue={item.name} className={cn("h-7 min-w-0 px-2 text-xs", className)}
             onClick={(e) => e.stopPropagation()}
             onBlur={(e) => done(e.currentTarget.value)}
             onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); if (e.key === "Escape") done(null) }} />
    )
  }
  return (
    <div className={cn("flex min-w-0 items-center gap-1 text-xs text-muted-foreground", className)}>
      <span className="truncate" title={item.name}>{item.name.slice(item.name.indexOf("/") + 1)}</span>  {/* its group says the folder */}
      {onRename && (
        <button aria-label="Rename" onClick={(e) => { e.stopPropagation(); setEditing(true) }}
                className="shrink-0 rounded p-0.5 opacity-0 group-hover:opacity-100 hover:bg-muted hover:text-foreground">
          <Pencil className="size-3" />
        </button>
      )}
    </div>
  )
}

/** An item's bin: asks first, then deletes. */
function Bin({ onRemove, className }: { onRemove: () => void; className?: string }) {
  return (
    <span onClick={(e) => e.stopPropagation()}>
      <Confirm title="Delete it?" description="It's gone for good in a week." onConfirm={onRemove}>
        <Button size="icon-xs" variant="secondary" aria-label="Delete"
                className={cn("bg-background/80 text-muted-foreground opacity-0 group-hover:opacity-100 hover:text-destructive", className)}><Trash2 /></Button>
      </Confirm>
    </span>
  )
}

function PlayButton({ item }: { item: MediaItem }) {
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null)
  useEffect(() => () => audio?.pause(), [audio])
  const play = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (audio) { audio.pause(); return setAudio(null) }
    const a = new Audio(file(item.file))
    a.onended = () => setAudio(null)
    a.play()
    setAudio(a)
  }
  return (
    <button onClick={play} aria-label={audio ? "Stop" : "Play"} className="shrink-0 rounded-full border p-1.5 hover:bg-muted">
      {audio ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
    </button>
  )
}

/** The end of what's loaded: when it's seen, the next page loads. */
function More({ onSeen }: { onSeen: () => void }): ReactNode {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const seen = new IntersectionObserver((entries) => entries[0]?.isIntersecting && onSeen(), { rootMargin: "400px" })
    if (end.current) seen.observe(end.current)
    return () => seen.disconnect()
  }, [onSeen])
  return <div ref={end} className="py-6 text-center text-xs text-muted-foreground">Loading…</div>
}

const count = (n: number) => (n === 1 ? "1 file" : `${n} files`)
