// Contribute: proki's code on GitHub, a coffee for its developer (soon), and a suggestion of
// yours. A suggestion is kept on this computer until it reaches the developer, sent at once if
// you're online, else as soon as you are (the main window tries again, see pages/main.tsx).

import { useEffect, useState } from "react"
import { ArrowUpRight, Check, Coffee, Send } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import github from "@/assets/brands/github.svg?raw"

const LONGEST = 5000  // characters a suggestion can have (proki/tools/suggestions.py)

export function ContributeView() {
  const [text, setText]       = useState("")
  const [contact, setContact] = useState("")
  const [sending, setSending] = useState(false)
  const [waiting, setWaiting] = useState(0)
  const [said, setSaid]       = useState<{ sent: boolean } | { error: string } | null>(null)

  useEffect(() => void window.proki.tool("send_suggestions").then((r) => !r.error && setWaiting(r.waiting)), [])

  const send = async () => {
    setSending(true)
    const answer = await window.proki.tool("suggest", { text, ...(contact.trim() ? { contact } : {}) })
    setSending(false)
    if (answer.error) return setSaid({ error: answer.error })
    setWaiting(answer.waiting)
    setSaid({ sent: !answer.waiting })
    setText("")
  }

  return (
    <div className="mx-auto max-w-2xl px-8 pt-7 pb-24">
      <PageHeader title="Contribute" sub="Proki is open source, and made by one person. Any of these helps it get better." className="mb-6" />

      <div className="mb-10 grid gap-3 sm:grid-cols-2">
        <button onClick={() => window.proki.link("github")}
                className="group flex items-start gap-3 rounded-xl border bg-card px-4 py-3.5 text-left transition-colors hover:bg-accent/60 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
          <span aria-hidden className="mt-0.5 size-5 shrink-0 [&>svg]:size-full" dangerouslySetInnerHTML={{ __html: github }} />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1 text-sm font-semibold">The code, on GitHub <ArrowUpRight aria-hidden className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" /></span>
            <span className="mt-0.5 block text-xs text-muted-foreground">Report a bug, or send a change of your own.</span>
          </span>
        </button>
        <div className="flex items-start gap-3 rounded-xl border border-dashed px-4 py-3.5">
          <Coffee aria-hidden className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-2 text-sm font-semibold">Buy me a coffee <span className="rounded-full bg-muted px-1.5 py-px text-[10px] font-medium text-muted-foreground">soon</span></span>
            <span className="mt-0.5 block text-xs text-muted-foreground">A way to say thanks is on its way.</span>
          </span>
        </div>
      </div>

      <section aria-labelledby="suggest" className="rounded-xl border bg-card">
        <header className="border-b px-5 py-3.5">
          <h2 id="suggest" className="text-sm font-semibold">Suggest something</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Something that got in your way, felt slow, or could simply be nicer. It goes straight to the developer.</p>
        </header>
        <form className="flex flex-col gap-4 px-5 py-4" onSubmit={(e) => (e.preventDefault(), text.trim() && !sending && send())}>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium">What could be better?</span>
            <Textarea value={text} onChange={(e) => (setText(e.target.value), setSaid(null))} maxLength={LONGEST} rows={5} className="min-h-28 resize-none"
                      placeholder="When I… I expected… instead…" />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium">How to reach you <span className="font-normal text-muted-foreground">(if you'd like an answer)</span></span>
            <Input value={contact} onChange={(e) => setContact(e.target.value)} maxLength={200} placeholder="An email, or a GitHub name" autoComplete="email" />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <p role="status" className={cn("min-w-0 flex-1 text-xs", said && "error" in said ? "text-destructive" : "text-muted-foreground")}>
              {said && "error" in said ? said.error
                : said?.sent ? <span className="inline-flex items-center gap-1 text-foreground"><Check aria-hidden className="size-3.5 text-emerald-600 dark:text-emerald-400" /> Sent. Thank you!</span>
                : waiting ? `${waiting === 1 ? "One suggestion is" : `${waiting} suggestions are`} kept here, and sent as soon as you're online.`
                : "Only what you write here is sent, with the time you wrote it."}
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
