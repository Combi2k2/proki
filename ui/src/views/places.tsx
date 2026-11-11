// The actions of the automations that set or read something, as rows to go to: a spec's dialog and a record's field dialog list them alike.

import { Code, Split } from "lucide-react"
import { humane } from "@/lib/friendly"
import type { Place } from "@/lib/proki"
import { cn } from "@/lib/utils"
import { ACTIONS, Tinted } from "@/views/program-forms"
import { bus, FLASH, goTo } from "@/views/scope-shared"

/** The automations' page at `p`, its action or way out lit. */
export function goToPlace(p: Place) {
  bus.flashing = { program: p.program!, state: p.state!, kind: p.by === "condition" ? "branch" : "action", at: p.at ?? 0 }
  goTo({ program: p.program!, state: p.state! })
  window.dispatchEvent(new Event(FLASH))
}

/** `places` as a table of its automation, state and what is there; a click goes to it. */
export function Places({ places, onVisit }: { places: Place[]; onVisit: (p: Place) => void }) {
  const ROW = "grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.4fr)] items-center gap-3 px-2"
  return (
    <div className="rounded-md border text-xs">
      <div className={cn(ROW, "border-b bg-muted/40 py-1 text-xs text-muted-foreground")}><span>Automation</span><span>State</span><span>Where</span></div>
      {places.map((p, i) => {
        const [name, Icon, tint] = p.by === "condition" ? [`Transition ${(p.at ?? 0) + 1}`, Split, "bg-muted text-muted-foreground"] : ACTIONS[p.kind ?? ""] ?? [p.kind ?? "action", Code, "bg-muted text-muted-foreground"]
        return (
          <button key={i} type="button" onClick={() => onVisit(p)}
                  className={cn(ROW, "w-full border-b py-1.5 text-left last:border-b-0 hover:bg-muted/60")}>
            <span className="truncate font-mono font-medium">{p.program}</span>
            <span className="truncate font-mono">{humane(p.state ?? "")}</span>
            <span className="flex min-w-0 items-center gap-1.5">
              <Tinted icon={Icon} tint={tint} />
              <span className="shrink-0">{name}</span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
