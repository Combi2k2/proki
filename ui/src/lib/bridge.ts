// `window.proki`: what the pages may call, each one of the app's commands.

import { convertFileSrc, invoke } from "@tauri-apps/api/core"
import { listen } from "@tauri-apps/api/event"
import { getCurrentWebview } from "@tauri-apps/api/webview"
import { open } from "@tauri-apps/plugin-dialog"

const engine = (name: string) => (request: object = {}) => invoke<never>("engine", { name, request })

if ("__TAURI_INTERNALS__" in window) {
  window.proki = {
    // the popup
    onShow: (callback) => {
      listen("show", (event) => callback(event.payload as never)).then(() => invoke("popup_ready"))
    },
    answer: (id, answer) => void invoke("answer", { id, answer }),
    resize: (height) => void invoke("resize", { height }),
    // the windows: the engine's tables (proki/serve.py)
    tasks: engine("tasks"),
    notes: engine("notes"),
    fields: engine("fields"),
    apps: engine("apps"),
    today: engine("today"),
    metrics: engine("metrics"),
    // your programs: a tool by its name (proki/tools/), {error} for a mistake
    tool: (name, args = {}) => invoke("tool", { name, args }),
    // files: picked with the system's picker, or dropped on the window, as paths
    pickFiles: async (extensions) => {
      const picked = await open({ multiple: true, filters: [{ name: "Media", extensions }] })
      return picked ?? []
    },
    pickFolder: () => open({ directory: true }),
    onDrop: (callback) => getCurrentWebview().onDragDropEvent(({ payload }) => {
      if (payload.type === "drop") callback("drop", payload.paths)
      else callback(payload.type === "leave" ? "leave" : "over", [])
    }),
    fileUrl: (path) => convertFileSrc(path),
    note: () => void invoke("note"),
    link: (to) => void invoke("link", { to }),
    session: (op) => void invoke("session", { op }),
    // the main window: the page the tray or the engine asked for, by its path ("tasks/12")
    onNavigate: (callback) => {
      listen<string>("navigate", ({ payload }) => callback(payload))
    },
  }
}
