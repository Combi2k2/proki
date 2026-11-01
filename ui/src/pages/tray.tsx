import { useEffect, useState } from "react"
import { createRoot } from "react-dom/client"
import { Pause, Play, X } from "lucide-react"
import prokiMark from "../../logo/proki.png"
import { INITIAL, tray, type TrayState, type TrayStatus } from "@/lib/tray"
import "./tray.css"

// On macOS the background is the native menu material supplied by the window.
if ("__TAURI_INTERNALS__" in window && navigator.userAgent.includes("Mac")) {
  document.documentElement.dataset.nativeMenu = "true"
}

function Focus({ status }: { status: TrayStatus }) {
  const score = status.available && !status.paused && status.focus !== null && Number.isFinite(status.focus)
    ? Math.round(Math.max(0, Math.min(1, status.focus)) * 100) : null
  const lines = status.focus_lines
  const band = score === null || !lines?.length ? "unknown" : score / 100 < lines[0] ? "low" : score / 100 < lines.at(-1)! ? "mid" : "high"
  const detail = status.paused ? "Tracking paused" : !status.available ? "Waiting for activity" : score === null ? "No recent activity" : "Focus score"
  return (
    <figure className="focus" data-band={band} aria-label={`Focus: ${score === null ? detail : `${score} out of 100`}`}>
      <div className="focus-dial">
        <svg viewBox="0 0 120 120" aria-hidden="true">
          <circle className="focus-track" cx="60" cy="60" r="52" />
          <circle className="focus-value" cx="60" cy="60" r="52" pathLength="100"
            strokeDasharray={`${score ?? 0} 100`} visibility={score ? "visible" : "hidden"} />
        </svg>
        <span className="focus-number" aria-hidden="true">{score ?? "—"}</span>
      </div>
      <figcaption>Focus{score === null && <span>{detail}</span>}</figcaption>
    </figure>
  )
}

function Tray() {
  const [state, setState] = useState<TrayState>({ status: INITIAL, autostart: null, startup_error: null })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const refresh = async () => setState(await tray.state())
  useEffect(() => {  // the state as the panel opens, then each status the engine sends
    let active = true
    const failed = (reason: unknown) => { if (active) setError(String(reason)) }
    const update = () => void tray.state().then((value) => active && setState(value)).catch(failed)
    const listening = tray.subscribe((status) => active && setState((value) => ({ ...value, status })))
      .catch((reason) => (failed(reason), () => {}))
    const escape = (event: KeyboardEvent) => event.key === "Escape" && void tray.action("close").catch(failed)  // no such action: only hidden
    update()
    window.addEventListener("focus", update)
    window.addEventListener("keydown", escape)
    return () => {
      active = false
      void listening.then((stop) => stop())
      window.removeEventListener("focus", update)
      window.removeEventListener("keydown", escape)
    }
  }, [])
  const run = async (action: () => Promise<unknown>) => {
    if (busy) return
    setBusy(true)
    setError("")
    try { await action(); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)) }
    finally { setBusy(false) }
  }
  const act = (action: string) => void run(() => tray.action(action))
  const { status } = state
  const recording = status.paused === false && status.available
  const recordingLabel = status.paused ? "Resume Proki tracking" : "Pause Proki tracking"
  return (
    <main className="tray-panel" aria-label="Proki menu" aria-busy={busy}>
      <header className="tray-header">
        <img className="brand-mark" src={prokiMark} alt="" />
        <div className="brand-name">Proki</div>
        <span className="tracking-status" title={status.text}>
          {status.paused ? "Paused" : recording ? "Recording" : status.paused === null ? "Connecting…" : "Waiting for activity"}
        </span>
        <button className="recording" data-recording={recording} data-paused={Boolean(status.paused)}
          aria-label={status.paused === null ? "Connecting to Proki" : recordingLabel} aria-pressed={status.paused === false}
          title={`${recordingLabel}. ActivityWatch continues recording independently.`}
          disabled={busy || status.paused === null} onClick={() => void run(() => tray.tracking(!status.paused))}>
          {status.paused ? <Play size={12} fill="currentColor" /> : recording ? <span /> : <Pause size={12} />}
        </button>
      </header>
      <div className="tray-body">
        <nav className="tray-actions" aria-label="Quick actions">
          <button disabled={busy} onClick={() => act("view:today")}>Open Proki</button>
          <hr />
          <button disabled={busy || status.paused !== false} onClick={() => act(status.session ? "session:stop" : "session:start")}>
            {status.session ? "End session" : "New session"}
            {status.session && <span className="session-time">{status.session}</span>}
          </button>
          <button disabled={busy} onClick={() => act("note")}>New note</button>
          <hr />
          <button disabled={busy} onClick={() => act("view:settings")}>Settings…</button>
        </nav>
        <Focus status={status} />
      </div>
      <div className="startup">
        <button role="switch" aria-checked={state.autostart === true}
          title="Start Proki automatically when you log in" disabled={busy}
          onClick={() => void run(() => tray.autostart(!state.autostart))}>
          Launch at login<span className="startup-switch" aria-hidden="true"><span /></span>
        </button>
      </div>
      <footer className="tray-footer">
        <button disabled={busy} onClick={() => act("quit")}>Quit Proki</button>
      </footer>
      {(error || state.startup_error) && <div className="tray-error" role="alert">
        <span>{error || state.startup_error}</span>
        <button aria-label="Dismiss error" onClick={() => { setError(""); setState(value => ({ ...value, startup_error: null })) }}><X size={14} /></button>
      </div>}
    </main>
  )
}

createRoot(document.getElementById("root")!).render(<Tray />)
