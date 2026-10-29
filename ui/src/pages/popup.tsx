// The popup: one question or poke at a time (main.js: "show", null when it leaves).
// A question to you has "Later": no answer, as if it timed out (none when it's `immediate`).
// Then, by its options:
//   none           a text to type, and "OK"
//   1 to 3         a button each, the first the main one ("OK" if it's one of them)
//   4 or more      a dropdown to pick from (its `selected` picked already), and "OK" to confirm
// An option "OK" or "Later" is that button itself: picking it picks the option. A poke has
// nothing to answer: just "OK". Each may have a title, a picture (media) and a sound, which plays while it's
// shown: answering it, closing it, or its leaving for any reason stops the sound at once.

import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Kbd } from "@/components/ui/kbd"
import { Textarea } from "@/components/ui/textarea"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { fileUrl as file, mount, type Shown } from "@/lib/proki"

function Popup() {
  const [item, setItem] = useState<Shown | null>(null)
  const [typed, setTyped] = useState("")
  const [picked, setPicked] = useState<number | null>(null)
  const card = useRef<HTMLDivElement>(null)

  useEffect(() => {
    window.proki.onShow((shown) => {
      setItem(shown)
      setTyped(shown?.show.text ?? "")
      setPicked(shown?.show.selected ?? null)
    })
  }, [])
  useEffect(() => {  // its sound, while it's shown
    if (!item?.show.sound) return
    const sound = new Audio(file(item.show.sound))
    sound.loop = true
    sound.play()
    return () => sound.pause()
  }, [item])
  const fit = () => {  // the window fits the card
    if (card.current) window.proki.resize(card.current.getBoundingClientRect().height + 24)
  }
  useLayoutEffect(fit, [item])

  if (!item) return null
  const answer = (value: number | string | null) => {
    setItem(null)  // off the screen, and quiet, at once
    window.proki.answer(item.id, value)
  }
  const options = item.options
  const poke = options !== null && options.length === 0
  const is = (word: string) => options?.findIndex((o) => o.trim().toUpperCase() === word) ?? -1
  const [okAt, laterAt] = [is("OK"), is("LATER")]  // an option that is that button itself (-1: none)
  const buttons = options !== null && options.length >= 1 && options.length <= 3
  const listed = options !== null && options.length > 3
  const main = okAt >= 0 ? okAt : options?.findIndex((_, index) => index !== laterAt) ?? -1  // the button drawn filled
  const ok = () => {
    if (options === null) answer(typed.trim() || null)
    else if (picked !== null) answer(picked)
    else if (okAt >= 0) answer(okAt)
  }
  const later = laterAt >= 0 ? () => answer(laterAt) : item.show.immediate ? null : () => answer(null)

  return (
    <div className="p-3">
      <Card ref={card} className="gap-3 shadow-xl ring-foreground/15">
        <CardContent className="flex flex-col gap-3">
          <div className="flex gap-3">
            {item.show.media && (
              <img src={file(item.show.media)} alt="" onLoad={fit} className="size-20 shrink-0 object-contain" />
            )}
            <div className="flex min-w-0 flex-col gap-1.5">
              {item.show.title ? (
                <h2 className="text-sm font-semibold">{item.show.title}</h2>
              ) : (
                <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                  <span className="size-2 rounded-full bg-primary" />
                  proki
                </div>
              )}
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{item.text}</p>
            </div>
          </div>
          {listed && <Chooser options={options} picked={picked} onPick={setPicked} hidden={[okAt, laterAt]} />}
          {options === null && (
            <Textarea
              autoFocus
              value={typed}
              placeholder="Type something…"
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && ok()}
              className="min-h-24 resize-none"
            />
          )}
        </CardContent>
        <CardFooter className="flex flex-wrap justify-end gap-2 border-t bg-muted/40 py-3">
          {options === null && <span className="mr-auto text-xs text-muted-foreground"><Kbd>⌘</Kbd> <Kbd>↵</Kbd></span>}
          {poke ? (
            <Button size="sm" onClick={() => answer(null)}>OK</Button>
          ) : (
            <>
              {later && <Button variant="ghost" size="sm" onClick={later}>Later</Button>}
              {buttons ? options!.map((label, index) => index !== laterAt && (
                <Button key={index} size="sm" variant={index === main ? "default" : "outline"}
                        onClick={() => answer(index)}>{label}</Button>
              )) : (
                <Button size="sm" disabled={listed && picked === null && okAt < 0} onClick={ok}>OK</Button>
              )}
            </>
          )}
        </CardFooter>
      </Card>
    </div>
  )
}

/** Four or more options: a dropdown to pick one from, the one picked already shown (but the
 *  `hidden` ones: "OK" and "Later", buttons of their own). A native menu, so it opens past the
 *  popup's small window, and scrolls when there are many. */
function Chooser({ options, picked, onPick, hidden }: {
  options: string[]
  picked: number | null
  onPick: (index: number) => void
  hidden: number[]
}) {
  return (
    <NativeSelect autoFocus value={picked ?? ""} onChange={(e) => onPick(Number(e.target.value))} className="w-full">
      {picked === null && <NativeSelectOption value="" disabled>Choose one…</NativeSelectOption>}
      {options.map((label, index) => !hidden.includes(index) &&
        <NativeSelectOption key={index} value={index}>{label}</NativeSelectOption>)}
    </NativeSelect>
  )
}

mount(<Popup />)
