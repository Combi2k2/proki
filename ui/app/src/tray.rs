// The tray's panel, on a left click on its icon (the menu is still there on a right one): the
// focus now, the session, pausing Proki, and starting it at login. It hides as it loses the focus.

use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::{AppHandle, LogicalPosition, Manager, PhysicalPosition, Rect, WebviewUrl, WebviewWindowBuilder, WindowEvent};
use tauri_plugin_autostart::ManagerExt;

use crate::{bus, launcher, on_menu, proki};

const WIDTH: f64 = 280.0;
const HEIGHT: f64 = 230.0;
const MARGIN: f64 = 12.0;  // the least room left between the panel and the screen's right edge

static HIDDEN: Mutex<Option<Instant>> = Mutex::new(None); // when the panel last hid as it lost focus
static TOUCHED: Mutex<Option<Instant>> = Mutex::new(None); // when the panel last gained or lost focus, or was shown

/// The panel or the popup just came or went: the app being activated then is theirs, not the Dock icon's.
pub fn touch() {
    *TOUCHED.lock().unwrap() = Some(Instant::now());
}

/// Whether the panel or the popup was in use within `span`.
pub fn used_within(span: Duration) -> bool {
    TOUCHED.lock().unwrap().is_some_and(|at| at.elapsed() < span)
}

#[derive(Clone, Serialize, Deserialize)]
pub struct State {
    pub text: String,
    pub session: String,
    pub focus: Option<f64>,
    pub focus_lines: Option<Vec<f64>>, // the engine's, none until it says
    pub paused: Option<bool>,
    pub available: bool,
}

impl Default for State {
    fn default() -> Self {
        Self { text: "Connecting to Proki…".into(), session: String::new(), focus: None,
            focus_lines: None, paused: None, available: false }
    }
}

pub fn make(app: &AppHandle) -> tauri::Result<()> {
    let panel = WebviewWindowBuilder::new(app, "tray", WebviewUrl::App("tray.html".into()))
        .title("Proki menu")
        .inner_size(WIDTH, HEIGHT)
        .visible(false).focused(false).decorations(false).transparent(true)
        .shadow(true).resizable(false).maximizable(false).always_on_top(true)
        .skip_taskbar(true).visible_on_all_workspaces(true).accept_first_mouse(true);
    #[cfg(target_os = "macos")]
    let panel = panel.effects(tauri::window::EffectsBuilder::new()
        .effect(tauri::window::Effect::Menu)
        .state(tauri::window::EffectState::Active)
        .radius(8.0).build());
    let panel = panel.build()?;
    let window = panel.clone();
    panel.on_window_event(move |event| {
        if let WindowEvent::Focused(_) = event {
            *TOUCHED.lock().unwrap() = Some(Instant::now());
        }
        if matches!(event, WindowEvent::Focused(false)) {
            let _ = window.hide();
            *HIDDEN.lock().unwrap() = Some(Instant::now());
        }
    });
    Ok(())
}

pub fn hide(app: &AppHandle) {
    if let Some(panel) = app.get_webview_window("tray") { let _ = panel.hide(); }
}

pub fn toggle(app: &AppHandle, rect: Rect, position: PhysicalPosition<f64>) {
    let Some(panel) = app.get_webview_window("tray") else { return };
    // A click on the icon takes the focus from the open panel first, which hides it: that click closes it.
    let closed = HIDDEN.lock().unwrap().take().is_some_and(|at| at.elapsed() < Duration::from_millis(300));
    if closed || panel.is_visible().unwrap_or(false) { hide(app); return; }
    // On macOS the icon's rect is in pixels at its own screen's scale while screens are laid out in
    // points: find the screen by the cursor in points, so a monitor plugged in or out never sends the
    // panel astray. Elsewhere it's all pixels.
    let primary = app.primary_monitor().ok().flatten();
    #[cfg(target_os = "macos")]
    let found = {
        let cursor = app.cursor_position().unwrap_or(position).to_logical::<f64>(primary.as_ref().map_or(1.0, |m| m.scale_factor()));
        app.available_monitors().unwrap_or_default().into_iter().find(|m| {
            let s = m.scale_factor();
            let (at, size) = (m.position().to_logical::<f64>(s), m.size().to_logical::<f64>(s));
            (at.x..at.x + size.width).contains(&cursor.x) && (at.y..at.y + size.height).contains(&cursor.y)
        })
    };
    #[cfg(not(target_os = "macos"))]
    let found = app.monitor_from_point(position.x, position.y).ok().flatten();
    if let Some(monitor) = found.or(primary) {
        let scale  = monitor.scale_factor();
        let anchor = rect.position.to_logical::<f64>(scale);
        let icon   = rect.size.to_logical::<f64>(scale);
        let area   = monitor.work_area();
        let (left, top)     = (area.position.x as f64 / scale, area.position.y as f64 / scale);
        let (right, bottom) = (left + area.size.width as f64 / scale, top + area.size.height as f64 / scale);
        let room  = anchor.x + WIDTH + MARGIN <= right;                       // its left edge on the icon's, else its right edge on the icon's
        let x     = (if room { anchor.x } else { anchor.x + icon.width - WIDTH }).clamp(left, (right - WIDTH).max(left));
        let below = anchor.y + icon.height;
        let y     = if below + HEIGHT <= bottom { below } else { anchor.y - HEIGHT };  // under the icon, else over it
        let at    = LogicalPosition::new(x, y.clamp(top, (bottom - HEIGHT).max(top)));
        #[cfg(target_os = "macos")]
        let _ = panel.set_position(at);
        #[cfg(not(target_os = "macos"))]
        let _ = panel.set_position(at.to_physical::<f64>(scale));
    }
    *TOUCHED.lock().unwrap() = Some(Instant::now());
    let _ = panel.show();
    let _ = panel.set_focus();
}

#[tauri::command]
pub fn tray_state(app: AppHandle) -> Value {
    let state = proki(&app).tray.lock().unwrap().clone();
    let startup = app.autolaunch().is_enabled();
    json!({ "status": state, "autostart": startup.as_ref().ok(),
        "startup_error": startup.err().map(|e| e.to_string()) })
}

#[tauri::command]
pub async fn tray_tracking(app: AppHandle, paused: bool) -> Result<(), String> {
    let result = bus::ask(&app, "proki.app.tracking", json!({ "paused": paused })).await;
    if let Some(error) = result["error"].as_str() { return Err(error.into()); }
    let Some(paused) = result["paused"].as_bool() else { return Err("Tracking did not confirm the change".into()); };
    proki(&app).tray.lock().unwrap().paused = Some(paused);
    crate::update_tray(&app);
    Ok(())
}

#[tauri::command]
pub fn tray_autostart(app: AppHandle, enabled: bool) -> Result<(), String> {
    if enabled && launcher(&app).is_none() {
        return Err("Proki's launcher could not be found. Restore the repository's .venv and launch.py, or install the packaged app, then try again.".into());
    }
    let startup = app.autolaunch();
    (if enabled { startup.enable() } else { startup.disable() }).map_err(|e| e.to_string())
}

/// One of the tray menu's actions ("view:today", "note", "session:start", "quit", ...), the panel hidden first.
#[tauri::command]
pub fn tray_action(app: AppHandle, action: String) {
    hide(&app);
    on_menu(&app, &action);
}
