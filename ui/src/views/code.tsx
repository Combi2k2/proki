// Expressions coloured as Python is: keywords, True/False/None, strings, numbers, the functions
// called, the names, the operators. Expr shows one; CodeInput and CodeArea are a field and a box
// to type one in, coloured as it's typed (the text drawn over the field, the field's own
// transparent: its caret and its selection stay).

import { useEffect, useLayoutEffect, useRef, type ComponentProps } from "react"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const KEYWORDS  = new Set(["and", "or", "not", "in", "is", "if", "else", "lambda", "for"])
const CONSTANTS = new Set(["True", "False", "None"])
const TOKEN     = /('(?:[^'\\]|\\.)*'?|"(?:[^"\\]|\\.)*"?)|(\d+\.?\d*(?:e[+-]?\d+)?|\.\d+)|([A-Za-z_]\w*)|(\s+)|([^\s\w'"]+)/gi
const COLOUR    = {
  keyword:  "text-code-keyword",
  constant: "text-code-constant",
  string:   "text-code-string",
  number:   "text-code-number",
  call:     "text-code-call",
  name:     "text-foreground",
  operator: "text-muted-foreground",
} as const

/** An expression as coloured spans, a token each (spaces as they are). */
function colour(text: string) {
  return [...text.matchAll(TOKEN)].map((m, i) => {
    const [all, string, number, word, space] = m
    if (space) return all
    const kind = string ? "string" : number ? "number" : word
      ? KEYWORDS.has(word) ? "keyword" : CONSTANTS.has(word) ? "constant" : /^\s*\(/.test(text.slice(m.index + all.length)) ? "call" : "name"
      : "operator"
    return <span key={i} className={COLOUR[kind]}>{all}</span>
  })
}

/** An expression shown coloured, in the font code is in. */
export function Expr({ children, className, ...props }: { children: string } & Omit<ComponentProps<"code">, "children">) {
  return <code className={cn("font-mono", className)} {...props}>{colour(children)}</code>
}

const SIZE = "text-base md:text-sm"  // the field's own, before the caller's

/** A field to type an expression in, coloured. `layout`: where the field sits (its width, flex), on its box. */
export function CodeInput({ value, className, layout, ...props }: { value: string; layout?: string } & ComponentProps<typeof Input>) {
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
        <span ref={shown}>{colour(value)}</span>
      </div>
    </div>
  )
}

/** A box to type a longer expression in, coloured; it grows with what's typed. */
export function CodeArea({ value, className, ...props }: { value: string } & ComponentProps<typeof Textarea>) {
  return (
    <div className="relative min-w-0">
      <Textarea value={value} spellCheck={false} autoCapitalize="off" autoCorrect="off" {...props}
                className={cn("font-mono text-transparent caret-foreground selection:text-transparent", className)} />
      <div aria-hidden className={cn("pointer-events-none absolute inset-0 overflow-hidden border border-transparent px-2.5 py-2 font-mono break-words whitespace-pre-wrap", SIZE, className, "min-h-0")}>
        {colour(value)}{"\n"}
      </div>
    </div>
  )
}
