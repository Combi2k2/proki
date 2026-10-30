"""Bridge a stdio MCP client to Proki's authenticated local HTTP server."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

from proki import settings
from proki.services.nats import NatsBus
from proki.utils import wait_until

START = 300   # Proki may wait on a keychain prompt while starting.
CALL = 600    # A tool may take a while to answer.


class Bridge:
    """Keep one HTTP session for the stdio client, and rejoin after a server restart."""

    def __init__(self, url: str):
        self.url = url
        self.session: str | None = None
        self.version: str | None = None
        self.initialize: dict | None = None

    def post(self, message: dict) -> list[str]:
        headers = {"Authorization": f"Bearer {settings.TOOLS_TOKEN.read_text().strip() if settings.TOOLS_TOKEN.exists() else ''}",
                   "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.version:
            headers["MCP-Protocol-Version"] = self.version
        body = json.dumps(message, ensure_ascii=False).encode()
        with urllib.request.urlopen(urllib.request.Request(self.url, body, headers), timeout=CALL) as answer:
            if session := answer.headers.get("mcp-session-id"):
                self.session = session
            said = answer.read().decode()
        messages = [data[5:].strip() for data in said.splitlines() if data.startswith("data:")] or ([said] if said.strip() else [])
        if message.get("method") == "initialize":
            for item in messages:
                if version := json.loads(item).get("result", {}).get("protocolVersion"):
                    self.version = version
        return messages

    def forward(self, message: dict) -> list[str]:
        if message.get("method") == "initialize":
            self.initialize = message
        try:
            return self.post(message)
        except urllib.error.HTTPError as error:
            if error.code != 404 or self.initialize is None:
                raise
            # The server's in-memory session disappeared on restart. A new
            # initialize request must create the replacement session.
            self.session = self.version = None
            if message.get("method") == "initialize":
                return self.post(message)
            initialized = self.post(self.initialize)
            if not any("result" in json.loads(item) for item in initialized):
                raise RuntimeError("Proki did not reinitialize its MCP session") from error
            self.post({"jsonrpc": "2.0", "method": "notifications/initialized"})
            return self.post(message)


def main() -> int:
    """Forward one JSON-RPC message per stdin line and write replies to stdout."""
    settings.configure_ports()
    url = f"http://{settings.HOST}:{settings.PORTS.tools}/mcp"
    up = lambda: NatsBus.is_up(settings.HOST, settings.PORTS.tools)
    if not up():
        launcher = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(settings.ROOT_DIR / "launch.py")]
        subprocess.Popen(launcher, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        wait_until(up, START)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    bridge = Bridge(url)
    for line in sys.stdin:
        if not line.strip():
            continue
        asked = json.loads(line)
        try:
            said = bridge.forward(asked)
        except (urllib.error.URLError, OSError, RuntimeError) as error:
            if "id" in asked and "method" in asked:
                print(json.dumps({"jsonrpc": "2.0", "id": asked["id"], "error": {"code": -32000,
                      "message": f"proki isn't answering: {error}"}}), flush=True)
            continue
        for message in said:
            print(message, flush=True)
    return 0
