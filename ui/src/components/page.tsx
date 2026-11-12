// A view's title row, the same on every view: its title, what's beside it (tabs, a count), a line
// under it, and its actions at the right.

import type { ReactNode } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

/** A search box for a view's title row: `label` says what it searches. */
export function SearchBox({ value, onChange, label }: { value: string; onChange: (text: string) => void; label: string }) {
  return (
    <label className="relative">
      <Search aria-hidden className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Search" aria-label={label} className="h-8 w-56 pl-8 text-sm" />
    </label>
  )
}

/** A view's title, `beside` it, `sub` under it, and `children` (its actions) at the right. */
export function PageHeader({ title, beside, sub, children, className }: {
  title: ReactNode; beside?: ReactNode; sub?: ReactNode; children?: ReactNode; className?: string
}) {
  return (
    <header className={cn("flex flex-wrap items-center gap-x-4 gap-y-3", className)}>
      <div className="mr-auto flex min-w-0 flex-1 basis-72 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="font-heading text-[22px] leading-7 font-semibold tracking-[-0.025em]">{title}</h1>
          {beside}
        </div>
        {sub && <div className="max-w-[68ch] text-sm text-muted-foreground">{sub}</div>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  )
}
