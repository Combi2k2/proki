// The welcome, the first time the app opens (and again from Settings): a few steps, each a sticker,
// a title and a line under it, Back and Next at the foot. On the way, ActivityWatch is checked (the
// launcher installs it if it was nowhere) and the browser's extension offered.

import { useEffect, useRef, useState } from "react"
import { Dialog as DialogPrimitive } from "radix-ui"
import { Check, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { cn } from "@/lib/utils"
import doomscroll from "@/assets/welcome/doomscroll.gif"
import filming from "@/assets/welcome/filming.gif"
import happyHearts from "@/assets/welcome/happy_hearts.gif"
import hi from "@/assets/welcome/hi.gif"
import puppyEyes from "@/assets/welcome/puppy_eyes.gif"
import sobbing from "@/assets/welcome/sobbing.gif"
import squish from "@/assets/welcome/squish.gif"

type Browser = "chrome" | "firefox" | "other"
const TRAY = navigator.userAgent.includes("Mac") ? "menu bar" : "system tray"
const STEPS = {
  hi:      { gif: hi,          title: "Hi, I'm Proki!",                         text: "I help you stay on what you meant to do, and nudge you back when you drift." },
  thanks:  { gif: happyHearts, title: "Thank you for giving me a try",          text: "It means a lot. Really, a lot." },
  yours:   { gif: doomscroll,  title: "Welcome to the to‑do app you make yours", text: "Less of this, more of what you planned: tasks, notes and nudges, each an automation you can change." },
  watch:   { gif: filming,     title: "Let me see what you're working on",      text: "ActivityWatch tells me which app you're in, and it all stays on this computer. If your computer asks, let it see your windows." },
  browser: { gif: puppyEyes,   title: "Which browser do you use?",              text: "Its ActivityWatch extension shows me which sites you're on too." },
  sorry:   { gif: sobbing,     title: "Sorry, I can't see that one yet",        text: "I'll still keep track of your apps, just not the sites you visit." },
  done:    { gif: squish,      title: "Hehe, from now on you're stuck with me", text: `I'll be in your ${TRAY} whenever you need me.` },
}
const BROWSERS: { id: Browser; label: string; store?: "aw-chrome" | "aw-firefox"; name?: string }[] = [
  { id: "chrome",  label: "Chrome, Edge, Brave…", store: "aw-chrome",  name: "Chrome" },
  { id: "firefox", label: "Firefox",              store: "aw-firefox", name: "Firefox" },
  { id: "other",   label: "Other" },
]

export function Welcome({ onDone }: { onDone: () => void }) {
  const [at, setAt]             = useState(0)
  const [ahead, setAhead]       = useState(true)  // the way it went last: the step slides in from there
  const [browser, setBrowser]   = useState<Browser | null>(null)
  const [watching, setWatching] = useState<boolean | null>(null)
  const next = useRef<HTMLButtonElement>(null)

  const path = ["hi", "thanks", "yours", "watch", "browser", ...(browser === "other" ? ["sorry"] : []), "done"] as (keyof typeof STEPS)[]
  const step = path[at]
  const last = at === path.length - 1
  const { gif, title, text } = STEPS[step]
  const chosen = BROWSERS.find((b) => b.id === browser)
  const go = (by: number) => (setAhead(by > 0), setAt((was) => was + by))

  useEffect(() => {  // ActivityWatch, while its step is shown: it may still be getting installed
    if (step !== "watch") return
    const check = () => void window.proki.watching().then(setWatching).catch(() => setWatching(false))
    check()
    const every = setInterval(check, 2000)
    return () => clearInterval(every)
  }, [step])

  return (
    <DialogPrimitive.Root open>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay data-tauri-drag-region
                                 className="fixed inset-0 z-50 bg-black/45 [-webkit-app-region:drag] data-open:animate-in data-open:fade-in-0 data-open:duration-300" />
        <DialogPrimitive.Content
          onEscapeKeyDown={(e) => e.preventDefault()}
          onPointerDownOutside={(e) => e.preventDefault()}
          onOpenAutoFocus={(e) => (e.preventDefault(), next.current?.focus())}
          className="fixed top-1/2 left-1/2 z-50 flex h-[460px] max-h-[calc(100vh-2rem)] w-[480px] max-w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl bg-popover text-popover-foreground shadow-[0_24px_64px_-16px_rgb(0_0_0/0.4)] ring-1 ring-foreground/10 outline-none [-webkit-app-region:no-drag] data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-open:duration-300 data-open:ease-(--ease-out)"
        >
          <div key={step} className={cn("flex min-h-0 flex-1 flex-col animate-in fade-in-0 duration-300 ease-(--ease-out) motion-reduce:animate-none",
                                         ahead ? "slide-in-from-right-4" : "slide-in-from-left-4")}>
            <div className="flex shrink-0 justify-center pt-10">
              <img src={gif} alt="" className="size-32 object-contain" />
            </div>
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2.5 px-12 text-center">
              <DialogPrimitive.Title className="text-[28px] leading-[1.15] font-semibold tracking-[-0.03em] text-balance">{title}</DialogPrimitive.Title>
              <DialogPrimitive.Description className="max-w-[42ch] text-sm leading-relaxed text-pretty text-muted-foreground">{text}</DialogPrimitive.Description>
              {step === "watch" && (
                <div role="status" className="mt-2 flex min-h-8 flex-wrap items-center justify-center gap-x-3 gap-y-1 text-sm">
                  {watching === null ? <Spinner className="text-muted-foreground" />
                    : watching ? <span className="flex items-center gap-1.5 font-medium"><Check className="size-4 text-focused" />ActivityWatch is running</span>
                    : <>
                        <span className="flex items-center gap-2 text-muted-foreground"><Spinner />Getting it ready, about a minute…</span>
                        <Button variant="link" size="sm" className="h-auto px-0" onClick={() => window.proki.link("activitywatch")}>
                          Install it yourself <ExternalLink data-icon="inline-end" />
                        </Button>
                      </>}
                </div>
              )}
              {step === "browser" && (
                <div className="mt-2 flex flex-col items-center gap-3">
                  <ToggleGroup type="single" variant="outline" size="sm" value={browser ?? ""} aria-label="Your browser"
                               onValueChange={(value) => value && setBrowser(value as Browser)}>
                    {BROWSERS.map(({ id, label }) => <ToggleGroupItem key={id} value={id} className="px-3">{label}</ToggleGroupItem>)}
                  </ToggleGroup>
                  <Button variant="outline" size="sm" className={cn(!chosen?.store && "invisible")} tabIndex={chosen?.store ? 0 : -1}
                          onClick={() => chosen?.store && window.proki.link(chosen.store)}>
                    Add the extension to {chosen?.name ?? "it"} <ExternalLink data-icon="inline-end" />
                  </Button>
                </div>
              )}
            </div>
          </div>

          <div className="flex shrink-0 items-center justify-between px-6 pb-6">
            <div aria-label={`Step ${at + 1} of ${path.length}`} className="flex gap-1.5">
              {path.map((s, i) => (
                <span key={s} className={cn("h-1.5 rounded-full transition-[width,background-color] duration-300 ease-(--ease-out)",
                                            i === at ? "w-4 bg-foreground" : "w-1.5 bg-foreground/20")} />
              ))}
            </div>
            <div className="flex gap-2">
              {at > 0 && <Button variant="ghost" onClick={() => go(-1)}>Back</Button>}
              <Button ref={next} className="min-w-20" disabled={step === "browser" && !browser} onClick={() => last ? onDone() : go(1)}>
                {last ? "Let's go" : "Next"}
              </Button>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
