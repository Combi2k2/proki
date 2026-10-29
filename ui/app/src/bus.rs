// The message bus (NATS):
//
//   proki.ask.usr   questions: shown in the popup, one at a time, answered with
//                   {"answer": the option's index, or the text}
//   proki.ui        one-way: poke, cancel, status, open, quit
//   proki.app.*     what the UI asks of the engine: note, quit, tasks, notes, apps, today, metrics (proki/serve.py)

use std::time::Duration;

use async_nats::RequestErrorKind;
use futures::StreamExt;
use serde_json::{json, Value};
use tauri::AppHandle;

use crate::popup::{self, Item, Reply};
use crate::{open_main, proki, update_tray};

pub async fn connect(app: AppHandle) {
    let address = proki(&app).args.nats.clone();
    let bus = loop {
        match async_nats::connect(&address).await {
            Ok(bus) => break bus,
            Err(_) => tokio::time::sleep(Duration::from_secs(1)).await, // the engine may still be starting it
        }
    };
    let asked = bus.queue_subscribe("proki.ask.usr", "proki.ask.usr".into()).await;
    let shown = bus.subscribe("proki.ui").await;
    let _ = proki(&app).bus.set(bus);
    if let Ok(mut asked) = asked {
        let app = app.clone();
        tauri::async_runtime::spawn(async move {
            while let Some(message) = asked.next().await {
                on_asked(&app, message);
            }
        });
    }
    if let Ok(mut shown) = shown {
        let app = app.clone();
        tauri::async_runtime::spawn(async move {
            while let Some(message) = shown.next().await {
                on_shown(&app, message);
            }
        });
    }
    proki(&app).tray.lock().unwrap().0 = "proki: connected".into();
    update_tray(&app);
}

fn decode(message: &async_nats::Message) -> Value {
    serde_json::from_slice(&message.payload).unwrap_or(Value::Null)
}

fn on_asked(app: &AppHandle, message: async_nats::Message) {
    let request = decode(&message);
    let options = request["options"].as_array().map(|options| {  // what each means is for jev and the LLM
        options.iter().map(|o| o[0].as_str().unwrap_or_default().to_string()).collect()
    });
    let show = if request["show"].is_object() { request["show"].clone() } else { json!({}) };
    popup::enqueue(app, Item {
        id: request["id"].clone(),
        text: request["context"].as_str().unwrap_or_default().into(),
        options,
        show,
        reply: message.reply.map_or(Reply::Nothing, Reply::Bus),
    });
}

fn on_shown(app: &AppHandle, message: async_nats::Message) {
    let m = decode(&message);
    match m["type"].as_str().unwrap_or_default() {
        "poke" => popup::poke(app, m["text"].as_str().unwrap_or_default().into(),
                              json!({ "title": m["title"], "media": m["media"], "sound": m["sound"] })),
        "cancel" => popup::cancel(app, &m["id"]),
        "status" => {
            let session = match m["session"].as_f64() {
                Some(minutes) => format!("{minutes}m"), // 12 as "12m", as JS says it
                None => String::new(),
            };
            *proki(app).tray.lock().unwrap() = (m["text"].as_str().unwrap_or_default().into(), session);
            update_tray(app);
        }
        "open" => {
            open_main(app, m["path"].as_str().unwrap_or_default());
        }
        "quit" => app.exit(0),
        _ => {}
    }
}

/// What the engine answers to `request` on `subject`, or {error} (no engine, or no answer in 5s).
/// While proki's still starting (no bus yet, or nothing serving `subject`) it's asked again, for
/// up to 30s.
pub async fn ask(app: &AppHandle, subject: &str, request: Value) -> Value {
    let given_up = tokio::time::Instant::now() + Duration::from_secs(30);
    loop {
        let starting = tokio::time::Instant::now() < given_up;
        let Some(bus) = proki(app).bus.get() else {
            if !starting {
                return json!({ "error": "not connected to proki" });
            }
            tokio::time::sleep(Duration::from_millis(250)).await;
            continue;
        };
        let asked = bus.request(subject.to_string(), request.to_string().into());
        return match tokio::time::timeout(Duration::from_secs(5), asked).await {
            Ok(Ok(message)) => decode(&message),
            Ok(Err(e)) if starting && e.kind() == RequestErrorKind::NoResponders => {
                tokio::time::sleep(Duration::from_millis(250)).await;
                continue;
            }
            Ok(Err(e)) => json!({ "error": e.to_string() }),
            Err(_) => json!({ "error": "timed out" }),
        };
    }
}

/// An answer to the engine's question, to its reply subject.
pub fn respond(app: &AppHandle, subject: async_nats::Subject, answer: Value) {
    let Some(bus) = proki(app).bus.get().cloned() else { return };
    tauri::async_runtime::spawn(async move {
        let _ = bus.publish(subject, answer.to_string().into()).await;
    });
}
