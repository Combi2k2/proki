// An icon to choose, by its picture: a few that suit a helper first, any other found by what
// it's called. What's chosen is its name.

import { useState, type ReactNode } from "react"
import { DynamicIcon, iconNames, type IconName } from "lucide-react/dynamic"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

const SUITED: IconName[] = [
  "timer", "hourglass", "alarm-clock", "calendar-clock", "clock", "sunrise", "sun", "sunset", "moon-star", "bed-double", "coffee", "cup-soda",
  "brain", "waves", "target", "zap", "flame", "leaf", "heart-pulse", "dumbbell", "person-standing", "footprints", "eye", "music",
  "list-checks", "list-todo", "compass", "bell", "bot", "sparkles", "lightbulb", "notebook-pen", "pencil", "book-open", "tag", "folder",
  "mail", "message-circle", "phone", "users", "house", "briefcase", "chart-line", "trophy", "gift", "shield", "wand", "rocket",
]
const SHOWN = 60  // found, at most

export function IconPicker({ value, onPick, label = "Choose an icon", disabled, children }: {
  value: string
  onPick: (name: string) => void
  label?: string
  disabled?: boolean
  children: ReactNode  // what opens it
}) {
  const [open, setOpen] = useState(false)
  const [find, setFind] = useState("")
  const words = find.trim().toLowerCase().replace(/\s+/g, "-")
  const found = words ? (iconNames as IconName[]).filter((n) => n.includes(words)).slice(0, SHOWN) : SUITED
  const pick = (name: string) => (onPick(name), setOpen(false), setFind(""))
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild disabled={disabled} aria-label={label} title={disabled ? undefined : label}>{children}</PopoverTrigger>
      <PopoverContent align="start" className="flex w-72 flex-col gap-2 p-2">
        <Input value={find} onChange={(e) => setFind(e.target.value)} placeholder="Find an icon: sun, book…" autoFocus className="h-8"
               autoCapitalize="off" autoCorrect="off" spellCheck={false} />
        <div role="listbox" aria-label="Icons" className="grid max-h-56 grid-cols-8 gap-0.5 overflow-y-auto [scrollbar-width:thin]">
          {found.map((name) => (
            <button key={name} role="option" aria-selected={name === value} title={name} aria-label={name} onClick={() => pick(name)}
                    className={cn("grid aspect-square place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground",
                                  name === value && "bg-primary/12 text-primary")}>
              <DynamicIcon name={name} className="size-4" />
            </button>
          ))}
        </div>
        {!found.length && <p className="px-1 pb-1 text-xs text-muted-foreground">No icon is called that.</p>}
      </PopoverContent>
    </Popover>
  )
}
