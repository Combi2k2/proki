// Settings: Proki's two reasoning services and the local connections used at startup.
//
// A service is set by its provider: pick one, give its key (and a custom one's URL) and try
// it, pick one of the models there, then save. The key is kept on this computer, readable by you only,
// and never shown again; the service is asked from the moment it's saved. A change not saved yet
// says so where it was made, and on its service's tab.

import { useEffect, useState, type ReactNode } from "react"
import { Check, RefreshCw, Server, Sparkles } from "lucide-react"
import { PageHeader } from "@/components/page"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Ports, Service, Services } from "@/lib/proki"
import { cn } from "@/lib/utils"
import anthropic from "@/assets/providers/anthropic.svg?raw"
import google from "@/assets/providers/google.svg?raw"
import openai from "@/assets/providers/openai.svg?raw"
import openrouter from "@/assets/providers/openrouter.svg?raw"
import nebius from "@/assets/providers/nebius.svg?raw"
import nvidia from "@/assets/providers/nvidia.svg?raw"

const SERVICES: Record<Service, { title: string; about: string }> = {
  llm: { title: "LLM", about: "Helps me turn your plans into useful next steps." },
  jev: { title: "Jev", about: "Helps me make sense of your tasks and apps." },
}
const LOGOS: Record<string, string> = { openai, anthropic, google, openrouter, nebius, nvidia }
const PROVIDER_ORDER: Record<Service, string[]> = {
  llm: ["openai", "anthropic", "google", "nvidia", "openrouter", "nebius", "custom"],
  jev: ["openjev", "openrouter", "custom"],
}

type Result = { ok: boolean; text: string } | null

const failed = (error: unknown) => error instanceof Error ? error.message : "Could not reach Proki."

export function SettingsView({ onWelcome }: {
  onWelcome: () => void  // the welcome shown again
}) {
  const [services, setServices]   = useState<Services | null>(null)
  const [loadError, setLoadError] = useState("")
  const [service, setService]     = useState<Service>("llm")
  const [unsaved, setUnsaved]     = useState<Record<Service, boolean>>({ llm: false, jev: false })
  const [retry, setRetry]         = useState(0)

  useEffect(() => {
    let active = true
    setLoadError("")
    const timeout = setTimeout(() => {
      active = false
      setLoadError("Proki is taking too long to load your connections. Try again in a moment.")
    }, 20_000)
    window.proki.tool("get_settings")
      .then((answer) => {
        if (!active) return
        if (answer.error) setLoadError(answer.error)
        else setServices(answer)
      })
      .catch((error: unknown) => { if (active) setLoadError(failed(error)) })
      .finally(() => clearTimeout(timeout))
    return () => { active = false; clearTimeout(timeout) }
  }, [retry])

  return (
    <div className="mx-auto max-w-2xl px-8 pt-7 pb-24">
      <PageHeader title="Settings" sub="A few things to help me help you." className="mb-6" />

      <section aria-labelledby="welcome" className="mb-10 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-5 py-3.5">
        <div>
          <h2 id="welcome" className="text-sm font-semibold">Welcome</h2>
          <p className="text-xs text-muted-foreground">Tracking, browser tabs, and a little brain upgrade.</p>
        </div>
        <Button size="sm" variant="outline" onClick={onWelcome}>Show the welcome</Button>
      </section>

      <h2 className="text-sm font-semibold">Services</h2>
      <p className="mt-0.5 mb-4 text-sm text-muted-foreground">My thinking buddies. Pick a provider for each, add your key, and choose a model. Keys are saved on this computer.</p>
      {loadError ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-destructive">
          <span>{loadError}</span>
          <Button size="sm" variant="outline" onClick={() => setRetry((was) => was + 1)}>Try again</Button>
        </div>
      ) : !services ? (
        <p role="status" className="text-sm text-muted-foreground">Loading your saved connections…</p>
      ) : (
        <>
        <Tabs value={service} onValueChange={(value) => setService(value as Service)}>
          <TabsList className="mb-3">
            {(Object.keys(SERVICES) as Service[]).map((s) => (
              <TabsTrigger key={s} value={s} className="px-3">
                {SERVICES[s].title}
                {unsaved[s] && <span className="size-1.5 rounded-full bg-primary" aria-label="not saved yet" />}
              </TabsTrigger>
            ))}
          </TabsList>
          {(Object.keys(SERVICES) as Service[]).map((s) => (
            <TabsContent key={s} value={s} forceMount className="data-[state=inactive]:hidden">
              <ServiceSetup service={s} services={services} onSaved={setServices}
                            onUnsaved={(on) => setUnsaved((was) => was[s] === on ? was : { ...was, [s]: on })} />
            </TabsContent>
          ))}
        </Tabs>
        <PortSetup services={services} onSaved={setServices} />
        </>
      )}
    </div>
  )
}

/** A provider's logo, or an icon for one without. */
function Logo({ id }: { id: string }) {
  if (LOGOS[id]) return <span aria-hidden className="size-4 shrink-0 [&>svg]:size-full" dangerouslySetInnerHTML={{ __html: LOGOS[id] }} />
  const Icon = id === "custom" ? Server : Sparkles
  return <Icon aria-hidden className={cn("size-4 shrink-0", id === "custom" ? "text-muted-foreground" : "text-brand")} />
}

const PORT_LABELS: Record<keyof Ports, string> = { activitywatch: "ActivityWatch", nats: "Message bus", tools: "App tools" }

function PortSetup({ services, onSaved }: { services: Services; onSaved: (services: Services) => void }) {
  const [ports, setPorts] = useState(services.ports)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Result>(null)
  const names = Object.keys(PORT_LABELS) as (keyof Ports)[]
  const changed = names.some((name) => ports[name] !== services.ports[name])
  const restart = names.some((name) => services.ports[name] !== services.active_ports[name])
  const valid = names.every((name) => Number.isInteger(ports[name]) && ports[name] >= 1 && ports[name] <= 65535)
                && new Set(Object.values(ports)).size === names.length
  const save = async () => {
    setBusy(true)
    try {
      const answer = await window.proki.tool("set_ports", ports)
      if (answer.error) setResult({ ok: false, text: answer.error })
      else {
        onSaved(answer)
        setResult({ ok: true, text: "Saved. Quit and reopen Proki to use these ports." })
      }
    } catch (error) {
      setResult({ ok: false, text: failed(error) })
    } finally {
      setBusy(false)
    }
  }
  return (
    <section aria-labelledby="local-ports" className="mt-8 border-t pt-5">
      <h2 id="local-ports" className="text-sm font-semibold">Local connections</h2>
      <p id="ports-help" className="mt-0.5 mb-3 text-xs text-muted-foreground">Only change these if a port is busy. Apply them by quitting and reopening Proki. If you run ActivityWatch separately, match its port here.</p>
      <form onSubmit={(event) => { event.preventDefault(); if (valid && changed) void save() }}>
        <div className="flex flex-wrap items-end gap-3">
          <FieldGroup className="grid min-w-0 flex-1 grid-cols-3 gap-3 max-[460px]:grid-cols-1">
            {names.map((name) => <Field key={name}>
              <FieldLabel htmlFor={`port-${name}`} className="text-xs">{PORT_LABELS[name]}</FieldLabel>
              <Input id={`port-${name}`} type="number" inputMode="numeric" min={1} max={65535} step={1}
                     aria-describedby="ports-help" aria-invalid={!valid} className="h-8 font-mono text-xs tabular-nums"
                     value={ports[name] || ""} onChange={(event) => {
                       setPorts((was) => ({ ...was, [name]: Number(event.target.value) }))
                       setResult(null)
                     }} />
            </Field>)}
          </FieldGroup>
          <Button type="submit" size="sm" variant="outline" disabled={busy || !valid || !changed}>
            {busy && <Spinner data-icon="inline-start" />}Save ports
          </Button>
        </div>
        <div className="mt-2 min-h-4 text-xs text-muted-foreground" role="status">
          {!valid ? "Choose different whole numbers from 1 to 65535." : result ? <Outcome result={result} />
            : restart ? "New ports saved. Restart Proki when you're ready." : "Changes stay on this computer."}
        </div>
      </form>
    </section>
  )
}

/** A service: its provider, its connection and its model, tried and saved. */
function ServiceSetup({ service, services, onSaved, onUnsaved }: {
  service: Service
  services: Services
  onSaved: (services: Services) => void
  onUnsaved: (on: boolean) => void
}) {
  const current   = services.services[service]
  const providers = services.providers[service]
  const order     = PROVIDER_ORDER[service].filter((id) => id in providers)
  const { title, about } = SERVICES[service]

  const [provider, setProvider] = useState(current?.provider ?? order[0])
  const [url, setUrl]           = useState(current?.provider === "custom" ? current.url : "")
  const [key, setKey]           = useState<string | undefined>(undefined)  // undefined: the one kept
  const [model, setModel]       = useState(current?.model ?? "")
  const [models, setModels]     = useState<string[] | null>(providers[provider]?.models ?? null)
  const [tested, setTested]     = useState<Result>(null)
  const [saved, setSaved]       = useState<Result>(null)
  const [busy, setBusy]         = useState<"test" | "models" | "save" | null>(null)

  const chosen = providers[provider]
  const custom = provider === "custom"
  const asked  = { service, provider, ...(custom ? { url } : {}), ...(key === undefined ? {} : { key }) }
  const same   = current?.provider === provider && current.model === model.trim() && key === undefined
                 && (!custom || current.url === url.trim().replace(/\/+$/, ""))
  const shown  = !models ? [] : models.includes(model) ? models : models.filter((m) => m.toLowerCase().includes(model.trim().toLowerCase()))
  const changed = !same && (current !== null || model.trim() !== "" || key !== undefined)
  useEffect(() => onUnsaved(changed), [changed, onUnsaved])

  const pick = (to: string) => {
    setProvider(to)
    setUrl(current?.provider === to && to === "custom" ? current.url : "")
    setKey(undefined)
    setModel(current?.provider === to ? current.model : "")
    setModels(providers[to].models ?? null)
    setTested(null)
    setSaved(null)
  }
  const edited = (then: () => void) => { then(); setTested(null); setSaved(null) }

  const run = async <T,>(step: "test" | "models" | "save", call: () => Promise<T & { error?: string }>, done: (answer: T) => void, shown: (result: Result) => void) => {
    setBusy(step)
    try {
      const answer = await call()
      if (answer.error) shown({ ok: false, text: answer.error })
      else done(answer)
    } catch (error) {
      shown({ ok: false, text: failed(error) })
    }
    setBusy(null)
  }
  const test = () => run("test", () => window.proki.tool("test_connection", { ...asked, ...(model.trim() ? { model: model.trim() } : {}) }),
                         (answer) => setTested({ ok: true, text: answer.models === undefined ? "Connected" : `Connected: ${answer.models} models` }), setTested)
  const list = () => run("models", () => window.proki.tool("list_models", asked), (answer) => setModels(answer.models), setTested)
  const save = () => run("save", () => window.proki.tool("set_settings", { ...asked, model: model.trim() }), (answer) => {
    onSaved(answer)
    setKey(undefined)
    setSaved({ ok: true, text: "Saved. Proki asks it from now on." })
  }, setSaved)

  return (
    <section className="rounded-xl border bg-card">
      <header className="flex items-start justify-between gap-3 border-b px-5 py-3">
        <p className="min-w-0 pt-0.5 text-xs text-muted-foreground">{about}</p>
        {current ? <Badge variant="secondary" className="max-w-72 justify-start text-[11px]" title={`In use: ${providers[current.provider]?.name ?? current.provider} · ${current.model}`}>
                     <Logo id={current.provider} /><span className="truncate font-mono">{current.model}</span>
                   </Badge>
                 : <Badge variant="outline" className="text-[11px]">Not set</Badge>}
      </header>

      <div className="flex flex-col gap-4 px-5 py-4">
        <Row label="Provider" htmlFor={`${service}.provider`}>
          <Select value={provider} onValueChange={pick}>
            <SelectTrigger id={`${service}.provider`} className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {order.map((id) => (
                <SelectItem key={id} value={id}><Logo id={id} /> {providers[id].name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Row>

        <Row label="API key" htmlFor={`${service}.key`} about={custom ? "Only if your service needs one." : undefined}>
          <div className="flex items-center gap-2">
            <Input id={`${service}.key`} type="password" autoComplete="off" spellCheck={false} className="h-8 flex-1 font-mono text-xs"
                   placeholder={chosen.key ? "•••••••• kept: type to replace" : custom ? "none, for a service on this computer" : "paste your key"}
                   value={key ?? ""} onChange={(e) => edited(() => setKey(e.target.value))} />
            {chosen.key && key === undefined && <Button variant="ghost" size="sm" className="h-8 text-xs text-muted-foreground" onClick={() => edited(() => setKey(""))}>Remove</Button>}
            {chosen.key && key === "" && <Badge variant="outline" className="text-[11px]">removed on save</Badge>}
          </div>
        </Row>

        <Row label="Base URL" htmlFor={`${service}.url`}>
          <Input id={`${service}.url`} readOnly={!custom} spellCheck={false} placeholder="http://localhost:11434/v1"
                 className={cn("h-8 font-mono text-xs", !custom && "border-dashed text-muted-foreground")}
                 value={custom ? url : chosen.url} onChange={(e) => edited(() => setUrl(e.target.value))} />
        </Row>

        <Row label="Model" htmlFor={`${service}.model`} about={chosen.models ? undefined : "Fetch the models there, then search for one, or type its ID."}>
          <div className="flex items-center gap-2">
            <Input id={`${service}.model`} spellCheck={false} className="h-8 flex-1 font-mono text-xs"
                   placeholder={models ? "search, or type a model ID" : "a model ID"} value={model} onChange={(e) => edited(() => setModel(e.target.value))} />
            {!chosen.models && (
              <Button variant="outline" size="sm" disabled={busy !== null || (custom && !url.trim())} onClick={list}>
                {busy === "models" ? <Spinner data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />} Fetch models
              </Button>
            )}
          </div>
          {models && (
            <div className="mt-2 max-h-48 overflow-y-auto rounded-md border" role="listbox" aria-label={`${title} models`}>
              {shown.length ? shown.map((m) => (
                <button key={m} type="button" role="option" aria-selected={m === model} onClick={() => edited(() => setModel(m))}
                        className={cn("flex w-full items-center justify-between px-3 py-1.5 text-left font-mono text-xs hover:bg-accent", m === model && "bg-accent")}>
                  <span className="truncate">{m}</span>{m === model && <Check className="size-3.5 shrink-0" />}
                </button>
              )) : <p className="px-3 py-2 text-xs text-muted-foreground">None match: saved as you typed it.</p>}
            </div>
          )}
          {models && models.length > 0 && <p className="mt-1 text-[11px] text-muted-foreground tabular-nums">{shown.length} of {models.length}</p>}
        </Row>
      </div>

      <footer className="flex flex-wrap items-center gap-3 border-t px-5 py-3">
        <Button variant="outline" size="sm" disabled={busy !== null || (custom && !url.trim())} onClick={test}>
          {busy === "test" ? <Spinner data-icon="inline-start" /> : null} Test connection
        </Button>
        <Outcome result={tested} />
        <span className="ml-auto flex items-center gap-3">
          {saved ? <Outcome result={saved} /> : changed && <span role="status" className="text-xs text-muted-foreground">Unsaved changes</span>}
          <Button size="sm" disabled={busy !== null || same || !model.trim() || (custom && !url.trim())} onClick={save}>
            {busy === "save" ? <Spinner data-icon="inline-start" /> : null} Save and use
          </Button>
        </span>
      </footer>
    </section>
  )
}

/** A field of a service's setup: its label (and what to know about it) beside its control. */
function Row({ label, htmlFor, about, children }: { label: string; htmlFor: string; about?: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] items-start gap-x-4 max-[560px]:grid-cols-1 max-[560px]:gap-y-1.5">
      <label htmlFor={htmlFor} className="pt-2 text-xs font-medium">{label}</label>
      <div className="min-w-0">
        {children}
        {about && <p className="mt-1 text-[11px] text-muted-foreground">{about}</p>}
      </div>
    </div>
  )
}

/** How a step went: done, or why not. */
function Outcome({ result }: { result: Result }) {
  if (!result) return null
  return (
    <span role="status" className={cn("text-xs", result.ok ? "text-muted-foreground" : "text-destructive")}>
      {result.ok && <Check className="mr-1 inline size-3.5" />}{result.text}
    </span>
  )
}
