// A value changed in a table, held until it's kept: what it was, what it is now, and for a list each row's place in what it was (a row added has
// none, a row taken out stays, marked, until Save).

import { useEffect, useState } from "react"
import { arrayMove } from "@dnd-kit/sortable"

export type Path = (string | number)[]
type Meta = { key: number; was: number | null; gone?: boolean }

/** The value at `path` in `root` (none: undefined). */
export const at = (root: unknown, path: Path): unknown => path.reduce<unknown>((v, k) => (v == null ? undefined : (v as Record<string | number, unknown>)[k]), root)
export const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/** A whole value with the one at `path` replaced. */
function withAt(root: unknown, path: Path, value: unknown): unknown {
  if (!path.length) return value
  const [key, ...rest] = path
  const inner = withAt((root as Record<string | number, unknown>)[key], rest, value)
  return Array.isArray(root) ? root.map((v, i) => (i === key ? inner : v)) : { ...(root as object), [key]: inner }
}

let next = 1  // a row's key, for as long as the page lives
const metaOf = (value: unknown): Meta[] => (Array.isArray(value) ? value.map((_, i) => ({ key: next++, was: i })) : [])

/** `value` held for change (`enabled`: it can be), started over each time `open` turns on and when `value` changes while nothing's changed; `onReset`: after each. */
export function useDraft(value: unknown, enabled: boolean, open: boolean, onReset: () => void) {
  const [base, setBase]     = useState(value)  // what it is, as kept
  const [draft, setDraft]   = useState(value)  // what it is, changed here
  const [meta, setMeta]     = useState<Meta[]>(() => metaOf(value))
  const [picked, setPicked] = useState<number[]>([])  // the rows chosen to delete, by their keys
  const list  = Array.isArray(draft) && enabled ? meta : null
  const final = list ? (draft as unknown[]).filter((_, i) => !list[i]?.gone) : draft
  const dirty = enabled && !same(final, base)

  const reset = (to: unknown) => (setBase(to), setDraft(to), setMeta(metaOf(to)), setPicked([]), onReset())
  useEffect(() => void (!dirty && !same(value, base) && reset(value)), [JSON.stringify(value)])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => void (open && reset(value)), [open])  // eslint-disable-line react-hooks/exhaustive-deps

  /** What the place at `path` was, as kept (`found`: none, for a row added). */
  const was = (path: Path): { found: boolean; value: unknown } => {
    if (!list) return { found: true, value: at(base, path) }
    const old = list[path[0] as number]?.was
    return old === null || old === undefined ? { found: false, value: undefined } : { found: true, value: at(base, [old, ...path.slice(1)]) }
  }
  const rows = (items: unknown[], keys: number[]) => {  // the rows `keys` taken out: one added is dropped, one that was stays, marked
    const kept = items.map((_, i) => i).filter((i) => !(keys.includes(list![i].key) && list![i].was === null))
    setDraft(kept.map((i) => items[i]))
    setMeta(kept.map((i) => (keys.includes(list![i].key) ? { ...list![i], gone: true } : list![i])))
    setPicked([])
  }
  const mark = (i: number, gone: boolean) => list && setMeta(list.map((m, j) => (j === i ? { ...m, gone } : m)))

  return {
    base, draft, list, final, dirty, picked, reset, was,
    put:    (path: Path, to: unknown) => (setDraft(withAt(draft, path, to)), Promise.resolve(null)),
    take:   (keys: number[]) => list && rows(draft as unknown[], keys),
    back:   (i: number) => mark(i, false),
    move:   (from: number, to: number) => list && from !== to && (setDraft(arrayMove(draft as unknown[], from, to)), setMeta(arrayMove(list, from, to))),
    push:   (to: unknown) => list && (setDraft([...(draft as unknown[]), to]), setMeta([...list, { key: next++, was: null }])),
    choose: (key: number) => setPicked(picked.includes(key) ? picked.filter((k) => k !== key) : [...picked, key]),
  }
}
