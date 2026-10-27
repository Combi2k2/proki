"""The tools, collected and served on this machine (`Tools`), for the clients holding proki's
token. Each client is told what they are as it connects."""

from __future__ import annotations

import contextlib
import json
import secrets
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import mcp_types as types
import uvicorn
from mcp.server.lowlevel import Server

import proki.tools
from proki.engine import Engine
from proki.errors import ProkiError
from proki.programs.code.work import Work
from proki.programs.shipped import Shipped
from proki.services.media import Library
from proki.settings import Settings
from proki.tools import media, programs, records, settings
from proki.tools.base import Tool

ANY   = {"anyOf": [{"type": kind} for kind in ("string", "number", "boolean", "object", "array", "null")]}  # any value at all
NESTS = ("items", "additionalProperties")                                                              # a schema in it
LISTS = ("anyOf", "oneOf", "allOf")                                                                    # schemas in it
ABOUT = ("description", "title", "default")                                                            # about the value, whatever its type


class Tools:
    """The programs' tools, the media library's if there's one, each store's (`stores`: what
    `tools()` gives its own, like `Work`), and the services' (`config`: the ones asked)."""

    def __init__(self, engine: Engine, shipped: Shipped, library: Library | None = None, stores: Iterable[Work] = (),
                 config: Settings | None = None):
        made = [*programs.tools(engine, shipped), *(media.tools(library, engine) if library else []),
                *settings.tools(config or Settings()), *records.tools(), *(tool for store in stores for tool in store.tools())]
        self.tools: dict[str, tuple[types.Tool, Callable[[dict], Any]]] = {t.name: (served(t), t.run) for t in made}
        self.server = Server("proki", version="0.1", instructions=proki.tools.__doc__,
                             on_list_tools=self.list_tools, on_call_tool=self.call_tool)

    async def list_tools(self, ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[tool for tool, _ in self.tools.values()])

    async def call_tool(self, ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        return self.call(params.name, params.arguments or {})

    def call(self, name: str, arguments: dict) -> types.CallToolResult:
        """Run tool `name`: what it returns, or its mistake as the tool's error."""
        if name not in self.tools:
            return error(f"no tool {name!r}")
        tool, run = self.tools[name]
        if missing := [arg for arg in tool.input_schema["required"] if arg not in arguments]:
            return error(f"{name} needs {', '.join(missing)}")
        if unknown := [arg for arg in arguments if arg not in tool.input_schema["properties"]]:
            return error(f"{name} has no {', '.join(unknown)}")
        try:
            result = run(arguments)
        except KeyError as e:
            return error(f"no {e.args[0]!r}")
        except (ProkiError, ValueError) as e:
            return error(str(e))
        result = {"ok": True} if result is None else result
        text   = json.dumps(result, ensure_ascii=False, default=str)
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)],
                                    structured_content=result if isinstance(result, dict) else {"result": result})

    def http(self, port: int, token: str) -> uvicorn.Server:
        """The tools on this machine's `port`, for the clients sending `token`.
        `await server.serve()` serves them, `should_exit = True` stops it."""
        app = Bearer(self.server.streamable_http_app(), token)
        return Quiet(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on",
                                    timeout_graceful_shutdown=2))  # a connection left open doesn't hold proki up

    @staticmethod
    def token(path: Path) -> str:
        """The token at `path`, made the first time (readable by you only)."""
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(secrets.token_urlsafe(32))
            path.chmod(0o600)
        return path.read_text().strip()


def served(tool: Tool) -> types.Tool:
    hints = (types.ToolAnnotations(read_only_hint=True) if tool.readonly else
             types.ToolAnnotations(destructive_hint=True) if tool.undoable else None)
    return types.Tool(name=tool.name, description=tool.desc, annotations=hints,
                      input_schema={"type": "object", "properties": {name: portable(arg) for name, arg in tool.args.items()},
                                    "required": list(tool.required)})


def portable(schema: dict) -> dict:
    """`schema` as every client reads it: a value of one of several types, a branch for each; one
    that says nothing, any value."""
    if not schema:
        return ANY
    made = {k: [portable(s) for s in v] if k in LISTS else portable(v) if k in NESTS and isinstance(v, dict) else
              {n: portable(s) for n, s in v.items()} if k == "properties" else v for k, v in schema.items()}
    if not isinstance(kinds := made.get("type"), list):
        return made
    about, rest = ({k: v for k, v in made.items() if (k in ABOUT) == inside and k != "type"} for inside in (True, False))
    return about | {"anyOf": [{"type": kind} if kind == "null" else {"type": kind, **rest} for kind in kinds]}


def error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


class Bearer:
    """Lets through the HTTP requests that send the token, and nothing else."""

    def __init__(self, app: Any, token: str):
        self.app, self.expected = app, f"Bearer {token}".encode()

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and dict(scope["headers"]).get(b"authorization") != self.expected:
            await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"proki: a token is needed"})
            return
        await self.app(scope, receive, send)


class Quiet(uvicorn.Server):
    """A server that leaves the signals to proki (it stops when proki says so)."""

    @contextlib.contextmanager
    def capture_signals(self):
        yield
