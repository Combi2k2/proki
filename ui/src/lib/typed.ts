// A value as it's typed: empty is unknown, true / false, a number, `{…}` / `[…]` read as JSON, else an expression.

/** A value as it's typed in (an object or a list as JSON). */
export function valueText(value: unknown): string {
  return value === null || value === undefined ? "" : typeof value === "object" ? JSON.stringify(value) : String(value)
}

/** What's typed as a value: null when empty, else the value it reads as. */
export function parseValue(text: string): unknown {
  const t = text.trim()
  if (t === "") return null
  if (t === "true" || t === "false") return t === "true"
  if (/^[{[]/.test(t)) try { return JSON.parse(t) } catch { /* not JSON: an expression */ }
  return /^-?\d+(\.\d+)?$/.test(t) ? Number(t) : t
}

/** An action's value as it's typed: an object's fields each an expression, `{"name": work.plan.name, "note": 'Todo'}`. */
export function exprText(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return valueText(value)
  return `{${Object.entries(value).map(([k, v]) => `${JSON.stringify(k)}: ${v}`).join(", ")}}`
}

/** An object's pieces split at the commas (or the colon, for `at: ":"`) that sit outside any quote or bracket. */
function apart(text: string, at: "," | ":"): string[] {
  const out: string[] = []
  let depth = 0, quote = "", from = 0
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (quote) { if (c === "\\") i++; else if (c === quote) quote = ""; continue }
    if (c === "'" || c === '"') quote = c
    else if ("([{".includes(c)) depth++
    else if (")]}".includes(c)) depth--
    else if (c === at && depth === 0 && (at === "," || out.length === 0)) (out.push(text.slice(from, i)), from = i + 1)
  }
  out.push(text.slice(from))
  return out
}

/** What `exprText` wrote, back: an object whose fields are expressions. Text that isn't one reads as `parseValue` does. */
export function parseExpr(text: string): unknown {
  const t = text.trim()
  if (!t.startsWith("{") || !t.endsWith("}")) return parseValue(text)
  const inside = t.slice(1, -1).trim()
  if (!inside) return {}
  const pairs = apart(inside, ",").filter((p) => p.trim()).map((p) => apart(p, ":"))
  if (pairs.some((p) => p.length < 2)) return t
  return Object.fromEntries(pairs.map(([k, v]) => [k.trim().replace(/^(['"])(.*)\1$/, "$2"), v.trim()]))
}
