// A choice kept in this window's storage, like which view is shown. Without storage (a
// private window, cleared data), the choice lasts until the window closes.

/** The choice kept under `key`, if it's one of `options`, else `fallback`. */
export function recall<T extends string>(key: string, options: readonly T[], fallback: T): T {
  try {
    const kept = localStorage.getItem(key)
    return options.includes(kept as T) ? (kept as T) : fallback
  } catch {
    return fallback
  }
}

/** Keep `value` under `key`. */
export function remember(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // no storage here
  }
}

/** The JSON kept under `key`, else `fallback`. */
export function recallJson<T>(key: string, fallback: T): T {
  try {
    const kept = localStorage.getItem(key)
    return kept === null ? fallback : (JSON.parse(kept) as T)
  } catch {
    return fallback
  }
}

/** Keep `value` under `key`, as JSON. */
export function rememberJson(key: string, value: unknown): void {
  remember(key, JSON.stringify(value))
}
