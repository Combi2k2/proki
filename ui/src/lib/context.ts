// A prompt and its named expression values.

export type Pair = [string, string]

/** What's said, as the popup shows it: its text with {name}s filled from expressions. */
export const contextOf = (value: unknown) => {
  const context = typeof value === "string" ? { format: value, values: {} } : (value as { format?: string; values?: Record<string, string> | Pair[] }) ?? {}
  return { format: context.format ?? "", values: (Array.isArray(context.values) ? context.values : Object.entries(context.values ?? {})) as Pair[] }
}

