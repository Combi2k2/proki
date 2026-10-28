// proki's UI: the tray, the popup and the windows. The launcher (launch.py) starts it, or you do.
// It talks to the engine only over the message bus (bus.rs: --nats=host:port), and to the programs'
// tools over MCP (tools.rs: --tools=host:port, --tools-token=path), each where the engine is unless
// it's told. The pages are the same React pages (src/pages/), built into dist/; they reach this
// process through `window.proki` (src/lib/bridge.ts), each call one of the commands here.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bus;
mod popup;
mod tools;

use std::sync::Mutex;
use std::time::Duration;

use serde_json::{json, Value};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

pub struct Args {
    pub nats: String,
    pub tools: String,
    pub tools_token: String,
}

/// Where the engine keeps the tools' token: its config folder, as the engine finds it on each OS.
fn token() -> String {
    let var = |name: &str| std::env::var(name).unwrap_or_default();
    let dir = if cfg!(target_os = "windows")                { format!("{}\\proki\\proki", var("LOCALAPPDATA")) }
              else if cfg!(target_os = "macos")             { format!("{}/Library/Application Support/proki", var("HOME")) }
              else if !var("XDG_CONFIG_HOME").is_empty()    { format!("{}/proki", var("XDG_CONFIG_HOME")) }
              else                                          { format!("{}/.config/proki", var("HOME")) };
    format!("{dir}{}tools-token", std::path::MAIN_SEPARATOR)
}

fn option(name: &str, fallback: &str) -> String {
    let prefix = format!("--{name}=");
    std::env::args().find_map(|a| a.strip_prefix(&prefix).map(String::from)).unwrap_or_else(|| fallback.into())
}

/// What the app keeps: where the engine is, the popup's line, the tray's text.
pub struct Proki {
    pub args: Args,
    pub bus: tokio::sync::OnceCell<async_nats::Client>,
    pub queue: Mutex<popup::Queue>,
    pub tray: Mutex<(String, String)>, // the tray's first line, and the running session next to its icon
    pub tools: tools::Tools,
}

pub fn proki(app: &AppHandle) -> &Proki {
    app.state::<Proki>().inner()
}

// --- the commands: what the pages may call, and nothing else (src/lib/bridge.ts) -------------

const ENGINE: [&str; 6] = ["tasks", "notes", "fields", "apps", "today", "metrics"]; // proki.app.* (proki/serve.py)

#[tauri::command]
async fn engine(app: AppHandle, name: String, request: Value) -> Value {
    if !ENGINE.contains(&name.as_str()) {
        return json!({ "error": format!("no {name:?}") });
    }
    bus::ask(&app, &format!("proki.app.{name}"), request).await
}

#[tauri::command]
async fn tool(app: AppHandle, name: String, args: Value) -> Value {
    proki(&app).tools.call(&name, args).await
}

#[tauri::command]
async fn session(app: AppHandle, op: String) {
    bus::ask(&app, "proki.app.session", json!({ "op": op })).await;
}

#[tauri::command]
fn note(app: AppHandle) {
    popup::new_note(&app);
}

const LINKS: [(&str, &str); 1] = [("github", "https://github.com/Combi2k2/proki")]; // the pages a page may open, by name

#[tauri::command]
fn link(to: String) {
    let Some((_, url)) = LINKS.iter().find(|(name, _)| *name == to) else { return };
    #[cfg(target_os = "macos")]
    let opened = std::process::Command::new("open").arg(url).spawn();
    #[cfg(target_os = "windows")]
    let opened = std::process::Command::new("cmd").args(["/C", "start", "", url]).spawn();
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    let opened = std::process::Command::new("xdg-open").arg(url).spawn();
    if let Err(e) = opened {
        eprintln!("couldn't open {url}: {e}");
    }
}

// --- the tray and the windows -----------------------------------------------------------------

const VIEWS: [&str; 7] = ["today", "tasks", "notes", "apps", "metrics", "programs", "media"];

pub fn update_tray(app: &AppHandle) {
    let Some(tray) = app.tray_by_id("proki") else { return };
    let (status, session) = proki(app).tray.lock().unwrap().clone();
    let menu = || -> tauri::Result<Menu<tauri::Wry>> {
        let item = |id: &str, label: &str| MenuItem::with_id(app, id, label, true, None::<&str>);
        let separator = || PredefinedMenuItem::separator(app);
        let menu = Menu::new(app)?;
        menu.append(&MenuItem::with_id(app, "status", &status, false, None::<&str>)?)?;
        menu.append(&separator()?)?;
        menu.append(&item("view:today", "Open proki")?)?;
        menu.append(&item("note", "New note…")?)?;
        if session.is_empty() {
            menu.append(&item("session:start", "Start focus session")?)?;
        } else {
            menu.append(&item("session:stop", &format!("Stop focus session ({session})"))?)?;
        }
        menu.append(&separator()?)?;
        for (view, label) in [("tasks", "Tasks"), ("notes", "Notes"), ("apps", "Apps"), ("metrics", "Metrics"),
                              ("programs", "Programs"), ("media", "Media")] {
            menu.append(&item(&format!("view:{view}"), label)?)?;
        }
        menu.append(&separator()?)?;
        menu.append(&item("quit", "Quit proki")?)?;
        Ok(menu)
    };
    if let Ok(menu) = menu() {
        let _ = tray.set_menu(Some(menu));
    }
    let _ = tray.set_tooltip(Some(&status));
    let _ = tray.set_title(Some(&session));
}

fn on_menu(app: &AppHandle, id: &str) {
    match id {
        "note" => popup::new_note(app),
        "quit" => quit(app),
        _ => {
            if let Some(op) = id.strip_prefix("session:") {
                let (app, op) = (app.clone(), op.to_string());
                tauri::async_runtime::spawn(async move { session(app, op).await });
            } else if let Some(view) = id.strip_prefix("view:") {
                open_main(app, view);
            }
        }
    }
}

/// The main window on the page at `path` ("tasks/12": its view, then what in it, the page's to
/// read): made if it isn't there. A view there isn't: Today.
pub fn open_main(app: &AppHandle, path: &str) {
    let view = path.split('/').next().unwrap_or_default();
    let hash = if VIEWS.contains(&view) { path } else { "today" };
    if let Some(main) = app.get_webview_window("main") {
        let _ = main.emit_to("main", "navigate", hash);
        let _ = main.show();
        let _ = main.set_focus();
        return;
    }
    let built = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("main.html".into()))
        .title("proki")
        .inner_size(1180.0, 720.0)
        .min_inner_size(720.0, 480.0)
        .accept_first_mouse(true)
        // the view to open, read by the page as it starts (main.tsx): kept on a reload
        .initialization_script(&format!("if (!location.hash) location.hash = {};", json!(hash)));
    #[cfg(target_os = "macos")]
    let built = built.title_bar_style(tauri::TitleBarStyle::Overlay).hidden_title(true);
    match built.build() {
        Ok(main) => {
            let _ = main.set_focus();
        }
        Err(e) => eprintln!("the main window: {e}"),
    }
}

pub fn quit(app: &AppHandle) {
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        bus::ask(&app, "proki.app.quit", json!({})).await; // the engine stops, and closes this app
        tokio::time::sleep(Duration::from_secs(2)).await;
        app.exit(0);
    });
}

// --- start ------------------------------------------------------------------------------------

fn main() {
    let args = Args {
        nats: option("nats", "127.0.0.1:4222"),
        tools: option("tools", "127.0.0.1:9144"),
        tools_token: option("tools-token", &token()),
    };
    let tools = tools::Tools::new(&args.tools, &args.tools_token);
    let state = Proki {
        args,
        bus: tokio::sync::OnceCell::new(),
        queue: Mutex::new(popup::Queue::default()),
        tray: Mutex::new(("proki".into(), String::new())),
        tools,
    };

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|_app, _args, _cwd| {})) // one proki: a second one quits
        .plugin(tauri_plugin_dialog::init())
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            engine,
            tool,
            session,
            note,
            link,
            popup::popup_ready,
            popup::answer,
            popup::resize,
        ])
        .setup(|app| {
            let icon = tauri::image::Image::from_bytes(include_bytes!("../icons/tray.png"))?;
            TrayIconBuilder::with_id("proki")
                .icon(icon)
                .icon_as_template(true)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| on_menu(app, event.id().as_ref()))
                .build(app)?;
            update_tray(app.handle());

            popup::make(app.handle())?;
            tauri::async_runtime::spawn(bus::connect(app.handle().clone()));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("proki's UI couldn't start");

    app.run(|app, event| match event {
        RunEvent::ExitRequested { api, code: None, .. } => api.prevent_exit(), // its windows closed: it keeps running, in the Dock and the tray
        #[cfg(target_os = "macos")]
        RunEvent::Reopen { has_visible_windows: false, .. } => open_main(app, "today"), // its Dock icon clicked
        _ => {}
    });
}
