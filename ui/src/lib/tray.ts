import { invoke } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"

export type TrayStatus = {
  text: string
  session: string
  focus: number | null
  focus_lines: number[] | null
  paused: boolean | null
  available: boolean
}
export type TrayState = {
  status: TrayStatus
  autostart: boolean | null
  startup_error: string | null
}

export const INITIAL: TrayStatus = {
  text: "Connecting to Proki…", session: "", focus: null,
  focus_lines: null, paused: null, available: false,
}

// Browser previews follow the same development-only convention as the other pages.
const preview = import.meta.env.DEV && !("__TAURI_INTERNALS__" in window)
const params = new URLSearchParams(location.search)
let sample: TrayState = {
  status: { ...INITIAL, text: "Recording activity", paused: false, available: true, focus: 0.78, focus_lines: [0.35, 0.5] },
  autostart: false, startup_error: null,
}
if (preview) {
  if (params.has("score")) sample.status.focus = Number(params.get("score")) / 100
  if (params.has("paused")) sample.status.paused = true
  if (params.has("empty")) sample.status.focus = null
  if (params.has("loading")) sample.status = INITIAL
  if (params.has("session")) sample.status.session = "12m"
}

export const tray = {
  state: (): Promise<TrayState> => preview ? Promise.resolve(sample) : invoke("tray_state"),
  subscribe: (callback: (status: TrayStatus) => void) => preview
    ? Promise.resolve(() => {}) : listen<TrayStatus>("tray-status", ({ payload }) => callback(payload)),
  tracking: async (paused: boolean) => {
    if (!preview) return invoke<void>("tray_tracking", { paused })
    if (params.has("error")) throw new Error("Couldn’t reach Proki. Please try again.")
    sample = { ...sample, status: { ...sample.status, paused } }
  },
  autostart: async (enabled: boolean) => {
    if (!preview) return invoke<void>("tray_autostart", { enabled })
    sample = { ...sample, autostart: enabled }
  },
  action: async (action: string) => {
    if (!preview) return invoke<void>("tray_action", { action })
    if (action.startsWith("view:")) location.href = `main.html#${action.slice(5)}`
    if (action.startsWith("session:")) sample = { ...sample, status: { ...sample.status, session: action.endsWith("start") ? "0m" : "" } }
  },
}
