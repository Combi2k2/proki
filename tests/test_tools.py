"""Your programs as tools over MCP (proki/tools/): what each does, its mistakes as the
tool's error, and the server, for clients with the token only."""

import asyncio
import json
import socket
import sqlite3

import pytest

from proki import settings, storage
from proki.core.programs import Program
from proki.engine import Engine
from proki.programs.shipped import Shipped
from proki.tools.server import Tools


@pytest.fixture
def tools():
    db = sqlite3.connect(":memory:")
    db.executescript(storage.SCHEMA)
    return Tools(Engine(settings.SHIPPED_DIR), Shipped(settings.SHIPPED_DIR, storage.StateDB(db)))


def call(tools, tool, **arguments):
    result = tools.call(tool, arguments)
    return result.is_error, json.loads(result.content[0].text) if not result.is_error else result.content[0].text


def test_every_kind_has_its_tools(tools):
    names = set(tools.tools)
    for kind in ("input", "variable", "signal", "rule", "program", "state", "branch", "action"):
        assert {f"add_{kind}", f"update_{kind}", f"remove_{kind}"} <= names
    rule = tools.tools["add_rule"][0].input_schema
    assert rule["properties"]["cmp"]["enum"][0] == "gt" and set(rule["required"]) == {"name", "lhs", "cmp", "rhs"}
    assert "at" in tools.tools["add_branch"][0].input_schema["properties"]


def test_a_program_made_through_the_tools(tools):
    assert call(tools, "add_program", name="late", desc="late at night")[0] is False
    assert call(tools, "add_state", program="late", name="poking", every=0.5)[0] is False
    error, said = call(tools, "add_branch", program="late", state="idle", goto="nowhere")
    assert error and "late has no state 'nowhere'" in said  # the mistake, said where
    assert call(tools, "add_branch", program="late", state="idle", goto="poking", **{"when": ["daytime > 1320"]})[0] is False
    error, detail = call(tools, "get_program", name="late")
    assert not error and [b["goto"] for b in detail["states"][0]["next"]] == ["poking"]
    assert call(tools, "update_state", program="late", name="poking", changes={"desc": "a poke"})[1]["desc"] == "a poke"
    error, gone = call(tools, "remove_program", name="late")
    assert not error and len(gone) == 4 and "late" not in Program.registry  # it, its two states, its way out


def test_several_changes_are_kept_together(tools):
    error, said = call(tools, "apply_changes", changes=[
        {"op": "add", "kind": "program", "data": {"name": "p"}},
        {"op": "add", "kind": "branch", "data": {"program": "p", "state": "idle", "goto": "b"}}])
    assert error and "no state 'b'" in said and "p" not in Program.registry


async def test_off_and_back_to_default(tools):
    call(tools, "switch_program", name="bedtime", on=False)
    assert not Program.registry["bedtime"].on
    call(tools, "update_program", name="day", changes={"desc": "mine"})
    call(tools, "reset_program", name="day")
    assert Program.registry["day"].desc != "mine"


async def test_the_server_answers_clients_with_the_token(tools):
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = tools.http(port, "secret")
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        async with httpx2.AsyncClient() as plain:
            assert (await plain.post(url, json={})).status_code == 401  # no token
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer secret"}) as client:
            async with streamable_http_client(url, http_client=client) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    assert "add_program" in {t.name for t in listed.tools}
                    result = await session.call_tool("add_program", {"name": "remote"})
                    assert not result.is_error and "remote" in Program.registry
    finally:
        server.should_exit = True
        await serving


def test_a_signal_of_a_program(tools):
    call(tools, "add_program", name="late")
    error, made = call(tools, "add_signal", name="hour", expr="daytime // 60", scope="program", program="late")
    assert not error and made["scope"] == "program"
    assert call(tools, "update_signal", name="hour", scope="program", program="late", changes={"desc": "the hour"})[1]["desc"] == "the hour"
    detail = call(tools, "get_program", name="late")[1]
    assert detail["name"] == "late"
    error, said = call(tools, "add_rule", name="late_hour", lhs="hour", cmp="ge", rhs=22)  # global: it doesn't see it
    assert error and "unknown name 'hour'" in said


def test_the_media_tools(tmp_path):
    from proki.services.media import Library

    db = sqlite3.connect(":memory:")
    db.executescript(storage.SCHEMA)
    library = Library(db, settings.ASSETS_DIR, tmp_path / "media")
    tools = Tools(Engine(settings.SHIPPED_DIR), Shipped(settings.SHIPPED_DIR, storage.StateDB(db)), library)
    page = call(tools, "get_media", kind="sound")[1]
    assert page["total"] == 1 and page["media"][0]["key"] == "alarm-clock"
    mine = tmp_path / "mine.png"
    mine.write_bytes((settings.ASSETS_DIR / "media/bugcat/stare_luffy.png").read_bytes())
    key = call(tools, "add_media", path=str(mine))[1]["key"]
    call(tools, "rename_media", key=key, name="luffy")
    assert call(tools, "get_media", keys=[key])[1]["media"][0]["name"] == "luffy"
    call(tools, "set_pool", name="questions", keys=[key])
    said = call(tools, "remove_media", keys=[key, "bugcat/sad"])[1]
    assert said["removed"] == ["bugcat/sad"] and "still used" in said["kept"][key]  # the pool has it
    assert call(tools, "get_media", keys=["bugcat/sad", key])[1]["media"][0]["key"] == key  # deleted: out
    assert [m["key"] for m in call(tools, "list_pools")[1]["questions"]] == [key]
    call(tools, "set_pool", name="questions", keys=[])
    away = call(tools, "list_specs", kind="action", program="pomodoro")[1][5]["id"]  # a poke's
    call(tools, "set_picks", id=away, keys=[key, "alarm-clock"])
    assert [m["key"] for m in call(tools, "get_picks", id=away)[1]["media"]] == [key, "alarm-clock"]
    assert "still used" in call(tools, "remove_media", keys=[key])[1]["kept"][key]  # a poke's pick
    error, said = call(tools, "set_picks", id="nobody", keys=[key])
    assert error and "no poke or question has id 'nobody'" in said


def test_the_board_is_tools_too_its_mistakes_their_errors():
    from proki.programs.code.work import Work

    db = sqlite3.connect(":memory:")
    db.executescript(storage.SCHEMA)
    tools = Tools(Engine(settings.SHIPPED_DIR), Shipped(settings.SHIPPED_DIR, storage.StateDB(db)), stores=[Work(db)])
    assert tools.tools["read_records"][0].annotations.read_only_hint and tools.tools["remove_record"][0].annotations.destructive_hint
    assert tools.tools["add_op"][0].input_schema["required"] == ["group", "op"]
    op = tools.tools["add_op"][0].input_schema["properties"]  # as every client reads it: one type a branch, any value said
    assert op["after"] == {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]} and op["fields"]["anyOf"]

    _, group = call(tools, "add_record", name="work.groups", fields={"name": "Thesis", "tags": ["papers"], "deadline": "2026-11-01T00:00:00+00:00"})
    _, task = call(tools, "add_record", name="work.tasks", fields={"group": group["id"], "name": "Read the papers", "after": []})
    assert call(tools, "change_record", name="work.tasks", id=task["id"], fields={"status": "dropped"}) == (False, {"ok": True})
    _, groups = call(tools, "read_records", name="work.groups")
    assert groups["records"][0]["deadline"] == "2026-11-01T00:00:00+00:00" and groups["fields"]["tags"]["desc"]
    assert call(tools, "read_records", name="work.tasks")[1]["records"][0]["status"] == "dropped"
    assert call(tools, "add_record", name="work.groups", fields={"name": "Visa", "tags": ["nope"]}) == (True, "work.groups.tags is of type array (['nope'])")
    assert call(tools, "add_record", name="work.tasks", fields={"name": "no group"}) == (True, "work.tasks needs its group")
    assert call(tools, "add_record", name="work.tasks", fields={"group": group["id"], "name": "x", "colour": "red"}) == (True, "work.tasks has no field colour")
    assert call(tools, "add_record", name="work.nope", fields={})[0]
