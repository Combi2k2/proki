// Questions and pokes, in the popup: one at a time, the urgent ones first. The page says when it's
// ready ("popup_ready"), gets each as "show" (null when it leaves), and answers with "answer".

use std::collections::VecDeque;
use std::time::Duration;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, LogicalSize, Manager, PhysicalPosition, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

use crate::{bus, proki};

pub enum Reply {
    Bus(async_nats::Subject), // the engine's question: {"answer": ...} to its reply subject
    Note,                     // "New note…": what's written goes to the engine
    Nothing,                  // a poke
}

pub struct Item {
    pub id: Value,
    pub text: String,
    pub options: Option<Vec<String>>,
    pub show: Value,
    pub reply: Reply,
}

#[derive(Default)]
pub struct Queue {
    waiting: VecDeque<Item>,
    showing: Option<Item>,
    ready: bool, // the page listens: what's shown before this would be lost
    pokes: u64,
    notes: u64,
}

pub fn make(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    WebviewWindowBuilder::new(app, "popup", WebviewUrl::App("popup.html".into()))
        .title("proki question")
        .inner_size(400.0, 160.0)
        .visible(false)
        .focused(false)
        .decorations(false)
        .transparent(true) // the card's rounded corners and shadow
        .shadow(false)
        .resizable(false)
        .maximizable(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .visible_on_all_workspaces(true)
        .accept_first_mouse(true) // a click on it while you're in another app clicks what's under it
        .build()
}

fn popup(app: &AppHandle) -> Option<WebviewWindow> {
    app.get_webview_window("popup")
}

pub fn enqueue(app: &AppHandle, item: Item) {
    {
        let mut queue = proki(app).queue.lock().unwrap();
        if item.show.get("urgent").and_then(Value::as_bool).unwrap_or(false) {
            if let Some(shown) = queue.showing.take() {
                queue.waiting.push_front(shown); // back in line, shown again after this one
            }
            queue.waiting.push_front(item);
        } else {
            queue.waiting.push_back(item);
        }
    }
    show_next(app);
}

pub fn show_next(app: &AppHandle) {
    let shown = {
        let mut queue = proki(app).queue.lock().unwrap();
        if !queue.ready || queue.showing.is_some() {
            return;
        }
        let Some(item) = queue.waiting.pop_front() else { return };
        let shown = json!({ "id": item.id, "text": item.text, "options": item.options, "show": item.show });
        queue.showing = Some(item);
        shown
    };
    let Some(popup) = popup(app) else { return };
    let _ = popup.emit_to("popup", "show", shown);
    place(&popup);
    let _ = popup.show(); // in front, but the app you're in keeps your keys
}

/// What's shown leaves the screen (its alarm, if it rings, stops with it).
fn hidden(app: &AppHandle) {
    proki(app).queue.lock().unwrap().showing = None;
    if let Some(popup) = popup(app) {
        let _ = popup.emit_to("popup", "show", Value::Null);
        let _ = popup.hide();
    }
}

pub fn cancel(app: &AppHandle, id: &Value) {
    let showing = {
        let mut queue = proki(app).queue.lock().unwrap();
        queue.waiting.retain(|item| &item.id != id);
        queue.showing.as_ref().is_some_and(|item| &item.id == id)
    };
    if showing {
        hidden(app);
        show_next(app);
    }
}

pub fn poke(app: &AppHandle, text: String, show: Value) {
    let id = {
        let mut queue = proki(app).queue.lock().unwrap();
        queue.pokes += 1;
        json!(format!("poke{}", queue.pokes))
    };
    enqueue(app, Item { id, text, options: Some(vec![]), show, reply: Reply::Nothing });
}

/// "New note…": what's on your mind (nothing written, nothing sent). The engine asks how urgent it is.
pub fn new_note(app: &AppHandle) {
    let id = {
        let mut queue = proki(app).queue.lock().unwrap();
        queue.notes += 1;
        json!(format!("note{}", queue.notes))
    };
    let text = "What's on your mind?".into();
    enqueue(app, Item { id, text, options: None, show: json!({ "title": "New note" }), reply: Reply::Note });
}

fn place(popup: &WebviewWindow) {
    let (Ok(Some(monitor)), Ok(size)) = (popup.primary_monitor(), popup.outer_size()) else { return };
    let area = monitor.work_area();
    let margin = (16.0 * monitor.scale_factor()) as i32;
    let x = area.position.x + area.size.width as i32 - size.width as i32 - margin;
    let _ = popup.set_position(PhysicalPosition::new(x, area.position.y + margin));
}

#[tauri::command]
pub fn popup_ready(app: AppHandle) {
    proki(&app).queue.lock().unwrap().ready = true;
    show_next(&app);
}

#[tauri::command]
pub fn answer(app: AppHandle, id: Value, answer: Value) {
    let item = {
        let mut queue = proki(&app).queue.lock().unwrap();
        match &queue.showing {
            Some(item) if item.id == id => queue.showing.take().unwrap(),
            _ => return,
        }
    };
    hidden(&app);
    match item.reply {
        Reply::Bus(subject) => bus::respond(&app, subject, json!({ "answer": answer })),
        Reply::Note => {
            if let Some(text) = answer.as_str().filter(|t| !t.trim().is_empty()) {
                let (app, text) = (app.clone(), text.to_string());
                tauri::async_runtime::spawn(async move {
                    bus::ask(&app, "proki.app.note", json!({ "text": text })).await;
                });
            }
        }
        Reply::Nothing => {}
    }
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(Duration::from_millis(300)).await;
        show_next(&app);
    });
}

/// The window fits the card (its height, from the page).
#[tauri::command]
pub fn resize(app: AppHandle, height: f64) {
    let Some(popup) = popup(&app) else { return };
    let (Ok(size), Ok(scale)) = (popup.inner_size(), popup.scale_factor()) else { return };
    let width = size.width as f64 / scale;
    let _ = popup.set_size(LogicalSize::new(width, height.ceil().clamp(80.0, 560.0)));
    place(&popup);
}
