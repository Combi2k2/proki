// What the scope you're in can use, in a panel at the window's corner: the inputs, signals, variables and rules, each opened over the page in a dialog
// that says what it is, its value, what writes it and what reads it, and changed where it's read.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import { ChevronRight, CircleGauge, Eye, EyeOff, Pencil, Trash2 } from "lucide-react"
import { Confirm } from "@/components/confirm"
import { ErrorDialog } from "@/components/error-dialog"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Switch } from "@/components/ui/switch"
import { TooltipProvider } from "@/components/ui/tooltip"
import { type Change, type GlobalSpecs, type ProgramSpecs, type Reference, type RuleSpec, type Scope, type Links, type Place, type SignalSpec, type Type, type VarDetail, type VariableSpec, type Where } from "@/lib/proki"
import { recall, recallJson, remember, rememberJson } from "@/lib/remember"
import { cn } from "@/lib/utils"
import { NAMES, parseSide, parseSpan, parseValue, SpanField, valueText, type Save } from "@/views/program-forms"
import { Expr } from "@/views/code"
import { Chip, fieldKeys, Pill, type Reader, ItemChange, kindOf, RecordFields, said, SCALARS, SchemaFields, schemaOf, StagedFields, TypeChange, TypeIcon } from "@/views/fields"
import { Editable, Pick, Staging, Term, typing, useStaged } from "@/views/in-place"
import { shown, SYMBOL } from "@/views/program-inspect"
import { Collection, emptyOf, Inspect } from "@/views/inspect"
import { same } from "@/views/value-draft"
import { collection, Flag, Opens, Scalar, Truth } from "@/views/value-parts"
import { goToPlace, Places } from "@/views/places"
import { AddButton, Detail, Apply, CHANGED, Kind, LINE, RESOURCE, Running, Spec, goTo, takeover, useSpecs } from "@/views/scope-shared"

/** What the scope you're in can use, read on its own: kept up as it changes, and as the editor
 * changes it. A program in code has none of its own. It fills the height it's given, the switch
 * for the hidden ones and the Clean button at its foot. */
export function Resources({ where }: { where: Where }) {
  const [reference, setReference] = useState<Reference | null>(null)
  const load = useCallback(async () => {
    const answer = await window.proki.tool("reference")
    if (!answer.error) setReference(answer)
  }, [])
  useEffect(() => {
    load()
    const live = setInterval(load, 5000)
    window.addEventListener(CHANGED, load)
    return () => (clearInterval(live), window.removeEventListener(CHANGED, load))
  }, [load])
  const code = reference?.programs.find((p) => p.name === where.program)?.kind === "code"
  const { specs, error, setError, change, act } = useSpecs<GlobalSpecs | ProgramSpecs>(where.program, reference !== null && !code)
  if (!reference || (!specs && !code)) return <p className="p-3 text-xs text-muted-foreground">{error || "Loading…"}</p>
  const own = { variables: specs?.variables ?? [], signals: specs?.signals ?? [], rules: specs?.rules ?? [] }
  return (
    <div className="flex min-h-full flex-col gap-2 px-3 pt-3">
      {error && <ErrorDialog message={error} onClose={() => setError("")} />}
      <Kept key={`${where.scope}/${where.program}/${where.state}`} own={own} where={where} reference={reference} change={change} act={act} />
    </div>
  )
}

type Tab = Kind | "input"

const TABS: [Tab, string][] = [["input", "Inputs"], ["signal", "Signals"], ["variable", "Variables"], ["rule", "Rules"]]

const INPUTS = ["running", "app_name", "app_title", "tab_url", "label", "depth", "keys_pressed", "mouse_move", "mouse_click", "mouse_scroll", "time", "daytime", "weekday", "dd", "mm", "yy"]  // the inputs in this order: what's measured, then when

const SCOPES: [Scope, string][] = [["special", "Special"], ["global", "Global"], ["program", "Program"], ["state", "State"]]

/** What a scope can use: the inputs, or one kind at a time, by the scope it's from, from the
 * widest down to this one, each opened by its line (one at a time: this one's to start). This
 * part's own are edited and added to; the rest, from elsewhere, are read. Any line can be hidden,
 * kept so in this window; the hidden ones show only on their switch, greyed. */
function Kept({ own, where, reference, change, act }: {
  own: { variables: VariableSpec[]; signals: SignalSpec[]; rules: RuleSpec[] }  // every one of the part's, at any level
  where: Where
  reference: Reference
  change: Apply
  act: (changes: Change[]) => void
}) {
  const [tab, setTab] = useState<Tab>(() => recall("programs.kind", TABS.map(([k]) => k), "signal"))
  const [open, setOpen] = useState<Scope[]>([where.scope])  // the scopes open, any of them at once
  const [adding, setAdding] = useState<{ tab: Tab; scope: Scope } | null>(null)  // a new one being made, from which tab and scope
  const [hidden, setHidden] = useState(() => recall("programs.hidden", ["shown", "kept"], "kept") === "shown")
  const [hid, setHid]       = useState<string[]>(() => recallJson("programs.hid", []))  // each line hidden, as kind:name
  const any    = hid.filter((k) => k.startsWith(`${tab}:`)).length
  const all = [...own.variables, ...own.signals, ...own.rules]

  return (
    <section className="flex flex-1 flex-col gap-2">
      <Names reference={reference} own={all.map((s) => s.name)} />
      <div className="sticky top-0 z-10 -mx-3 -mt-3 bg-background px-3 pt-3 pb-1">  {/* pinned under the header as the lists scroll */}
       <div className="flex gap-1 rounded-lg bg-muted p-1">
        {TABS.map(([k, title]) => (
          <button key={k} aria-pressed={tab === k} onClick={() => (setTab(k), remember("programs.kind", k))}
                  className={cn("flex-1 rounded-md py-0.5 text-xs text-muted-foreground", tab === k && "bg-background font-medium text-foreground shadow-xs")}>
            {title}
          </button>
        ))}
       </div>
      </div>
      {TABS.map(([t]) => (  // each tab's lists stay in place, the other tabs' hidden, so a dialog opened from one stays as you browse
        <div key={t} hidden={t !== tab} className="flex flex-col gap-2">
          <Lists tab={t} active={t === tab} own={own} where={where} reference={reference} change={change} act={act} open={open} setOpen={setOpen} adding={adding?.tab === t ? adding.scope : null} setAdding={(scope) => setAdding(scope && { tab: t, scope })}
                 hidden={hidden} hid={hid} setHid={setHid} />
        </div>
      ))}
      <div className="sticky bottom-0 -mx-3 mt-auto flex items-center gap-2 border-t bg-background px-4 py-2 text-xs text-muted-foreground">
        <label className="flex items-center gap-2">
          <Switch size="sm" aria-label="Show hidden" checked={hidden} onCheckedChange={(on) => (setHidden(on), remember("programs.hidden", on ? "shown" : "kept"))} />
          Show hidden {any > 0 && <span className="tabular-nums">{any}</span>}
        </label>
        <Clean />
      </div>
    </section>
  )
}

/** One tab's lists of what a scope can use, by the scope each is from, widest first: every one stays in place (collapsed or on another tab it's only
 * hidden), so a dialog opened from a line stays open as you browse. */
function Lists({ tab, active, own, where, reference, change, act, open, setOpen, adding, setAdding, hidden, hid, setHid }: {
  tab: Tab
  active: boolean  // the tab shown: only it asks for a new one
  own: { variables: VariableSpec[]; signals: SignalSpec[]; rules: RuleSpec[] }
  where: Where
  reference: Reference
  change: Apply
  act: (changes: Change[]) => void
  open: Scope[]
  setOpen: (scopes: Scope[]) => void
  adding: Scope | null
  setAdding: (scope: Scope | null) => void
  hidden: boolean
  hid: string[]
  setHid: (hid: string[]) => void
}) {
  const kind = tab === "input" ? "signal" : tab
  const scopes = tab === "input" ? SCOPES.filter(([s]) => s === "global")  // the inputs: the app's, everywhere
                                 : SCOPES.filter(([s]) => s === "global" || (s === "special" ? kind === "variable" : s === "program" ? where.program !== null : where.state !== null))
  const full = (s: Spec) => (s.scope === "global" ? s.name : s.scope === "program" ? `${s.program}.${s.name}` : `${s.program}.${s.state}.${s.name}`)
  const rows = { variable: reference.variables, signal: reference.signals, rule: reference.rules }
  const veiled = (name: string) => hid.includes(`${tab}:${name}`)
  const veil   = (name: string) => {
    const next = veiled(name) ? hid.filter((k) => k !== `${tab}:${name}`) : [...hid, `${tab}:${name}`]
    setHid(next)
    rememberJson("programs.hid", next)
  }
  const found = (s: Spec) => ({ name: s.name, scope: s.scope, program: s.program, state: s.state })
  const add = (scope: Scope): Save => async (data) => {
    const mistake = await change([{ op: "add", kind, data: { ...data, program: where.program, state: scope === "state" ? where.state : null } }])
    if (!mistake) setAdding(null)
    return mistake
  }
  const of = (scope: Scope) => {
    const mine = (own[`${kind}s` as const] as Spec[]).filter((s) => s.scope === scope && (scope !== "state" || s.state === where.state) && (hidden || !veiled(full(s))))
    const taken = new Set(mine.map(full))
    const inside = scope === "program" ? `${where.program}.` : `${where.program}.${where.state}.`
    const outer = rows[kind].filter((r) => r.scope === scope && !taken.has(r.name) && (scope === "global" || scope === "special" || r.name.startsWith(inside)))
    return { mine, outer: outer.filter((r) => hidden || !veiled(r.name)) }
  }
  return (
    <>
      {scopes.map(([scope, title]) => {
        const { mine, outer } = tab === "input" ? { mine: [], outer: [] } : of(scope)
        const here = { ...where, scope }
        const shut = !open.includes(scope)
        const inputs = reference.inputs.filter((i) => hidden || !veiled(i.name)).sort((a, b) => INPUTS.indexOf(a.name) - INPUTS.indexOf(b.name))
        const lines = tab === "input" ? (inputs.length ? [<Inputs key="inputs" inputs={inputs} veiled={veiled} veil={veil} />] : []) : [
          ...mine.map((s, i): [string, ReactNode] => [full(s), (
            <KeptLine key={`${s.scope}:${i}`} veiled={veiled(full(s))} onVeil={() => veil(full(s))} kind={kind} spec={s} where={here} full={full(s)}
                      row={(rows[kind] as Row[]).find((r) => r.name === full(s))}
                      onSave={(data) => change([{ op: "update", kind, data: { ...found(s), changes: data } }])}
                      onDelete={() => act([{ op: "remove", kind, data: found(s) }])} />
          )]),
          ...outer.map((r): [string, ReactNode] => [r.name, (r as ObjectRow).fields
            ? <ObjectLine key={r.name} object={r as ObjectRow} label={r.name} veiled={veiled(r.name)} onVeil={() => veil(r.name)} />
            : <Outer key={r.name} kind={kind} row={r} scope={scope} program={where.program} veiled={veiled(r.name)} onVeil={() => veil(r.name)} />]),
        ].sort((a, b) => a[0].localeCompare(b[0])).map(([, line]) => line)
        if (scope === "special" && !lines.length) return null  // nothing to add to it: shown only with something in it
        return (
          <div key={scope} className="flex flex-col gap-0.5">
            <div className="group flex items-center gap-1">
              <button onClick={() => setOpen(shut ? [...open, scope] : open.filter((o) => o !== scope))}
                      aria-expanded={!shut} className="flex flex-1 items-center gap-1.5 rounded-md px-1 py-1 text-left hover:bg-background">
                <ChevronRight strokeWidth={3} className={cn("size-3.5 transition-transform", !shut && "rotate-90")} />
                <span className={cn("text-xs font-medium", shut && "text-muted-foreground")}>{title}</span>
                <span className="text-xs text-muted-foreground tabular-nums">{tab === "input" ? inputs.length : mine.length + outer.length}</span>
              </button>
              {scope !== "special" && tab !== "input" && (
                <AddButton label={`add to ${title.toLowerCase()}`} disabled={adding === scope}
                           onClick={() => (setOpen(shut ? [...open, scope] : open), setAdding(scope))} />
              )}
            </div>
            {(
              <div hidden={shut} className="flex flex-col gap-0.5 pl-3">
                {adding === scope && <Defining kind={kind} where={here} onSave={add(scope)} onClose={() => setAdding(null)} />}
                {lines.length === 0 && <p className="px-1 text-xs text-muted-foreground">None.</p>}
                {lines}
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}

/** Takes out what no automation's decision uses, asked first; what it's for on hover. */
function Clean() {
  const [failed, setFailed] = useState("")
  const clean = async () => {
    const answer = await window.proki.tool("remove_unused")
    setFailed(answer.error ?? "")
    if (!answer.error) window.dispatchEvent(new Event(CHANGED))
  }
  return (
    <Confirm title="Clean up?" action="Clean" onConfirm={clean}
             description="Removes what no automation uses. This can't be undone.">
      <Button size="xs" variant="ghost" className={cn("ml-auto", failed && "text-destructive")}
              title={failed || "Remove what no automation uses"}>
        Clean
      </Button>
    </Confirm>
  )
}

/** One of this part's own: its name (its description on hover) and its value, on a line; click
 * to see and edit it, in a panel over the page. */
type ObjectField = VarDetail & { shown?: boolean }

type ObjectRow   = VarDetail & { fields?: ObjectField[] }

/** A record or an object variable, as any line is: its value as `{…}`, a click on it opens its dialog, where its fields are. */
function ObjectLine({ object, label, veiled, onVeil }: { object: ObjectRow; label: string; veiled?: boolean; onVeil: () => void }) {
  const [viewing, setViewing] = useState(false)
  const fields  = object.fields ?? []
  const special = (object as { scope?: Scope }).scope === "special"  // the app's own (work, track): each field a value of its own
  const value   = special ? Object.fromEntries(fields.map((f) => [f.name.slice(object.name.length + 1), f.value])) : object.value  // the app's own (work, track): its fields'
  return (
    <PanelLine icon={<TypeIcon type={object.type ?? "object"} />} label={label} name={object.name} desc={object.desc} type={object.type ?? "object"} dim={veiled} onOpen={() => setViewing(true)}>
      <Value value={value} name={object.name} type={object.type ?? "object"} record={special ? undefined : object.name}
             opens={special ? (key, v, t) => (
               <span className="flex *:w-auto *:justify-start"><Value value={v} name={`${object.name}.${key}`} type={t} record={`${object.name}.${key}`} /></span>
             ) : undefined} />
      <Veil name={object.name} veiled={veiled} onClick={onVeil} />
      {viewing && <Viewing object={object} label={label} value={value} onClose={() => setViewing(false)} />}
    </PanelLine>
  )
}

/** A variable the app keeps, over the page, as any other: what it is, its value, what writes and
 * reads it, and its fields; a record's, each with how it's worked out, to change; else each
 * clicked to see what it is. */
function Viewing({ object, label, value, onClose }: { object: ObjectRow; label: string; value: unknown; onClose: () => void }) {
  const [seen, setSeen] = useState<ObjectField | null>(null)
  const fields = object.fields ?? []
  const short  = (f: VarDetail) => f.name.slice(object.name.length + 1)
  return (
    <Seen kind="variable" row={object as Row} name={label} full={object.name} desc={object.desc} type={object.type ?? "object"} value={value}
          locked="it's kept by the app" onClose={onClose}>
      <SchemaFields name={label} type={{ type: "object", properties: Object.fromEntries(fields.map((f) => [short(f), { ...schemaOf(f.type ?? "any"), description: f.desc }])) } as Type}
                    onOpen={(key) => setSeen(fields.find((f) => short(f) === key) ?? null)} />
      {seen && (
        <Seen kind="variable" row={{ ...seen, scope: "special" } as Row} name={seen.name} full={seen.name} desc={seen.desc} type={seen.type} value={seen.value} settable={collection(seen.value)} locked="it's kept by the app" onClose={() => setSeen(null)} />
      )}
    </Seen>
  )
}

/** A line of the panel: its icon and name (what it is, on hover), then what comes after (its value, its hide button, the dialog it opens); a click
 * anywhere on it calls `onOpen`, the dialogs open before it closed. `dim`: its name is not as strong. */
function PanelLine({ icon, label, name, desc, type, dim, onOpen, children }: {
  icon: ReactNode; label: string; name: string; desc?: string; type?: Type; dim?: boolean; onOpen: () => void; children: ReactNode
}) {
  const open = () => (takeover(), onOpen())
  return (
    <div onClick={(e) => e.currentTarget.contains(e.target as Node) && open()} className={LINE}>
      <button onClick={open} className="flex min-w-0 flex-1 items-center gap-2 text-left">
        {icon}
        <span title={[name, hover({ desc, type })].filter(Boolean).join(" · ")} className={cn("min-w-0 flex-1 truncate font-mono", dim ? "text-muted-foreground" : "font-medium")}>{label}</span>
      </button>
      {children}
    </div>
  )
}

function KeptLine({ kind, spec, where, full, row, veiled, onVeil, onSave, onDelete }: {
  kind: Kind
  spec: Spec
  where: Where
  full: string
  row?: Row         // as it runs (none: not built yet)
  veiled?: boolean  // a hidden one, shown on the switch
  onVeil: () => void
  onSave: Save
  onDelete: () => void
}) {
  const [open, setOpen] = useState(false)
  const type  = (row as { type?: Type } | undefined)?.type ?? (spec as { type?: Type }).type  // not built yet: the type it's made with
  const value = now(kind, row)
  const app   = (row as { app?: boolean } | undefined)?.app  // the app reads it: it can't be removed, nor retyped
  return (
    <PanelLine icon={<Lead kind={kind} type={type} />} label={spec.name} name={spec.name} desc={spec.desc} type={type} dim={veiled} onOpen={() => setOpen(true)}>
      <Value value={value} rule={kind === "rule"} name={spec.name} type={type} record={full} />
      <Veil name={full} veiled={veiled} onClick={onVeil} />
      {open && (
        <Seen kind={kind} row={row} spec={spec} name={spec.name} full={full} desc={spec.desc} type={type} value={value}
              kept={app ? "the app reads it" : undefined} onSave={onSave} onDelete={app ? undefined : onDelete} onClose={() => setOpen(false)} />
      )}
    </PanelLine>
  )
}

type Row = Reference["variables"][number] | Reference["signals"][number] | Reference["rules"][number]

/** A list or record variable's starting value, held in the dialog (as the text the spec keeps it in) and changed in its table; a table's records start empty. */
function StartsAs({ type, name, was }: { type?: Type; name: string; was: string }) {
  const st = useStaged()
  const text = (st?.patch.value as string | undefined) ?? was
  const held = (() => { try { return text ? JSON.parse(text) : null } catch { return null } })()
  return <span className="inline-flex font-mono"><Collection value={held} type={type} title={name} onPut={async (v) => (st?.put("value", JSON.stringify(v), was), null)} /></span>
}

/** Where a variable starts, changed where it's read (a flag, a table or text) and kept with the dialog's Save; `type`: the one it will have. */
function Starts({ type, name, was, editable }: { type?: Type; name: string; was: string; editable: boolean }) {
  const st   = useStaged()!
  const text = (st.patch.value as string | undefined) ?? was
  if (emptyOf(type) !== undefined) return <StartsAs type={type} name={name} was={was} />
  if (said(type) === "boolean" && editable) return <Flag value={text === "true" ? true : text === "false" ? false : null} changed={st.lit("value")} onPut={(on) => st.put("value", String(on), was)} />
  return <Editable label="Starts as" code list={NAMES} placeholder="unknown" {...st.field("value", was, editable)} />
}

/** A variable's value set by you, now (the mistake, if any). */
async function setValue(name: string, to: unknown): Promise<string | null> {
  const answer = await window.proki.tool("set_value", { name, value: to })
  if (!answer.error) window.dispatchEvent(new Event(CHANGED))
  return (answer.error as string | undefined) ?? null
}

type Rec = Record<string, unknown>

/** A variable's value kept as `after`. A table's records are kept by the changes that make it (one taken out, added, changed or moved: as the board
 * itself does them), anything else as one value. */
async function keepValue(name: string, before: unknown, after: unknown): Promise<string | null> {
  const read = Array.isArray(after) ? await window.proki.fields({ op: "read", record: name }) : null
  if (!read || read.error || !read.records.includes(name)) return setValue(name, after)
  const keys  = new Set(read.fields.map((f) => f.key))
  const were  = (Array.isArray(before) ? before : []) as Rec[]
  const rows  = after as Rec[]
  const ids   = new Set(rows.map((r) => r.id))
  const call  = async (tool: "add_record" | "change_record" | "remove_record" | "move_record", args: object) => (await window.proki.tool(tool, { name, ...args })) as { error?: string; id?: number }
  for (const r of were.filter((r) => !ids.has(r.id))) {
    const done = await call("remove_record", { id: r.id })
    if (done.error) return done.error
  }
  const order: number[] = []
  for (const row of rows) {
    const fields = Object.fromEntries(Object.entries(row).filter(([k]) => keys.has(k)))
    if (row.id == null) {
      const done = await call("add_record", { fields })
      if (done.error) return done.error
      order.push(done.id!)
      continue
    }
    const old     = were.find((r) => r.id === row.id)
    const changed = Object.fromEntries(Object.entries(fields).filter(([k, v]) => !same(old?.[k], v)))
    if (Object.keys(changed).length) {
      const done = await call("change_record", { id: row.id, fields: changed })
      if (done.error) return done.error
    }
    order.push(row.id as number)
  }
  const there = [...were.map((r) => r.id as number).filter((id) => ids.has(id)), ...order.filter((id) => !were.some((r) => r.id === id))]  // as it stands now
  if (!same(there, order)) {
    for (let i = order.length - 1; i >= 0; i--) {
      const done = await call("move_record", { id: order[i], before: order[i + 1] ?? null })
      if (done.error) return done.error
    }
  }
  window.dispatchEvent(new Event(CHANGED))
  return null
}

/** How to set a variable's value, when you can (it has a `user` write): none otherwise. Asked once `active`. */
export function useSetter(name: string | undefined, active: boolean, value: unknown): ((to: unknown) => Promise<string | null>) | undefined {
  const [yours, setYours] = useState(false)
  useEffect(() => {
    if (!name || !active) return
    let live = true
    window.proki.tool("links", { name }).then((answer) => live && setYours(!answer.error && (answer as Links).writes.some((w) => w.from === "user" && !w.program)))
    return () => void (live = false)
  }, [name, active])
  return yours && name ? (to) => keepValue(name, value, to) : undefined
}

/** Its value now: a rule's, its chance. */
const now = (kind: Kind, row?: Row) => kind === "rule" ? (row as Reference["rules"][number] | undefined)?.chance : (row as { value?: unknown } | undefined)?.value

/** One of a wider scope's, read here: click it to see what it is, its value, and where it's
 * changed (the app's own: nowhere; a global one another automation made: in that one). */
function Outer({ kind, row, scope, program, veiled, onVeil }: { kind: Kind; row: Row; scope: Scope; program: string | null; veiled: boolean; onVeil: () => void }) {
  const [open, setOpen] = useState(false)
  const type   = (row as { type?: Type }).type
  const value  = now(kind, row)
  const short  = scope === "global" || scope === "special" ? row.name : row.name.split(".").at(-1)!  // as an expression here says it
  const code   = (row as { from?: string }).from === "code" || scope === "special"
  const there  = scope === "program" && !code ? { program, state: null } : null
  const locked = code ? "it's kept by the app" : { special: "", global: "another automation made it", program: "", state: "this state's question sets it" }[scope]
  return (
    <PanelLine icon={<Lead kind={kind} type={type} />} label={short} name={row.name} desc={row.desc} type={type} dim={veiled} onOpen={() => setOpen(true)}>
      <Value value={value} rule={kind === "rule"} name={short} type={type} record={code && !collection(value) ? undefined : row.name} />
      <Veil name={row.name} veiled={veiled} onClick={onVeil} />
      {open && (
        <Mine kind={kind} full={row.name}>
          {(own) => own ? (
            <Seen kind={kind} row={row} spec={own.spec} name={short} full={row.name} desc={row.desc} type={type ?? (own.spec as { type?: Type }).type} value={value}
                  kept={(row as { app?: boolean }).app ? "the app reads it" : undefined} onSave={own.onSave} onDelete={(row as { app?: boolean }).app ? undefined : own.onDelete} onClose={() => setOpen(false)} />
          ) : (
            <Seen kind={kind} row={row} name={short} full={row.name} desc={row.desc} type={type} value={value} settable={!code || collection(value)}
                  locked={there ? undefined : locked} kept={there ? "delete it in the automation" : undefined}
                  onEdit={there ? () => (setOpen(false), goTo(there)) : undefined} onClose={() => setOpen(false)} />
          )}
        </Mine>
      )}
    </PanelLine>
  )
}

/** A variable, a signal or a rule, over the page: what it is, its type, its value now, how it's
 * worked out, its fields, what writes it and what reads it. Yours
 * (`spec`, `onSave`): each part is changed where it is, underlined as you point at it. Edit and
 * Delete sit by its close button; without `onEdit`, `onDelete`, each is greyed and says why on
 * hover (`locked`: both, `kept`: Delete). A variable's fields: a record's, with how each is worked
 * out, else `children`, else as its type says. `full`: its name as the app knows it; Escape, while a
 * part is being changed, puts that part back and leaves the dialog open. */
function Seen({ kind, row, spec, name, full, desc, type, value, settable: open = true, locked, kept, history, onHistory, onSave, onEdit, onDelete, onClose, onLeave, children }: {
  kind: Kind | "input"
  row?: Row         // as it runs (none: not built yet)
  spec?: Spec       // yours, to change
  name: string      // as an expression here says it
  full: string
  desc?: string
  type?: Type
  value: unknown
  settable?: boolean  // its value set by you, if nothing else says no (the app's own: no)
  locked?: string
  kept?: string
  history?: string  // an input's: how much of it is kept
  onHistory?: (text: string) => Promise<string | null>
  onSave?: Save
  onEdit?: () => void
  onDelete?: () => void
  onClose: () => void
  onLeave?: () => void  // going to a place of it: every dialog under it closing too (none: only this one)
  children?: ReactNode
}) {
  const [links, setLinks] = useState<Links | null>(null)
  useEffect(() => (window.addEventListener(RESOURCE, onClose), () => window.removeEventListener(RESOURCE, onClose)), [onClose])
  useEffect(() => {
    window.proki.tool("links", { name: full }).then((answer) => setLinks(answer.error ? null : answer))
  }, [full])
  const save    = onSave && ((changes: Record<string, unknown>) => onSave(changes))
  const rule    = kind === "rule" ? row as Reference["rules"][number] | undefined : undefined
  const ruled   = kind === "rule" ? spec as RuleSpec | undefined : undefined
  const signal  = kind === "signal" ? spec as SignalSpec | undefined : undefined
  const expr    = kind === "signal" ? (row as { expr?: string } | undefined)?.expr : undefined
  const persist = kind === "variable" ? (row as { persist?: boolean } | undefined)?.persist : undefined
  const scope   = (row as { scope?: Scope } | undefined)?.scope ?? spec?.scope
  const own     = (spec as { type?: Type } | undefined)?.type
  const lasts   = persist ? "across restarts" : { special: "", global: "until Proki restarts", program: "until the automation starts over", state: "until it leaves this state" }[scope ?? "global"]
  const user    = open && kind === "variable" && !!links?.writes.some((w) => w.from === "user" && !w.program)
  const put = (to: unknown) => keepValue(full, value, to)
  const worked: Worked | undefined = kind === "signal" ? {
    said:   signal?.expr ?? expr ?? "",
    detail: signal && save ? <Formula expr={signal.expr} />
                           : <Expr className="block rounded-md bg-muted px-2 py-1.5 break-words">{expr ?? ""}</Expr>,
  } : undefined
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg sm:has-[[data-record]]:max-w-2xl"
                     onEscapeKeyDown={typing}>
        <Staging reserve={!!save} onSave={async (patch) => {
          const { history: spanned, ...rest } = patch
          const mistake = spanned === undefined ? null : await onHistory?.(spanned as string)
          const failed = mistake ?? (Object.keys(rest).length ? await save?.(sent(rest)) ?? null : null)
          const gone   = kind === "variable" && !failed && "type" in rest && collection(value) && !Array.isArray(value)
            ? fieldKeys(own ?? type).filter((k) => !fieldKeys(rest.type as Type).includes(k)) : []  // a field taken out takes its value with it
          if (gone.length) await setValue(full, Object.fromEntries(Object.entries(value as object).filter(([k]) => !gone.includes(k))))
          return failed
        }}>
        {(st) => <>
        <DialogHeader>
          <DialogTitle className="flex min-w-0 items-center gap-2 pr-24 font-mono">
            <Lead kind={kind} type={type} className="size-4" />
            <Editable label="Name" {...st.field("name", name, !!save)} className="-mb-1 truncate pb-1 font-mono text-foreground" />
          </DialogTitle>
          <DialogDescription asChild>
            <div><Editable label="Description" long placeholder="No description" {...st.field("desc", desc ?? "", !!save)} /></div>
          </DialogDescription>
        </DialogHeader>
        <Corner what={kind} name={name} locked={locked} kept={kept ?? (links?.reads.length ? "something reads it (Read by): take that out first" : undefined)} onEdit={onEdit}
                gone={{ variable: kindOf(type) === "list" && (type as { items?: { type?: string } }).items?.type === "object" ? "Its records go with it." : "Its saved value goes with it.",
                        signal: "Its saved history goes with it." }[kind as string]}
                onDelete={onDelete && !links?.reads.length ? () => (onDelete(), onClose()) : undefined} />
        <dl className="grid grid-cols-[6rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-2 border-t pt-4 text-xs">
          {kind !== "rule" && <><Term>Type</Term><dd><TypeChange type={type} own={own} editable={!!save && !kept} kinds={kind === "signal" ? SCALARS : undefined} /></dd></>}
          <Term>Now</Term>
          <dd className="flex *:w-auto *:justify-start"><Value value={value} rule={kind === "rule"} name={name} full onPut={user ? put : undefined} string={said(type) === "string"} type={type} record={full} /></dd>
          {rule && <Fires rule={rule} ruled={save ? ruled : undefined} />}
          {kind === "variable" && <ItemChange type={type} own={own} editable={!!save && !kept} />}
          {kind === "variable" && spec && <><Term>Starts as</Term><dd><Starts type={(st.patch.type as Type | undefined) ?? type} name={name} was={valueText((spec as VariableSpec).value)} editable={!!save} /></dd></>}
          {kind === "signal" && (
            <>
              <Term>Keep</Term>
              <dd><SpanField label="Keep" name="backfill" was={String(signal?.backfill ?? (row as { backfill?: number | null } | undefined)?.backfill ?? "")} editable={!!signal && !!save} /></dd>
            </>
          )}
          {kind === "input" && (
            <>
              <Term>Keep</Term>
              <dd><SpanField label="Keep" name="history" was={history ?? ""} editable={!!onHistory} /></dd>
            </>
          )}
          {kind === "variable" && lasts && <><Term>Kept</Term><dd>{lasts}</dd></>}
        </dl>
        {kind === "variable" ? <RecordFields record={full}>{children ?? (save && !kept ? <StagedFields name={name} type={type} own={own} /> : <SchemaFields name={name} type={type ?? "any"} />)}</RecordFields> : <SchemaFields name={name} type={type ?? "any"} />}
        {links && <Linked links={links} worked={worked} rule={kind === "rule"} measured={kind === "input"} user={user} onLeave={onLeave ?? onClose} />}
        </>}
        </Staging>
      </DialogContent>
    </Dialog>
  )
}

/** What a resource's dialog held, as the changes it sends: each as its text says (a name trimmed, a number, a span). */
const SENT: Record<string, (text: string) => Record<string, unknown>> = {
  name:     (t) => ({ name: t.trim() }),
  lhs:      (t) => ({ lhs: parseSide(t) }),
  rhs:      (t) => ({ rhs: parseSide(t) }),
  softness: (t) => ({ softness: Number(t) || 0 }),
  level:    (t) => ({ level: Math.round(Number(t)) || 1 }),
  value:    (t) => ({ value: parseValue(t) }),
  backfill: (t) => ({ backfill: parseSpan(t), persist: parseSpan(t) !== null }),
}

const sent = (patch: Record<string, unknown>) => Object.assign({}, ...Object.entries(patch).map(([k, v]) => (SENT[k] ? SENT[k](v as string) : { [k]: v })))

/** A signal's expression, changed where it's read; kept with the dialog's Save. */
function Formula({ expr }: { expr: string }) {
  const st = useStaged()
  return <Editable label="Expression" code long list={NAMES} placeholder="Expression" className="w-full rounded-md bg-muted px-2 py-1.5 text-xs" {...(st?.field("expr", expr) ?? { value: expr })} />
}

/** A rule's own rows in its dialog: when it fires, how soft it is and where it votes, each changed where it's read, kept with the
 * dialog's Save. `ruled`: its spec (none: read only). */
function Fires({ rule, ruled }: { rule: Reference["rules"][number]; ruled?: RuleSpec }) {
  const st   = useStaged()
  const f    = (key: string, was: string) => st?.field(key, was, !!ruled) ?? { value: was }
  const Num  = ({ label, field, was, hint }: { label: string; field: string; was: string; hint: string }) => (
    <dd className="flex items-baseline gap-2 whitespace-nowrap">
      <span className="w-8 shrink-0"><Editable label={label} {...f(field, was)} /></span>
      <span className="text-muted-foreground">{hint}</span>
    </dd>
  )
  return (
    <>
      <Term>Condition</Term>
      <dd className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1 break-words">
        {ruled ? (
          <>
            <Editable label="Left side" code long list={NAMES} placeholder="Left side" {...f("lhs", String(ruled.lhs))} />
            <ComparedBy cmp={ruled.cmp} />
            <Editable label="Right side" code long list={NAMES} placeholder="Right side" {...f("rhs", String(ruled.rhs))} />
          </>
        ) : <Expr>{`${rule.lhs} ${SYMBOL[rule.cmp]} ${rule.rhs}`}</Expr>}
      </dd>
      <Term>Softness</Term>
      <Num label="Softness" field="softness" was={String(ruled?.softness ?? rule.softness)} hint="0 is hard" />
      <Term>Level</Term>
      <Num label="Level" field="level" was={String(ruled?.level ?? rule.level)} hint="higher votes first" />
    </>
  )
}

/** How a rule compares its sides, picked from the symbols; kept with the dialog's Save. */
function ComparedBy({ cmp }: { cmp: string }) {
  const staged = useStaged()
  const now = (staged?.patch.cmp as string | undefined) ?? cmp
  return (
    <Pick label="Compared by" value={now} changed={now !== cmp} className="ml-[1.125rem] font-mono" options={Object.entries(SYMBOL).map(([k, sym]) => [k, sym])}
          onPick={staged ? (k) => staged.put("cmp", k, cmp) : undefined} />
  )
}

/** How it's worked out, as Linked's expr row says it (`said`) and opens it (`detail`). */
type Worked = { said: string; detail: ReactNode }

/** What each kind of writer does, in a word (a reader's, below, is its MEANS). */
const WROTE = { expr: "Its expression, worked out each cycle", auto: "Actions in automations that set it", proki: "The app, as it works", measured: "The app, measuring each cycle", user: "You: click its value in Now" } as const

/** What each kind of reader does with an input, in a word. */
const MEANS = { auto: "Transitions and actions in automations", rule: "Rules that compare it", signal: "Signals measured continuously", variable: "Variables that start from it", proki: "The app reads it to show your day" } as const

/** What writes it and what reads it, each a table: a chip a row (expr, auto, user; the
 * automations, rules, signals, variables, the app), what it is beside it; a row clicked opens it
 * over the dialog. `worked`: its expr row; `user`: you set it (its row says where). The
 * automations' rows go where they are, lit, from any page; `onLeave`: the dialog closing. */
function Linked({ links, worked, rule, measured, user: set, onLeave }: {
  links: Links
  worked?: Worked
  rule?: boolean      // a rule's: worked out in its own dialog, nothing to list as written
  measured?: boolean  // an input's: the app measures it (else, it keeps it)
  user?: boolean      // you set it by hand, from its Now
  onLeave: () => void
}) {
  const [open, setOpen] = useState<string | null>(null)
  const [seen, setSeen] = useState<{ kind: Kind; name: string } | null>(null)
  const auto  = links.writes.filter((w) => w.program)
  const user  = set && links.writes.some((w) => w.from === "user" && !w.program)
  const flows = links.reads.filter((r) => r.program)
  const named = (by: string) => links.reads.filter((r) => r.by === by).map((r) => r.name ?? "")
  const shown = worked ?? links.writes.filter((w) => w.from === "expr").map((w): Worked => ({ said: w.text ?? "", detail: <Expr className="block rounded-md bg-muted px-2 py-1.5 break-words">{w.text ?? ""}</Expr> }))[0]
  const visit = (p: Place) => (setOpen(null), onLeave(), goToPlace(p))
  const written = [
    shown && { id: "expr", chip: <Chip name="expr" />, said: WROTE.expr },
    auto.length > 0 && { id: "auto", chip: <Chip name="auto" />, said: WROTE.auto },
    links.writes.some((w) => w.from === "proki") && { id: "proki", chip: <Pill by="proki" />, said: measured ? WROTE.measured : WROTE.proki },
    user && { id: "user", chip: <Chip name="user" />, said: WROTE.user },
  ].filter(Boolean) as Entry[]
  const read = [
    flows.length > 0 && { id: "auto", chip: <Pill by="auto" />,
                          said: MEANS.auto },
    ...(["rule", "signal", "variable"] as const).map((by) => named(by).length > 0 && { id: by, chip: <Pill by={by} />, said: MEANS[by] }),
    links.reads.some((r) => r.by === "app") && { id: "proki", chip: <Pill by="proki" />, said: MEANS.proki },
  ].filter(Boolean) as Entry[]
  return (
    <TooltipProvider delayDuration={300}>
      <dl className="grid grid-cols-[6rem_minmax(0,1fr)] items-center gap-x-3 gap-y-2 border-t pt-4 text-xs">
        {!rule && <Chips title="Written by" rows={written} empty="None." onOpen={setOpen} />}
        <Chips title="Read by" rows={read} empty="None." onOpen={(id) => setOpen(`read:${id}`)} />
      </dl>
      {open === "expr" && shown && <Detail title={<><Chip name="expr" /> Worked out</>} about="From its expression, each cycle." onClose={() => setOpen(null)}>{shown.detail}</Detail>}
      {(open === "auto" || open === "read:auto") && (
        <Detail title={open === "auto" ? <><Chip name="auto" /> Written by the automations</> : <><Pill by="auto" /> Read by the automations</>}
                about="Click one to go there." wide onClose={() => setOpen(null)}>
          <Places places={open === "auto" ? auto : flows} onVisit={visit} />
        </Detail>
      )}
      {open === "user" && <Detail title={<><Chip name="user" /> Set by you</>} about="Click its value in Now, above, and change it there." onClose={() => setOpen(null)} />}
      {open === "proki" && (
        <Detail title={<><Pill by="proki" /> Written by</>} onClose={() => setOpen(null)}
                about={measured ? "The app measures it each cycle, from what your computer recorded, or the clock. Nothing else can write it."
                                : "The app keeps it up as it works: from your records, your sessions, what you do in it."} />
      )}
      {(open === "read:rule" || open === "read:signal" || open === "read:variable") && (
        <Detail title={<><Pill by={open.slice(5) as Reader} /> Read by</>} about={open === "read:variable" ? "Each starts from its value." : `Each ${open.slice(5)} is worked out from it.`} onClose={() => setOpen(null)}>
          <ul className="flex flex-col rounded-md border text-xs">
            {named(open.slice(5)).map((n) => (
              <li key={n} className="border-b last:border-b-0">
                <button type="button" onClick={() => setSeen({ kind: open.slice(5) as Kind, name: n })}
                        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left hover:bg-muted/60">
                  <code className="font-mono">{n}</code><ChevronRight className="size-3.5 text-muted-foreground" />
                </button>
              </li>
            ))}
          </ul>
        </Detail>
      )}
      {open === "read:proki" && (
        <Detail title={<><Pill by="proki" /> Read by</>} onClose={() => setOpen(null)}
                about="The app reads it to show you your day, so it can't be removed, and its type stays as the app needs it." />
      )}
      {seen && <SeenNamed {...seen} onClose={() => setSeen(null)} onLeave={() => (setSeen(null), setOpen(null), onLeave())} />}
    </TooltipProvider>
  )
}

/** A spec's full name, as the engine says it. */
const fullOf = (s: Spec) => (s.scope === "global" ? s.name : s.scope === "program" ? `${s.program}.${s.name}` : `${s.program}.${s.state}.${s.name}`)

/** The spec behind a name, wherever it's made (the global scope's, or an automation's), with how to change it: so a resource you can
 * use here you can change here. `children`: given it, or null when no spec is behind it (the app's own). */
function Mine({ kind, full, children }: { kind: Kind; full: string; children: (own: { spec: Spec; onSave: Save; onDelete: () => void } | null) => ReactNode }) {
  const [spec, setSpec] = useState<Spec | null | undefined>(undefined)
  useEffect(() => {
    let live = true
    ;(async () => {
      const known = await window.proki.tool("reference")
      const parts = [null, ...(known.error ? [] : known.programs.filter((p: Running) => p.kind === "config").map((p: Running) => p.name))]
      for (const part of parts) {
        const answer = await window.proki.tool("program_specs", { name: part })
        const hit = answer.error ? undefined : (answer[`${kind}s`] as Spec[] | undefined)?.find((s) => fullOf(s) === full)
        if (hit) return live && setSpec(hit)
      }
      if (live) setSpec(null)
    })()
    return () => void (live = false)
  }, [kind, full])
  if (spec === undefined) return null
  const apply = async (changes: Change[]) => {
    const answer = await window.proki.tool("apply_changes", { changes })
    if (answer.error) return answer.error as string
    window.dispatchEvent(new Event(CHANGED))
    return null
  }
  const at = spec && { name: spec.name, scope: spec.scope, program: spec.program, state: spec.state }
  return children(spec && at ? {
    spec,
    onSave:   (changes) => apply([{ op: "update", kind, data: { ...at, changes } }]),
    onDelete: () => void apply([{ op: "remove", kind, data: at }]),
  } : null)
}

/** A signal, a variable or a rule found by its full name, over the dialog, as it runs: read
 * here; changed in its own scope. `onLeave`: going to a place of it, every dialog closing. */
function SeenNamed({ kind, name, onClose, onLeave }: { kind: Kind; name: string; onClose: () => void; onLeave: () => void }) {
  const [row, setRow] = useState<Row | null | undefined>(undefined)
  useEffect(() => {
    window.proki.tool("reference").then((r) => setRow(r.error ? null : ({ variable: r.variables, signal: r.signals, rule: r.rules }[kind] as Row[]).find((x) => x.name === name) ?? null))
  }, [kind, name])
  if (row === undefined) return null
  if (row === null) return <Detail title={<code>{name}</code>} about="It isn't running now." onClose={onClose} />
  const scope = (row as { scope: Scope }).scope
  const code  = (row as { from?: string }).from === "code" || scope === "special"
  return (
    <Mine kind={kind} full={name}>
      {(own) => own ? (
        <Seen kind={kind} row={row} spec={own.spec} name={name} full={name} desc={row.desc} type={(row as { type?: Type }).type} value={now(kind, row)}
              kept={(row as { app?: boolean }).app ? "the app reads it" : undefined} onSave={own.onSave} onDelete={(row as { app?: boolean }).app ? undefined : own.onDelete} onClose={onClose} onLeave={onLeave} />
      ) : (
        <Seen kind={kind} row={row} name={name} full={name} desc={row.desc} type={(row as { type?: Type }).type} settable={collection(now(kind, row))}
              value={now(kind, row)} locked={code ? "it's kept by the app" : "change it in its own scope"} onClose={onClose} onLeave={onLeave} />
      )}
    </Mine>
  )
}

type Entry = { id: string; chip: ReactNode; said: string }  // said: what it means, on hover

/** What writes it, or reads it, as a line: its title, then a chip a kind (what it means on hover); a chip clicked opens it. */
function Chips({ title, rows, empty, onOpen }: { title: string; rows: Entry[]; empty: string; onOpen: (id: string) => void }) {
  return (
    <>
      <dt className="text-muted-foreground">{title}</dt>
      <dd className="flex min-w-0 flex-wrap items-center gap-1.5">
        {rows.length === 0 ? <span className="text-muted-foreground">{empty}</span> : rows.map((r) => (
          <button key={r.id} type="button" title={r.said} onClick={() => onOpen(r.id)} className="flex rounded-md hover:opacity-80">{r.chip}</button>
        ))}
      </dd>
    </>
  )
}


/** A dialog's Delete, by its close button, greyed when it can't be done and saying why on hover (`locked`: it's read-only,
 * `kept`: it can't be deleted); `gone`: what's lost with it, as Delete asks. `onEdit`: where it's changed, elsewhere (its automation). */
export function Corner({ what, name, locked, kept, gone, onEdit, onDelete }: {
  what: string; name: string; locked?: string; kept?: string; gone?: string; onEdit?: () => void; onDelete?: () => void
}) {
  const why = locked ? `This ${what} is read-only: ${locked}` : `This ${what} can't be deleted: ${kept}`
  return (
    <div className="absolute top-2 right-10 flex">
      {onEdit && <Button size="icon-sm" variant="ghost" aria-label={`Edit the ${what} ${name}`} title="Edit, in its automation" onClick={onEdit}><Pencil /></Button>}
      {onDelete ? (
        <Confirm title={`Delete the ${what} “${name}”?`} description={[gone, "This can't be undone."].filter(Boolean).join(" ")} action={`Delete ${what}`} onConfirm={onDelete}>
          <Button size="icon-sm" variant="ghost" aria-label={`Delete the ${what} ${name}`} title="Delete"><Trash2 /></Button>
        </Confirm>
      ) : (
        <span title={why}><Button size="icon-sm" variant="ghost" aria-label={`Delete the ${what} ${name}`} disabled><Trash2 /></Button></span>
      )}
    </div>
  )
}

/** A line's hide button, grown out at the line's end as you point at it; a hidden line's show button, always there. */
function Veil({ name, veiled, onClick }: { name: string; veiled?: boolean; onClick: () => void }) {
  return (
    <Button size="icon-xs" variant="ghost" aria-label={`${veiled ? "Show" : "Hide"} ${name}`} title={veiled ? "Show it" : "Hide it"} onClick={(e) => (e.stopPropagation(), onClick())}
            className={cn("h-5! shrink-0 text-muted-foreground transition-[width,margin,opacity] duration-150 [&_svg]:size-3.5",
                          veiled ? "w-5!" : "-ml-2 w-0! overflow-hidden p-0 opacity-0 group-hover/line:ml-0 group-hover/line:w-5! group-hover/line:opacity-100 focus-visible:ml-0 focus-visible:w-5! focus-visible:opacity-100")}>
      {veiled ? <Eye /> : <EyeOff />}
    </Button>
  )
}

/** A new variable, signal or rule, over the page, laid out as its dialog is once made: its name the title, its description under it,
 * each changed where it's read, and kept with Save. Yours once made: changed where it is, in its own dialog. */
function Defining({ kind, where, onSave, onClose }: { kind: Kind; where: Where; onSave: Save; onClose: () => void }) {
  const dirty = useRef(false)
  const kept = (e: Event) => dirty.current && e.preventDefault()  // Escape or a click outside closes it only untouched
  const away = (e: Event) => ((e.target as Element | null)?.closest?.("[data-bubble-panel]") ? e.preventDefault() : kept(e))  // browsing the panel never closes it
  const made = async (patch: Record<string, unknown>) => {
    const given = sent(patch)
    const type  = (given.type as Type | undefined) ?? "any"
    const data  = {
      variable: { value: null },
      signal:   { expr: "", backfill: null, persist: false },
      rule:     { lhs: "", cmp: "gt", rhs: "", softness: 0, level: 1 },
    }[kind]
    const table = kind === "variable" && where.scope === "global" && kindOf(type) === "list" && ((type as { items?: { type?: string } }).items?.type === "object")  // a table: made empty, its rows added after
    const rows  = table && typeof given.value === "string" ? JSON.parse(given.value) as Rec[] : []
    const mistake = await onSave({ name: "", desc: "", ...data, ...given, ...(table ? { value: null } : {}), ...(kind === "rule" ? {} : { type }), scope: where.scope })
    if (mistake) return mistake
    for (const fields of rows) await window.proki.tool("add_record", { name: given.name, fields })
    onClose()
    return null
  }
  const rule = { lhs: "", cmp: "gt", rhs: "", softness: 0, level: 1 }
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent onEscapeKeyDown={(e) => (typing(e), kept(e))} onInteractOutside={away}
                     className="max-h-[85vh] overflow-x-hidden overflow-y-auto sm:max-w-lg sm:has-[[data-record]]:max-w-2xl">
        <Staging onCancel={onClose} onSave={made}>
          {(st) => {
            dirty.current = Object.keys(st.patch).length > 0
            const type = (st.patch.type as Type | undefined) ?? "any"
            const name = ((st.patch.name as string | undefined) ?? "").trim()
            return (
              <>
                <DialogHeader>
                  <DialogTitle className="flex min-w-0 items-center gap-2 pr-24 font-mono">
                    <Lead kind={kind} type={type} className="size-4" />
                    <Editable label="Name" {...st.field("name", "")} placeholder={`new ${kind}`} editing className="-mb-1 truncate pb-1 font-mono text-foreground" />
                  </DialogTitle>
                  <DialogDescription asChild><div><Editable label="Description" long placeholder="No description" {...st.field("desc", "")} /></div></DialogDescription>
                </DialogHeader>
                <dl className="grid grid-cols-[6rem_minmax(0,1fr)] items-baseline gap-x-3 gap-y-2 border-t pt-4 text-xs">
                  {kind !== "rule" && <><Term>Type</Term><dd><TypeChange type="any" own="any" editable kinds={kind === "signal" ? SCALARS : undefined} /></dd></>}
                  {kind === "variable" && <ItemChange own="any" editable />}
                  {kind === "variable" && <><Term>Starts as</Term><dd><Starts type={type} name={name || "variable"} was="" editable /></dd></>}
                  {kind === "signal" && <><Term>Expression</Term><dd><Formula expr="" /></dd><Term>Keep</Term><dd><SpanField label="Keep" name="backfill" was="" editable /></dd></>}
                  {kind === "rule" && <Fires rule={rule as Reference["rules"][number]} ruled={rule as unknown as RuleSpec} />}
                </dl>
                {kind === "variable" && <StagedFields name={name || "variable"} type="any" own="any" />}
              </>
            )
          }}
        </Staging>
      </DialogContent>
    </Dialog>
  )
}

/** The inputs: what's measured, the same everywhere. One that's on can be read by name; its
 * history (minutes) is kept as a table, for what reads its past. */
function Inputs({ inputs, veiled, veil }: { inputs: Reference["inputs"]; veiled: (name: string) => boolean; veil: (name: string) => void }) {
  const { specs, error, setError, change } = useSpecs<GlobalSpecs>(null)
  const used = Object.fromEntries((specs?.inputs ?? []).map((i) => [i.name, i]))
  if (!specs) return <p className="px-1 text-xs text-muted-foreground">{error || "Loading…"}</p>
  return (
    <div className="flex flex-col">
      {error && <ErrorDialog message={error} onClose={() => setError("")} />}
      {inputs.map((input) => (
        <InputLine key={input.name} {...input} spec={used[input.name]} veiled={veiled(input.name)} onVeil={() => veil(input.name)}
                   onBackfill={(backfill) => change([used[input.name] ? { op: "update", kind: "input", data: { name: input.name, changes: { backfill } } }
                                                                      : { op: "add", kind: "input", data: { name: input.name, backfill } }])} />
      ))}
    </div>
  )
}

/** An input, a line: its name, opening what it is, and its value now; one that's on goes into
 * the field you were in. */
function InputLine({ name, desc, type, value, spec, veiled, onVeil, onBackfill }: {
  name: string
  veiled: boolean
  onVeil: () => void
  desc: string
  type?: Type
  value: unknown
  spec?: { backfill: number | string | null }  // none: no automation reads it yet
  onBackfill: (backfill: number | string | null) => Promise<string | null>
}) {
  const [open, setOpen] = useState(false)
  return (
    <PanelLine icon={<TypeIcon type={type} />} label={name} name={name} desc={desc} type={type} dim={!spec || veiled} onOpen={() => setOpen(true)}>
      <Value value={value} name={name} />
      <Veil name={name} veiled={veiled} onClick={onVeil} />
      {open && (
        <Seen kind="input" name={name} full={name} desc={desc} type={type} value={value} settable={false}
              locked="the app measures it" history={spec?.backfill == null ? "" : String(spec.backfill)}
              onHistory={(t) => onBackfill(parseSpan(t))} onClose={() => setOpen(false)} />
      )}
    </PanelLine>
  )
}

/** What an expression can say: its syntax, what it can call, and what an action does; found by
 * what's typed. */
export const SYNTAX: [string, string][] = [
  ["a + b, a // b, a % b", "arithmetic; // divides and rounds down"],
  ["a if c else b", "a when c is true, else b"],
  ["a and b, a or b, not a", "yes or no"],
  ["x in (1, 2)", "whether x is one of them"],
  ["xs[0], xs[-1]", "an item of a list; -1 is the last"],
  ["xs[1:], xs[:3]", "a part of a list; set queue to queue[1:] pops the first"],
  ["record.field", "a field of a record"],
  ["xs.field", "a field of every item: a column"],
  ["work.tasks[i].status", "set's or add's name: a field of a record, set on its table"],
]

/** The names a field suggests: the global ones, then the scope's own. */
function Names({ reference, own }: { reference: Reference; own: string[] }) {
  const global = [
    ...reference.inputs.filter((i) => i.used).map((i) => i.name),
    ...reference.signals.filter((s) => s.scope === "global").map((s) => s.name),
    ...reference.variables.filter((v) => v.scope === "global" || v.scope === "special")
                          .flatMap((v) => [v.name, ...((v as ObjectRow).fields ?? []).map((f) => f.name)]),
    ...reference.rules.filter((r) => r.scope === "global").map((r) => r.name),
  ]
  return <datalist id={NAMES}>{[...new Set([...own, ...global])].map((n) => <option key={n} value={n} />)}</datalist>
}

// --- what the scopes share ------------------------------------------------------------------

/** A chance's colour: red through yellow to green as it grows. */
const heat = (c: number | null | undefined) => c == null ? "var(--muted-foreground)" : `oklch(0.82 0.17 ${25 + 120 * Math.min(1, Math.max(0, c))})`

/** A rule's chance as a ring filled to it, in its colour (the percent on hover). */
function Ring({ chance: c }: { chance: number | null }) {
  const colour = heat(c)
  const ring   = "radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 2px))"
  return (
    <span title={c == null ? "–" : `${Math.round(c * 100)}%`} className="relative size-4 shrink-0" style={{ color: colour }}>
      <span aria-hidden className="absolute inset-0 rounded-full"
            style={{ background: `conic-gradient(${colour} ${(c ?? 0) * 100}%, color-mix(in oklab, var(--muted-foreground) 30%, transparent) 0)`, mask: ring, WebkitMask: ring }} />
    </span>
  )
}

/** What leads a resource's name: its type's icon, a rule's gauge. */
function Lead({ kind, type, className }: { kind: Kind | "input"; type?: Type; className?: string }) {
  return kind === "rule" ? <CircleGauge aria-hidden className={cn("size-3.5 shrink-0 text-rose-300", className)} /> : <TypeIcon type={type} className={className} />
}

const chance = (c: number | null | undefined) => (c == null ? "–" : `${Math.round(c * 100)}%`)

/** A value beside its name, short enough to line up: yes or no as a mark, a big number in K, M
 * or B, a text whole; a list or a record, what it holds, opened as a table. */
export function Value({ value, rule, name, full, onPut, string, type, record, opens }: {
  value: unknown; rule?: boolean; name?: string; full?: boolean; onPut?: (value: unknown) => Promise<string | null>; string?: boolean; type?: Type; record?: string
  opens?: (key: string, value: unknown, type?: Type) => ReactNode  // an object whose fields are values of their own: how each opens
}) {
  const [open, setOpen] = useState(false)
  const yours = useSetter(record, open && !onPut && !rule, value)  // from the panel: kept to you if you can
  const all = rule ? chance(value as number | null) : shown(value)
  const held = collection(value) ? value : emptyOf(type)  // a list or a record, even empty or not given yet, opens as its table
  if (!rule && held !== undefined) return (
    <span className="flex w-20 shrink-0 justify-end font-mono">
      <Opens value={held} onOpen={() => setOpen(true)} />
      <Inspect title={name ?? "value"} type={type} value={held} open={open} onOpenChange={setOpen} edit={onPut ?? yours} record={record} opens={opens} />
    </span>
  )
  if (full && onPut && !rule) return <Scalar value={value} string={string} onPut={onPut} />
  if (rule && !full) return <Ring chance={value as number | null} />
  return (
    <span title={all} className={cn("flex min-w-12 justify-end font-mono tabular-nums", full ? "min-w-0 text-left break-all" : "max-w-[55%] shrink-0 text-right break-all")}>
      {typeof value === "boolean" && !rule ? <Truth value={value} />
        : rule ? <span style={{ color: heat(value as number | null) }}>{all}</span> : <Expr>{full ? all : brief(value)}</Expr>}
    </span>
  )
}

function brief(value: unknown): string {
  if (typeof value === "number") {
    const [size, unit] = [[1e9, "B"], [1e6, "M"], [1e3, "K"]].find(([size]) => Math.abs(value) >= (size as number)) ?? [1, ""]
    return unit ? `${Math.trunc(value / (size as number))}${unit}` : shown(value)
  }
  if (typeof value === "string") return `"${value.length > 10 ? `${value.slice(0, 9)}…` : value}"`  // short, quoted
  if (Array.isArray(value)) return "[]"
  return shown(value)
}

/** What a name shows on hover: its type, and what it is. */
export function hover({ desc, type }: { desc?: string; type?: Type }): string | undefined {
  return [type && type !== "any" ? said(type) : "", desc].filter(Boolean).join(" · ") || undefined
}
