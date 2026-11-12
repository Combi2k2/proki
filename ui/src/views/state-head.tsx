// The top of a state's dialog: the ring of its cycle, with its period; its name and what it's for.

import { useEffect, useState } from "react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { type ProgramDetail, type StateSpec } from "@/lib/proki"
import { humane } from "@/lib/friendly"
import { cn } from "@/lib/utils"
import { CHANGED_LINE, type Staged } from "@/views/in-place"

type Live = ProgramDetail["states"][number]

const PLAIN = { autoCapitalize: "off", autoCorrect: "off", spellCheck: false } as const  // names, as typed
const SIZE  = 104, WIDTH = 7, RADIUS = (SIZE - WIDTH) / 2  // ring + period (8 + 28) is as tall as the name and the description beside them (16 + 4 + 32, 8, 16 + 4 + 60)

/** Seconds left as a clock: 4:05, or 1:02:05 past an hour. */
const clock = (t: number) => {
  const [h, m, s] = [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60]
  return `${h ? `${h}:${String(m).padStart(2, "0")}` : m}:${String(s).padStart(2, "0")}`
}

/** The ring of a state's cycle, full as it starts and emptying as the wait runs (full when it isn't running), the time left in it; below, the period in seconds
 * (`onType`: changed as typed; none: read only), underlined to say it can be changed. */
function Cycle({ text, waking, changed, onType }: { text: string; waking: string | null; changed: boolean; onType?: (text: string) => void }) {
  const [, tick] = useState(0)
  useEffect(() => {
    if (!waking) return
    const t = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [waking])
  const seconds = Number(text) > 0 ? Number(text) : 0
  const left    = waking ? Math.max(0, Math.round((new Date(waking).getTime() - Date.now()) / 1000)) : null
  const share   = left === null || !seconds ? 1 : Math.min(1, left / seconds)
  return (
    <div className="flex shrink-0 flex-col items-center gap-2">
      <div className="relative grid place-items-center" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} aria-hidden className="-rotate-90">
          <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" strokeWidth={WIDTH} className="stroke-muted" />
          <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" strokeWidth={WIDTH} strokeLinecap="round" className="stroke-primary transition-[stroke-dashoffset] duration-1000 ease-linear motion-reduce:transition-none"
                  strokeDasharray={2 * Math.PI * RADIUS} strokeDashoffset={2 * Math.PI * RADIUS * (1 - share)} />
        </svg>
        <span className={cn("absolute font-mono text-base tabular-nums", left === null && "text-muted-foreground")}
              aria-label={left === null ? "not running" : `${left} seconds left`}>{clock(left ?? Math.round(seconds))}</span>
      </div>
      <label className="flex h-7 items-center gap-1.5 text-xs text-muted-foreground">
        <Input inputMode="decimal" aria-label="Cycle, in seconds" value={text} readOnly={!onType} onChange={(e) => onType?.(e.target.value)}
               className={cn("h-7 w-12 rounded-none border-0 border-b border-dotted border-muted-foreground bg-transparent px-0 text-center text-xs shadow-none focus-visible:border-solid focus-visible:border-ring focus-visible:ring-0 dark:bg-transparent",
                             changed && CHANGED_LINE, !onType && "border-transparent")} />
        seconds
      </label>
    </div>
  )
}

/** A state's name and what it's for, beside the ring of its cycle, changed under the dialog's `st` (`onTitle`: told the name as it's typed): nothing is kept until its Save. `spec`: none, for a state in code, read only. */
export function StateHead({ st, state, spec, live, detail, onTitle }: { st: Staged; state: string; spec?: StateSpec; live: Live; detail: ProgramDetail; onTitle: (name: string | null) => void }) {
  const typed = st.patch.name as string | undefined
  useEffect(() => (onTitle(typed ?? null), () => onTitle(null)), [typed, onTitle])  // the dialog's title follows what's typed
  const seconds = Math.round(live.every * 60 * 100) / 100
  const waking  = detail.on && detail.state === state ? detail.waking : null
  if (!spec) return (
    <div className="flex items-start gap-4">
      <Cycle text={String(seconds)} waking={waking} changed={false} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <span className="font-mono text-sm font-medium">{humane(state)}</span>
        <p className="text-sm">{live.desc || <span className="text-muted-foreground">No description.</span>}</p>
      </div>
    </div>
  )
  const shown = (key: "name" | "desc") => (st.patch[key] as string | undefined) ?? spec[key]
  return (
    <div className="flex items-start gap-4">
      <Cycle text={String(st.patch.every ?? seconds)} waking={waking} changed={"every" in st.patch} onType={(t) => st.put("every", t, String(seconds))} />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Name</span>
          <Input value={shown("name")} onChange={(e) => st.put("name", e.target.value, spec.name)} placeholder="waiting" {...PLAIN}
                 className={cn("h-8 font-mono text-xs", st.lit("name") && CHANGED_LINE)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Description</span>
          <Textarea value={shown("desc")} onChange={(e) => st.put("desc", e.target.value, spec.desc)} placeholder={live.desc || "An hour of work"}
                    className={cn("h-[3.75rem] min-h-0 resize-none field-sizing-fixed text-sm", st.lit("desc") && CHANGED_LINE)} />
        </label>
      </div>
    </div>
  )
}
