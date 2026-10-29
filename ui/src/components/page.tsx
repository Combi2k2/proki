// A view's title row, the same on every view: its title, what's beside it (tabs, a count), a line
// under it, and its actions at the right.

import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/** A view's title, `beside` it, `sub` under it, and `children` (its actions) at the right. */
export function PageHeader({ title, beside, sub, children, className }: {
  title: ReactNode; beside?: ReactNode; sub?: ReactNode; children?: ReactNode; className?: string
}) {
  return (
    <header className={cn("flex flex-wrap items-center gap-x-4 gap-y-3", className)}>
      <div className="mr-auto flex min-w-0 flex-col gap-1">
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
