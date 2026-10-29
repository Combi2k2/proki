// How programs work, a slide each: screenshots of the app (assets/help/) and a few points on what
// they show, under them. A screenshot not there is a placeholder saying which to take, and its name.

import { ImagePlus } from "lucide-react"
import { Carousel, CarouselContent, CarouselItem, CarouselNext, CarouselPrevious } from "@/components/ui/carousel"
import { Expr } from "@/views/code"

const SHOTS = import.meta.glob<string>("../assets/help/*.png", { eager: true, query: "?url", import: "default" })
const EDGE  = "inset(6px round 10px)"  // the background a screenshot was taken with, round it, cut off

// shots: each file's name, and what it shows; points: four at most, a line each, `code` in backticks
type Slide = { id: string; title: string; shots: [string, string][]; points: string[] }

const SLIDES: Slide[] = [
  { id: "program", title: "A program", shots: [["program", "a program's states drawn as a graph, the one it's in lit"]],
    points: ["Each state a box, each transition an arrow.", "Numbered in the order they're tried.",
             "The state it's in is lit: here, `looking`.", "Green holds, red doesn't, dashed is the else."] },
  { id: "state", title: "A state", shots: [["state", "a state open: what it's for, its actions and its transitions"]],
    points: ["What it's for, its actions, its transitions.", "`guessing` asks jev, then keeps jev's label.",
             "Jev answered: to `guessed`; else, `unguessed`.", "Drag a line by its grip to change the order."] },
  { id: "transitions", title: "Transitions", shots: [["way-out", "a state's transitions, each part of each condition marked as it is now"]],
    points: ["Holds when every part of its condition does.", "✓ holds now, ✗ doesn't, – can't be told yet.",
             "Tried top to bottom: the first that holds wins.", "The most particular first, the else last."] },
  { id: "action", title: "Actions", shots: [["action", "a state's actions: sets, a question to jev and one to you"]],
    points: ["Set, add, sub, append or remove a variable.", "Ask a question, poke you, open a view.",
             "Each says in a line what it's for.", "An \"only when\" is checked as it's taken."] },
  { id: "variable", title: "Variables", shots: [["variable", "the Variables tab: each variable's type, name and value now"]],
    points: ["Holds a value until an action sets it.", "Persisted, it survives a restart.",
             "Everyone's (Global), a program's or a state's.", "A lock: the app reads it, so it's kept."] },
  { id: "signal", title: "Signals", shots: [["signal_drawer", "the Signals tab: each signal's value now"], ["signal_chart", "a signal's history drawn over a day"]],
    points: ["Worked out every cycle, never set.", "`ts_mean(focus, 30)`: its 30-minute mean.",
             "`delay(focus, 10)`: it, 10 minutes ago.", "`every(focus, 5)`: a mean per 5 minutes."] },
  { id: "records", title: "Records", shots: [["records", "a list of records opened as a table: a row each, a column a field"]],
    points: ["Named fields; a list of them opens as a table.", "`track.labels` is one proki keeps.",
             "A field set on a record is set on its table.", "A plain value is only a copy."] },
  { id: "lists", title: "Lists", shots: [["lists", "a list of numbers opened: each item and its place"]],
    points: ["Counted from 0: `focus_lines[0]` is 0.35.", "`xs[-1]` the last, `xs[1:]` all but the first.",
             "`tasks.done`: a field's column, one a record.", "Pop a queue: set `queue` to `queue[1:]`."] },
  { id: "rule", title: "Rules", shots: [["rule", "a rule: its two sides, how they compare, its softness and level"]],
    points: ["Its two sides compared, softly or not.", "Softness 0: yes or no; more: a chance.",
             "Rules vote by level, the highest first.", "A level passes when over half its rules fire."] },
  { id: "expressions", title: "Expressions", shots: [["expression", "a signal open: its expression, its type and its history kept"]],
    points: ["Names, numbers, 'strings', True, False, None.", "and, or, not, comparisons, arithmetic.",
             "`focus` is `deep_share * steady * engaged`.", "Try them in the playground: yours are safe."] },
]

/** How programs work, as slides to go through, screenshots and a few points on each. */
export function Deck() {
  return (
    <section id="how" aria-roledescription="slides" aria-label="How programs work" className="scroll-mt-6">
      <h2 className="mb-3 text-base font-semibold">How programs work</h2>
      <Carousel className="mx-12">
        <CarouselContent>
          {SLIDES.map((s, i) => (
            <CarouselItem key={s.id} aria-label={`${i + 1} of ${SLIDES.length}: ${s.title}`}>
              <div className="flex h-full flex-col gap-5 rounded-[14px] border bg-background p-5">
                <div className="flex h-[min(52vh,30rem)] items-center justify-center gap-3">
                  {s.shots.map(([name, shows]) => SHOTS[`../assets/help/${name}.png`]
                    ? <img key={name} src={SHOTS[`../assets/help/${name}.png`]} alt={shows} style={{ clipPath: EDGE }} className="max-h-full min-w-0 object-contain" />
                    : <div key={name} className="flex h-full flex-1 flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/40 px-6 text-center text-muted-foreground">
                        <ImagePlus className="size-6" aria-hidden />
                        <p className="text-sm">Screenshot to take: {shows}</p>
                        <code className="font-mono text-xs">ui/src/assets/help/{name}.png</code>
                      </div>)}
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="flex items-baseline gap-2 text-lg font-semibold">
                    {s.title}<span className="text-xs font-normal tabular-nums text-muted-foreground">{i + 1} / {SLIDES.length}</span>
                  </h3>
                  <ul className="grid list-disc items-start gap-x-10 gap-y-1 pl-5 text-sm text-muted-foreground marker:text-muted-foreground/60 md:grid-cols-2">
                    {s.points.map((p) => (
                      <li key={p}>{p.split("`").map((bit, j) => j % 2 ? <Expr key={j} className="text-[0.92em]">{bit}</Expr> : bit)}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </CarouselItem>
          ))}
        </CarouselContent>
        <CarouselPrevious />
        <CarouselNext />
      </Carousel>
    </section>
  )
}
