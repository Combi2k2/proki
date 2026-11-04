// Support: proki's code on GitHub, a coffee for its developer, and a suggestion of
// yours, with pictures of it if you like. A suggestion is kept on this computer until it reaches the developer, sent at once if
// you're online, else as soon as you are (the main window tries again, see pages/main.tsx).

import { useEffect, useRef, useState } from "react"
import { ArrowUpRight, Check, Coffee, ImagePlus, Send, X } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import github from "@/assets/brands/github.svg?raw"

const LONGEST  = 5000  // characters a suggestion can have (proki/tools/suggestions.py)
const PICTURES = 3     // pictures it can have (the same)
const WIDEST   = 1600  // pixels a picture's longer side is shrunk to, before it's kept

/** An image file as a JPEG data URL, its longer side WIDEST at most. */
async function shrunk(file: File): Promise<string> {
  const image  = await createImageBitmap(file)
  const scale  = Math.min(1, WIDEST / Math.max(image.width, image.height))
  const canvas = Object.assign(document.createElement("canvas"), { width: Math.round(image.width * scale), height: Math.round(image.height * scale) })
  const pen    = canvas.getContext("2d")!
  pen.fillStyle = "#fff"  // what's see-through, on white rather than black
  pen.fillRect(0, 0, canvas.width, canvas.height)
  pen.drawImage(image, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL("image/jpeg", 0.85)
}

export function SupportView() {
  const [text, setText]         = useState("")
  const [contact, setContact]   = useState("")
  const [pictures, setPictures] = useState<string[]>([])
  const [sending, setSending]   = useState(false)
  const [waiting, setWaiting]   = useState(0)
  const [said, setSaid]         = useState<{ sent: boolean } | { error: string } | null>(null)

  const picker = useRef<HTMLInputElement>(null)

  useEffect(() => void window.proki.tool("send_suggestions").then((r) => !r.error && setWaiting(r.waiting)), [])

  const add = async (files: Iterable<File>) => {
    const images = [...files].filter((f) => f.type.startsWith("image/")).slice(0, PICTURES - pictures.length)
    if (!images.length) return
    try {
      const made = await Promise.all(images.map(shrunk))
      setPictures((held) => [...held, ...made].slice(0, PICTURES))
      setSaid(null)
    } catch {
      setSaid({ error: "That picture couldn't be opened. Try a PNG or a JPEG." })
    }
  }

  const send = async () => {
    setSending(true)
    const answer = await window.proki.tool("suggest", { text, ...(contact.trim() ? { contact } : {}), ...(pictures.length ? { pictures } : {}) })
    setSending(false)
    if (answer.error) return setSaid({ error: answer.error })
    setWaiting(answer.waiting)
    setSaid({ sent: !answer.waiting })
    setText("")
    setPictures([])
  }

  return (
    <div className="mx-auto max-w-5xl px-8 pt-7 pb-24 *:mx-auto *:max-w-[38rem]">
      <PageHeader title="Support" sub="Proki is open source, and made by one person. Any of these helps it get better." className="mb-6" />

      <div className="mb-10 grid gap-3 sm:grid-cols-2">
        <button onClick={() => window.proki.link("github")}
                className="group flex items-start gap-3 rounded-xl border bg-card px-4 py-3.5 text-left transition-colors hover:bg-accent/60 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
          <span aria-hidden className="mt-0.5 size-5 shrink-0 [&>svg]:size-full" dangerouslySetInnerHTML={{ __html: github }} />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1 text-sm font-semibold">The code, on GitHub <ArrowUpRight aria-hidden className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" /></span>
            <span className="mt-0.5 block text-xs text-muted-foreground">Report a bug, or send a change of your own.</span>
          </span>
        </button>
        <button onClick={() => window.proki.link("coffee")}
                className="group flex items-start gap-3 rounded-xl border bg-card px-4 py-3.5 text-left transition-colors hover:bg-accent/60 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
          <Coffee aria-hidden className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1 text-sm font-semibold">Buy me a coffee <ArrowUpRight aria-hidden className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" /></span>
            <span className="mt-0.5 block text-xs text-muted-foreground">A small thanks, if Proki makes your days easier.</span>
          </span>
        </button>
      </div>

      <section aria-labelledby="suggest" className="rounded-xl border bg-card">
        <header className="border-b px-5 py-3.5">
          <h2 id="suggest" className="text-sm font-semibold">Suggest something</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Something that got in your way, felt slow, or could simply be nicer. It goes straight to the developer.</p>
        </header>
        <form className="flex flex-col gap-4 px-5 py-4" onSubmit={(e) => (e.preventDefault(), text.trim() && !sending && send())}
              onPaste={(e) => void add(e.clipboardData.files)}>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium">What could be better?</span>
            <Textarea value={text} onChange={(e) => (setText(e.target.value), setSaid(null))} maxLength={LONGEST} rows={5} className="min-h-28 resize-none"
                      placeholder="When I… I expected… instead…" />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium">How to reach you <span className="font-normal text-muted-foreground">(if you'd like an answer)</span></span>
            <Input value={contact} onChange={(e) => setContact(e.target.value)} maxLength={200} placeholder="An email, or a GitHub name" autoComplete="email" />
          </label>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium">Pictures <span className="font-normal text-muted-foreground">(up to {PICTURES}: add one, or paste a screenshot)</span></span>
            <div className="flex flex-wrap gap-2">
              {pictures.map((picture, i) => (
                <div key={picture} className="relative size-20 overflow-hidden rounded-lg border bg-muted">
                  <img src={picture} alt={`Picture ${i + 1}`} className="size-full object-cover" />
                  <button type="button" aria-label={`Take out picture ${i + 1}`} onClick={() => setPictures(pictures.filter((_, j) => j !== i))}
                          className="absolute top-1 right-1 rounded-full bg-background/90 p-0.5 text-muted-foreground shadow-sm hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
                    <X aria-hidden className="size-3" />
                  </button>
                </div>
              ))}
              {pictures.length < PICTURES && (
                <button type="button" onClick={() => picker.current?.click()}
                        className="flex size-20 flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-xs text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
                  <ImagePlus aria-hidden className="size-5" /> Add
                </button>
              )}
            </div>
            <input ref={picker} type="file" accept="image/*" multiple hidden onChange={(e) => (void add(e.target.files ?? []), e.target.value = "")} />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <p role="status" className={cn("min-w-0 flex-1 text-xs", said && "error" in said ? "text-destructive" : "text-muted-foreground")}>
              {said && "error" in said ? said.error
                : said?.sent ? <span className="inline-flex items-center gap-1 text-foreground"><Check aria-hidden className="size-3.5 text-emerald-600 dark:text-emerald-400" /> Sent. Thank you!</span>
                : waiting ? `${waiting === 1 ? "One suggestion is" : `${waiting} suggestions are`} kept here, and sent as soon as you're online.`
                : "Only what you write and the pictures you add are sent, with the time you wrote it."}
            </p>
            <Button type="submit" disabled={!text.trim() || sending}>
              {sending ? <Spinner data-icon="inline-start" /> : <Send data-icon="inline-start" />} Send
            </Button>
          </div>
        </form>
      </section>
    </div>
  )
}
