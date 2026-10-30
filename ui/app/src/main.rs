// proki's UI: the tray, the popup and the windows. The launcher (launch.py) starts it, or you do;
// shipped, it starts the engine inside it (packaging/), unless proki's running already.
// It talks to the engine only over the message bus (bus.rs: --nats=host:port), and to the programs'
// tools over MCP (tools.rs: --tools=host:port, --tools-token=path), each where the engine is unless
// it's told. The pages are the same React pages (src/pages/), built into dist/; they reach this
// process through `window.proki` (src/lib/bridge.ts), each call one of the commands here.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bus;
mod popup;
mod tools;

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::Stdio;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;

use serde_json::{json, Value};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;

pub struct Args {
    pub nats: String,
    pub tools: String,
    pub tools_token: String,
    pub activitywatch: u16,
}

#[derive(Debug, PartialEq, serde::Deserialize)]
#[serde(default)]
struct Ports {
    activitywatch: u16,
    nats: u16,
    tools: u16,
}

impl Default for Ports {
    fn default() -> Self { Self { activitywatch: 5600, nats: 4222, tools: 9144 } }
}

fn read_ports(path: &std::path::Path) -> Result<Ports, String> {
    #[derive(Default, serde::Deserialize)]
    struct Config { #[serde(default)] ports: Ports }
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Ports::default()),
        Err(e) => return Err(format!("couldn't read settings: {e}")),
    };
    let config: Config = toml::from_str(text.trim_start_matches('\u{feff}')).map_err(|e| e.to_string())?;
    let ports = config.ports;
    if ports.activitywatch == 0 || ports.nats == 0 || ports.tools == 0 {
        return Err("ports must be between 1 and 65535".into());
    }
    if ports.activitywatch == ports.nats || ports.activitywatch == ports.tools || ports.nats == ports.tools {
        return Err("each service needs a different port".into());
    }
    Ok(ports)
}

#[cfg(test)]
mod port_tests {
    use super::*;

    fn parse(text: &str) -> Result<Ports, String> {
        let unique = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
        let path = std::env::temp_dir().join(format!("proki-ports-{}-{unique}.toml", std::process::id()));
        std::fs::write(&path, text).unwrap();
        let result = read_ports(&path);
        std::fs::remove_file(path).unwrap();
        result
    }

    #[test]
    fn defaults_and_saved_ports_match_the_engine() {
        assert_eq!(parse("").unwrap(), Ports::default());
        assert_eq!(parse("\u{feff}[ports]\nactivitywatch = 5612\nnats = 4232\ntools = 9152").unwrap(),
                   Ports { activitywatch: 5612, nats: 4232, tools: 9152 });
        assert_eq!(parse("[ports]\ntools = 9152").unwrap().activitywatch, 5600);
    }

    #[test]
    fn invalid_ports_are_rejected_before_starting_connections() {
        for text in ["[ports]\ntools = 0", "[ports]\nnats = 5600", "[ports]\ntools = 65536", "[ports]\ntools = true"] {
            assert!(parse(text).is_err());
        }
    }
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
    pub quitting: AtomicBool, // the engine asked to stop already
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

const LINKS: [(&str, &str); 4] = [ // the pages a page may open, by name
    ("github",        "https://github.com/Combi2k2/proki"),
    ("activitywatch", "https://activitywatch.net/downloads/"),
    ("aw-chrome",     "https://chromewebstore.google.com/detail/activitywatch-web-watcher/nglaklhklhcoonedhgnpgddginnjdadi"),
    ("aw-firefox",    "https://addons.mozilla.org/firefox/addon/aw-watcher-web/"),
];

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

/// The server and the three recording sources required by onboarding are available.
#[tauri::command]
async fn watching(app: AppHandle) -> bool {
    let client = reqwest::Client::new();
    let url = format!("http://127.0.0.1:{}/api/0/buckets/", proki(&app).args.activitywatch);
    let Ok(response) = client.get(url)
        .timeout(Duration::from_secs(1)).send().await else { return false };
    if !response.status().is_success() { return false; }
    let Ok(Value::Object(buckets)) = response.json::<Value>().await else { return false };
    ["currentwindow", "afkstatus", "os.hid.input"].iter().all(|kind|
        buckets.values().any(|bucket| bucket.get("type").and_then(Value::as_str) == Some(*kind)))
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
        if shipped(app).is_some() {
            menu.append(&item("command", "Install command-line tool…")?)?;
        }
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
        "command" => install_command(app),
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
        stop(&app).await; // the engine stops, and closes this app
        tokio::time::sleep(Duration::from_secs(2)).await;
        app.exit(0);
    });
}

/// The engine asked to stop, once, however the app quits (the tray, the Dock, Cmd-Q): the launcher
/// stops the rest with it, so nothing's left running.
async fn stop(app: &AppHandle) {
    if proki(app).quitting.swap(true, Ordering::SeqCst) {
        return;
    }
    if let Some(bus) = proki(app).bus.get() {
        let _ = tokio::time::timeout(Duration::from_secs(2), bus.request("proki.app.quit", "{}".into())).await;
    }
}

// --- the engine inside it ------------------------------------------------------------------------

/// The engine the app ships with (None: run from the repo, where the launcher starts it).
fn shipped(app: &AppHandle) -> Option<PathBuf> {
    let exe  = if cfg!(target_os = "windows") { "proki-engine.exe" } else { "proki-engine" };
    let path = app.path().resource_dir().ok()?.join("engine").join("proki-engine").join(exe);
    path.exists().then_some(path)
}

/// The shipped engine started, and what it needs with it, unless proki's running already: it
/// stops as the app quits.
fn start_engine(app: &AppHandle) {
    let Some(engine) = shipped(app) else { return };
    let tools = proki(app).args.tools.parse();
    if tools.is_ok_and(|at| TcpStream::connect_timeout(&at, Duration::from_millis(500)).is_ok()) {
        return;
    }
    let mut command = std::process::Command::new(engine);
    command.arg("--from-app").stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::null());
    #[cfg(target_os = "windows")]
    std::os::windows::process::CommandExt::creation_flags(&mut command, 0x0800_0000); // CREATE_NO_WINDOW
    if let Err(e) = command.spawn() {
        eprintln!("the engine couldn't start: {e}");
    }
}

/// `proki` made a command, in ~/.local/bin, for an AI agent to start the tools with (`proki mcp`):
/// how to add it to one, said. One that's there already and isn't ours is left as it is.
fn install_command(app: &AppHandle) {
    let Some(engine) = shipped(app) else { return };
    let home = std::env::var(if cfg!(target_os = "windows") { "USERPROFILE" } else { "HOME" }).unwrap_or_default();
    let bin  = PathBuf::from(home).join(".local").join("bin");
    let made = std::fs::create_dir_all(&bin).and_then(|_| {
        #[cfg(unix)]
        {
            let link = bin.join("proki");
            if link.is_symlink() {
                std::fs::remove_file(&link)?;
            }
            std::os::unix::fs::symlink(&engine, &link).map(|_| link)
        }
        #[cfg(windows)]
        {
            let shim = bin.join("proki.cmd");
            std::fs::write(&shim, format!("@\"{}\" %*\r\n", engine.display())).map(|_| shim)
        }
    });
    let text = match made {
        Ok(path) => {
            let path = path.display().to_string();
            let json = path.replace('\\', "\\\\");
            format!("proki is a command now: {path}\n\nAdd it to an AI agent with one of these:\n\n\
                     claude mcp add proki -- {path} mcp\n\n\
                     codex mcp add proki -- {path} mcp\n\n\
                     openclaw mcp set proki '{{\"command\":\"{json}\",\"args\":[\"mcp\"]}}'")
        }
        Err(e) => format!("proki couldn't be made a command in {}: {e}", bin.display()),
    };
    app.dialog().message(text).title("Command-line tool").show(|_| {});
}

// --- start ------------------------------------------------------------------------------------

fn main() {
    let ports = read_ports(&PathBuf::from(token()).with_file_name("config.toml"))
        .expect("Proki's local port settings are invalid");
    let args = Args {
        nats: option("nats", &format!("127.0.0.1:{}", ports.nats)),
        tools: option("tools", &format!("127.0.0.1:{}", ports.tools)),
        tools_token: option("tools-token", &token()),
        activitywatch: ports.activitywatch,
    };
    let tools = tools::Tools::new(&args.tools, &args.tools_token);
    let state = Proki {
        args,
        bus: tokio::sync::OnceCell::new(),
        queue: Mutex::new(popup::Queue::default()),
        tray: Mutex::new(("proki".into(), String::new())),
        tools,
        quitting: AtomicBool::new(false),
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
            watching,
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
            start_engine(app.handle());
            tauri::async_runtime::spawn(bus::connect(app.handle().clone()));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("proki's UI couldn't start");

    app.run(|app, event| match event {
        RunEvent::ExitRequested { api, code: None, .. } => api.prevent_exit(), // its windows closed: it keeps running, in the Dock and the tray
        #[cfg(target_os = "macos")]
        RunEvent::Reopen { has_visible_windows: false, .. } => open_main(app, "today"), // its Dock icon clicked
        RunEvent::Exit => tauri::async_runtime::block_on(stop(app)), // quit from the Dock or with Cmd-Q too
        _ => {}
    });
}
