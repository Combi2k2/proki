// Help: first, getting started, three steps each with the button that takes it, and answers to
// what people ask; then, for whoever builds their own automations, the playground
// (views/playground.tsx), how programs work as slides (views/deck.tsx), and every function and
// action there is, found as you type.
import { useEffect, useMemo, useState } from "react"
import { ArrowRight, Check, ListTodo, Search, Timer, Workflow, Wrench } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Reference, View } from "@/lib/proki"
import { recall, remember } from "@/lib/remember"
import { Expr } from "@/views/code"
import { Deck } from "@/views/deck"
import { Playground } from "@/views/playground"
import { SYNTAX } from "@/views/programs"

const STEPS: { title: string; about: string; icon: typeof Timer; label: string; go?: View; session?: boolean }[] = [
  { title: "Add what you're working on", about: "Make a group for a project, then list its tasks. Proki suggests which one to do next.", icon: ListTodo, label: "Open tasks", go: "tasks" },
  { title: "Start a focus session", about: "Proki keeps you company: it notices when focus slips and tells you when it's time for a break.", icon: Timer, label: "Start one now", session: true },
  { title: "Pick your helpers", about: "Automations work on their own: morning planning, bedtime reminders, sorting notes. Turn on the ones you like.", icon: Workflow, label: "See automations", go: "programs" },
]

const ANSWERS: [string, string][] = [
  ["What does proki watch?", "Only which app or website is in front, and whether you're at the computer. It never reads what you type or what's on the screen, and everything stays on this computer."],
  ["Why did a little window pop up?", "One of your automations had something to ask or say, like a break reminder or a question about a note. Answer it, or choose Later; you can turn any automation off on the Automations page."],
  ["How is my focus worked out?", "From the apps you used in the last few minutes: work apps count towards focus, chat and browsing less. On Apps & time you can say which apps are work for you."],
  ["What happens to a note I write down?", "It lands in your notes as unsorted. The note sorter files it as a todo, an idea or a thought, and checks with you when it isn't sure."],
  ["Can I change what an automation does?", "Yes. Open it on the Automations page to see how it works, step by step. The Build your own tab below explains how they work, step by step."],
]

/** Getting started, then answers. */
function Start({ onGo }: { onGo?: (view: View) => void }) {
  const [started, setStarted] = useState(false)
  return (
    <div className="flex flex-col gap-10">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-3">
        {STEPS.map((step, i) => (
          <Card key={step.title} size="sm" className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1" style={{ animationDelay: `${i * 40}ms` }}>
            <CardHeader>
              <span className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                <span className="grid size-6 place-items-center rounded-full bg-primary/12 text-[11px] font-semibold text-primary tabular-nums">{i + 1}</span>
                <step.icon aria-hidden className="size-4" />
              </span>
              <CardTitle>{step.title}</CardTitle>
              <CardDescription>{step.about}</CardDescription>
            </CardHeader>
            <CardFooter className="mt-auto">
              <Button variant="outline" size="sm" disabled={step.session && started}
                      onClick={() => step.session ? (window.proki.session("start"), setStarted(true)) : step.go && onGo?.(step.go)}>
                {step.session && started ? <><Check data-icon="inline-start" /> Session started</> : <>{step.label} <ArrowRight data-icon="inline-end" /></>}
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
      <section>
        <h2 className="mb-2 text-base font-semibold">Questions people ask</h2>
        <Accordion type="single" collapsible className="rounded-xl border px-4">
          {ANSWERS.map(([q, a]) => (
            <AccordionItem key={q} value={q}>
              <AccordionTrigger>{q}</AccordionTrigger>
              <AccordionContent className="max-w-[68ch] text-muted-foreground">{a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>
    </div>
  )
}

export function ManualView({ onGo }: { onGo?: (view: View) => void }) {
  const [tab, setTab] = useState(() => recall("help.tab", ["start", "build"] as const, "start"))
  const choose = (to: string) => { setTab(to as typeof tab); remember("help.tab", to) }
  return (
    <div className="mx-auto max-w-5xl px-8 pt-7 pb-10">
      <PageHeader title="Help" sub="New here? Start with these steps. Curious how it works inside? See Build your own." className="mb-5" />
      <Tabs value={tab} onValueChange={choose}>
        <TabsList className="mb-6">
          <TabsTrigger value="start">Get started</TabsTrigger>
          <TabsTrigger value="build"><Wrench data-icon="inline-start" /> Build your own</TabsTrigger>
        </TabsList>
        <TabsContent value="start"><Start onGo={onGo} /></TabsContent>
        <TabsContent value="build"><Build /></TabsContent>
      </Tabs>
    </div>
  )
}

/** How programs work, the playground and the reference. */
function Build() {
  const [reference, setReference] = useState<Reference | null>(null)
  const [find, setFind]   = useState("")
  useEffect(() => { window.proki.tool("reference").then((answer) => !answer.error && setReference(answer)) }, [])

  const needle = find.trim().toLowerCase()
  const has    = (...texts: string[]) => !needle || texts.some((t) => t.toLowerCase().includes(needle))
  const groups = useMemo<[string, [string, string][]][]>(() => [
    ["Syntax", SYNTAX.filter(([a, b]) => has(a, b))],
    ["Functions", (reference?.functions ?? []).filter((f) => has(f.call, f.about)).map((f) => [f.call, f.about])],
    ["Actions", (reference?.actions ?? []).filter((a) => has(a.name, a.about)).map((a) => [`${a.name} {${a.params.join(", ")}}`, a.about])],
  ], [reference, needle])  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col gap-10">
      <Playground />
      <Deck />
      <main>
      <div className="relative mb-6">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input value={find} onChange={(e) => setFind(e.target.value)} placeholder="Search the reference: slice, argmax, append…"
               aria-label="Search the reference" className="h-10 pl-9" />
      </div>

      <section id="reference" className="scroll-mt-6">
        <h2 className="mb-3 text-base font-semibold">Reference</h2>
        {groups.map(([title, rows]) => rows.length > 0 && (
          <div key={title} className="mb-5">
            <h3 className="mb-1.5 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">{title} <span className="tabular-nums">· {rows.length}</span></h3>
            <div className="divide-y rounded-xl border">
              {rows.map(([call, about]) => (
                <div key={call} className="flex items-baseline gap-4 px-4 py-2">
                  <Expr className="w-64 shrink-0 text-xs font-medium break-words">{call}</Expr>
                  <span className="text-xs text-muted-foreground first-letter:uppercase">{about}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
        {!reference && <p className="text-sm text-muted-foreground">Loading what programs can use…</p>}
      </section>
      </main>
    </div>
  )
}
