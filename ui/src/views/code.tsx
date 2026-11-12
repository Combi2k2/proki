// Expressions coloured as Python is: keywords, True/False/None, strings, numbers, the functions
// called, the names, the operators. Expr shows one; CodeInput is a field to type one in, coloured as it's typed (the text drawn over the field, the field's own
// transparent: its caret and its selection stay).

import { useEffect, useLayoutEffect, useRef, type ComponentProps, type ReactNode } from "react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const KEYWORDS  = new Set(["and", "or", "not", "in", "is", "if", "else", "lambda", "for"])
const CONSTANTS = new Set(["True", "False", "None"])
const TOKEN     = /('(?:[^'\\]|\\.)*'?|"(?:[^"\\]|\\.)*"?)|((?:\d+\.?\d*(?:e[+-]?\d+)?|\.\d+)(?:[KMB](?!\w))?)|([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)|(\s+)|([()[\]{}])|([^\s\w'"()[\]{}]+)/gi
const COLOUR    = {
  keyword:  "text-code-keyword",
  constant: "text-code-constant",
  string:   "text-code-string",
  number:   "text-code-number",
  call:     "text-code-call",
  name:     "text-foreground",
  bracket:  "text-code-bracket",
  operator: "text-code-punct",
} as const

/** An expression as coloured spans, a token each (spaces as they are). */
export function colour(text: string) {
  if (text.trim() === "–") return <span className="text-muted-foreground">{text}</span>  // nothing there
  return [...text.matchAll(TOKEN)].map((m, i) => {
    const [all, string, number, word, space, bracket] = m
    if (space) return all
    const kind = string ? "string" : number ? "number" : word
      ? KEYWORDS.has(word) ? "keyword" : CONSTANTS.has(word) ? "constant" : /^\s*\(/.test(text.slice(m.index + all.length)) ? "call" : "name"
      : bracket ? "bracket" : "operator"
    return <span key={i} className={COLOUR[kind]}>{all}</span>
  })
}

/** An expression shown coloured, in the font code is in. */
export function Expr({ children, className, ...props }: { children: string } & Omit<ComponentProps<"code">, "children">) {
  return <code className={cn("font-mono", className)} {...props}>{colour(children)}</code>
}

const SIZE = "text-base md:text-sm"  // the field's own, before the caller's

/** A field with no box: its text, a line under it as you point at it. */
export const BARE = "h-7 rounded-none border-0 border-b border-transparent bg-transparent px-0 text-xs shadow-none dark:bg-transparent hover:border-dotted hover:border-muted-foreground focus-visible:border-solid focus-visible:border-ring focus-visible:ring-0"

/** A field to type an expression in, coloured. `layout`: where the field sits (its width, flex), on its box.
 * `render`: how the text is drawn, as an expression's colours by default. */
export function CodeInput({ value, className, layout, render = colour, ...props }: { value: string; layout?: string; render?: (text: string) => ReactNode } & ComponentProps<typeof Input>) {
  const field = useRef<HTMLInputElement>(null)
  const shown = useRef<HTMLSpanElement>(null)
  const follow = () => void (shown.current && field.current && (shown.current.style.transform = `translateX(${-field.current.scrollLeft}px)`))
  useLayoutEffect(follow, [value])
  useEffect(() => {  // the field scrolls as its caret moves, not always saying so: followed after each move
    const moved = () => requestAnimationFrame(follow)
    const on = field.current!, events = ["scroll", "input", "keydown", "keyup", "mouseup", "focus", "blur", "select"]
    events.forEach((e) => on.addEventListener(e, moved))
    document.addEventListener("selectionchange", moved)
    return () => (events.forEach((e) => on.removeEventListener(e, moved)), document.removeEventListener("selectionchange", moved))
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={cn("relative min-w-0", layout)}>
      <Input ref={field} value={value} spellCheck={false} autoCapitalize="off" autoCorrect="off" {...props}
             className={cn("font-mono text-transparent caret-foreground selection:text-transparent", className)} />
      <div aria-hidden className={cn("pointer-events-none absolute inset-0 flex items-center overflow-hidden border border-transparent px-2.5 font-mono whitespace-pre", SIZE, className, "h-auto w-auto")}>
        <span ref={shown}>{render(value)}</span>
      </div>
    </div>
  )
}

const SLOT = /(\{[^{}\n]*\})/g

/** One {name} slot as Python reads a format string: its braces as punctuation, its name as a
 * placeholder's, what follows a colon (":.1f") as a format. */
function Slot({ inner }: { inner: string }) {
  const [, expr = "", spec = ""] = inner.match(/^([^:]*)(:.*)?$/s) ?? []
  return (
    <>
      <span className="text-code-bracket">{"{"}</span>
      {colour(expr)}
      {spec && <><span className="text-code-punct">:</span><span className="text-code-number">{spec.slice(1)}</span></>}
      <span className="text-code-bracket">{"}"}</span>
    </>
  )
}

/** A text with its {name} slots drawn as code (colour only, so it measures as it's typed). */
const Slots = ({ text, string }: { text: string; string?: boolean }) => (
  <>{text.split(SLOT).map((part, i) => (i % 2 ? <Slot key={i} inner={part.slice(1, -1)} /> : string && part ? <span key={i} className="text-code-string">{part}</span> : part))}</>
)

/** A text to type, its {name} slots drawn as code as they're typed; only the colour differs, so the
 * caret stays where the letters are. It grows with what's typed. The line under it shows as you point
 * at it. */
export function Template({ value, className, strings, ...props }: { value: string; strings?: boolean } & ComponentProps<typeof Textarea>) {
  const box = cn("col-start-1 row-start-1 min-h-14 w-full px-0 py-1 leading-relaxed break-words whitespace-pre-wrap", strings ? "font-mono text-xs" : "text-sm")
  return (
    <div className="grid">
      <div aria-hidden className={cn(box, "pointer-events-none")}>
        <Slots text={value} string={strings} />{"\n"}
      </div>
      <textarea value={value} spellCheck={false} {...props}
                className={cn(box, "resize-none overflow-hidden border-0 bg-transparent text-transparent caret-foreground outline-none placeholder:text-muted-foreground", !strings && "border-b border-transparent hover:border-dotted hover:border-muted-foreground focus:border-solid focus:border-ring", className)} />
    </div>
  )
}

/** A text with {slots}, in a box of its own, its name above it. */
export function TemplateBox({ label, className, ...props }: { label: string; value: string } & Omit<ComponentProps<typeof Textarea>, "value">) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium">{label}</span>
      <div className="rounded-md border px-2 py-1 text-xs focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50">
        <Template strings aria-label={label} className={className} {...props} />
      </div>
    </div>
  )
}
