"""The tools for an agent that starts its servers as commands (`proki mcp`): proki started if it isn't
running, then each of the agent's messages passed to it and its answers back, the token sent for you."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request

from proki import settings
from proki.services.nats import NatsBus
from proki.utils import wait_until

URL   = f"http://{settings.HOST}:{settings.TOOLS_PORT}/mcp"
START = 300   # seconds proki may take to start: it waits on you if the keychain asks
CALL  = 600   # seconds a tool may take to answer


def main() -> int:
    """Pass the agent's messages, a line each on stdin, to proki's tools, and their answers to stdout, until stdin closes."""
    up = lambda: NatsBus.is_up(settings.HOST, settings.TOOLS_PORT)
    if not up():
        launcher = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(settings.ROOT_DIR / "launch.py")]
        subprocess.Popen(launcher, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        wait_until(up, START)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")  # a line each, "\n" on Windows too
    headers = {"Authorization": f"Bearer {settings.TOOLS_TOKEN.read_text().strip() if settings.TOOLS_TOKEN.exists() else ''}",
               "Content-Type":  "application/json",
               "Accept":        "application/json, text/event-stream"}
    for line in sys.stdin:
        if not line.strip():
            continue
        asked = json.loads(line)
        try:
            with urllib.request.urlopen(urllib.request.Request(URL, line.encode(), headers), timeout=CALL) as answer:
                if session := answer.headers.get("mcp-session-id"):
                    headers["Mcp-Session-Id"] = session
                said = answer.read().decode()
        except (urllib.error.URLError, OSError) as e:
            if "id" in asked and "method" in asked:  # a request, not a notification: it's told why
                print(json.dumps({"jsonrpc": "2.0", "id": asked["id"], "error": {"code": -32000, "message": f"proki isn't answering: {e}"}}), flush=True)
            continue
        for message in [data[5:].strip() for data in said.splitlines() if data.startswith("data:")] or ([said] if said.strip() else []):
            if asked.get("method") == "initialize" and (version := json.loads(message).get("result", {}).get("protocolVersion")):
                headers["MCP-Protocol-Version"] = version
            print(message, flush=True)
    return 0
