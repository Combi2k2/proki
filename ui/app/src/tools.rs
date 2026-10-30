// The programs' tools, over MCP (proki/tools/server.py: streamable HTTP at /mcp, Authorization:
// Bearer the token in --tools-token's file). The windows call a tool by its name, the same tools
// an AI agent uses. Only what `tool` needs of MCP: initialize, then tools/call.

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

use serde_json::{json, Value};

const PROTOCOL: &str = "2025-06-18";

pub struct Tools {
    url: String,
    token_path: String,
    http: reqwest::Client,
    session: tokio::sync::Mutex<Option<String>>, // Mcp-Session-Id: connected on the first call (again after a failure)
    ids: AtomicU64,
}

impl Tools {
    pub fn new(address: &str, token_path: &str) -> Self {
        Tools {
            url: format!("http://{address}/mcp"),
            token_path: token_path.into(),
            http: reqwest::Client::builder().timeout(Duration::from_secs(15)).build()  // a provider asked has 10 of them
                .expect("the tools HTTP client should build"),
            session: tokio::sync::Mutex::new(None),
            ids: AtomicU64::new(1),
        }
    }

    /// Tool `name` with `args`: what it returns, or {error} (its mistake, or no engine).
    pub async fn call(&self, name: &str, args: Value) -> Value {
        let args = if args.is_object() { args } else { json!({}) };
        let mut session = self.session.lock().await;
        let called = async {
            if session.is_none() {
                *session = Some(self.connected().await?);
            }
            self.request(session.as_deref(), "tools/call", json!({ "name": name, "arguments": args })).await
        };
        match called.await {
            Ok(result) => {
                let text = result["content"][0]["text"].as_str().unwrap_or_default();
                if result["isError"].as_bool().unwrap_or(false) {
                    return json!({ "error": text });
                }
                match result.get("structuredContent") {
                    Some(content) if !content.is_null() => content.clone(),
                    _ => serde_json::from_str(text).unwrap_or_else(|e| json!({ "error": e.to_string() })),
                }
            }
            Err(e) => {
                *session = None; // the next call connects again (proki restarted, say)
                json!({ "error": e })
            }
        }
    }

    /// A session, retried while proki starts its tools (including first-run setup).
    async fn connected(&self) -> Result<String, String> {
        let given_up = tokio::time::Instant::now() + Duration::from_secs(30);
        loop {
            match self.connect().await {
                Err(error) if retryable(&error) && tokio::time::Instant::now() < given_up => {
                    tokio::time::sleep(Duration::from_millis(250)).await
                }
                connected => return connected,
            }
        }
    }

    async fn connect(&self) -> Result<String, String> {
        let hello = json!({ "protocolVersion": PROTOCOL, "capabilities": {},
                            "clientInfo": { "name": "proki-ui", "version": "0.1.2" } });
        let (session, _) = self.post(None, json!({ "jsonrpc": "2.0", "id": self.id(), "method": "initialize", "params": hello })).await?;
        let session = session.ok_or("no MCP session")?;
        self.post(Some(&session), json!({ "jsonrpc": "2.0", "method": "notifications/initialized" })).await?;
        // Don't consider the backend ready just because it accepted initialize. Confirm it can
        // serve the tools the UI depends on before the first screen leaves its loading state.
        self.request(Some(&session), "tools/list", json!({})).await?;
        Ok(session)
    }

    async fn request(&self, session: Option<&str>, method: &str, params: Value) -> Result<Value, String> {
        let (_, answer) = self.post(session, json!({ "jsonrpc": "2.0", "id": self.id(), "method": method, "params": params })).await?;
        let answer = answer.ok_or("no answer")?;
        if let Some(error) = answer.get("error") {
            return Err(error["message"].as_str().unwrap_or("MCP error").into());
        }
        Ok(answer["result"].clone())
    }

    fn id(&self) -> u64 {
        self.ids.fetch_add(1, Ordering::Relaxed)
    }

    /// One message posted: the session it names, and the answer (none for a notification), sent
    /// as JSON or as server-sent events.
    async fn post(&self, session: Option<&str>, message: Value) -> Result<(Option<String>, Option<Value>), String> {
        let token = tokio::fs::read_to_string(&self.token_path).await.map_err(|e| {
            // The app starts its bundled engine asynchronously; on slower machines the engine may
            // not have created the token yet when the first MCP connection arrives.
            if e.kind() == std::io::ErrorKind::NotFound {
                format!("tools token not ready: {e}")
            } else {
                format!("the tools' token: {e}")
            }
        })?;
        let mut posted = self.http.post(&self.url)
            .bearer_auth(token.trim())
            .header("Accept", "application/json, text/event-stream")
            .header("MCP-Protocol-Version", PROTOCOL)
            .json(&message);
        if let Some(session) = session {
            posted = posted.header("Mcp-Session-Id", session);
        }
        let response = posted.send().await.map_err(|e| format!("tools connection failed: {e}"))?;
        if !response.status().is_success() {
            let status = response.status();
            return Err(if status.is_server_error() {
                format!("tools server temporarily unavailable ({status})")
            } else {
                format!("tools server returned {status}; check that only one Proki instance is running")
            });
        }
        let header = |name: &str| response.headers().get(name).and_then(|v| v.to_str().ok()).map(String::from);
        let session = header("mcp-session-id");
        let events = header("content-type").is_some_and(|t| t.starts_with("text/event-stream"));
        let body = response.text().await.map_err(|e| e.to_string())?;
        if body.trim().is_empty() {
            return Ok((session, None));
        }
        let answer = if events {
            let id = message.get("id");
            body.split("\n\n")
                .map(|event| event.lines().filter_map(|l| l.strip_prefix("data:")).map(str::trim_start).collect::<Vec<_>>().join("\n"))
                .filter_map(|data| serde_json::from_str::<Value>(&data).ok())
                .find(|data| data.get("id") == id)
        } else {
            Some(serde_json::from_str(&body).map_err(|e| e.to_string())?)
        };
        Ok((session, answer))
    }
}

fn retryable(error: &str) -> bool {
    error.starts_with("tools token not ready:")
        || error.starts_with("tools connection failed:")
        || error.starts_with("tools server temporarily unavailable (")
}
