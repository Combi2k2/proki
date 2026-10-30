from __future__ import annotations

import json
import tomllib
from datetime import UTC, datetime

import pytest

from proki import editor, settings as config
from proki.core.signals import Stream
from proki.programs.code.base import make_variable
from proki.services import jev
from proki.tools import settings


class Reply:
    def __init__(self, status, data=None, text=""):
        self.status_code, self.data, self.text = status, data, text

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code != 200:
            raise settings.requests.HTTPError(response=self)


def test_a_service_set_is_kept_its_key_apart_and_asked_at_once(tmp_path, keys):
    path, live = tmp_path / "config.toml", config.Settings()
    shown = settings.save(live, path, "llm", "google", " gemini-2.5-flash ", key="k")
    google = config.PROVIDERS["llm"]["google"]["url"]
    assert tomllib.loads(path.read_text()) == {"llm": {"provider": "google", "url": google, "model": "gemini-2.5-flash"}}
    assert json.loads(keys.read_text()) == {"llm.google": "k"} and keys.stat().st_mode & 0o077 == 0  # yours only
    assert (live.llm.api_url, live.llm.api_key, live.llm.model) == (google, "k", "gemini-2.5-flash")  # asked from now on
    assert shown["services"] == {"llm": {"provider": "google", "url": google, "model": "gemini-2.5-flash"}, "jev": None}
    assert shown["providers"]["llm"]["google"]["key"] and not shown["providers"]["llm"]["openai"]["key"]

    settings.save(live, path, "jev", "custom", "m", url="http://localhost:8000/")  # no key given: none kept
    loaded = config.load(path)  # the next start
    assert (loaded.llm.model, loaded.llm.api_key) == ("gemini-2.5-flash", "k")
    assert (loaded.jev.api_url, loaded.jev.api_key, loaded.jev.model) == ("http://localhost:8000", None, "m")
    settings.save(live, path, "llm", "google", "gemini-2.5-flash", key="")  # empty: the key's taken away
    assert json.loads(keys.read_text()) == {} and live.llm.api_key is None
    assert config.load(tmp_path / "nothing.toml").llm.model == ""  # not set: every ask fails

    for args, problem in [(("llm", "nope", "m"), "no provider 'nope'"), (("llm", "custom", "m"), "needs its url"),
                          (("llm", "openai", " "), "needs a model")]:
        with pytest.raises(ValueError, match=problem):
            settings.save(live, path, *args)


def test_the_models_at_a_provider_with_the_key_given_or_kept(monkeypatch, keys):
    asked = []
    monkeypatch.setattr(settings.requests, "get", lambda url, headers, params, timeout: asked.append((url, headers, params)) or
                        Reply(200, {"data": [{"id": "models/b"}, {"id": "a"}, {"id": "a"}]}))
    keys.write_text(json.dumps({"llm.google": "kept"}))
    assert settings.models("llm", "google", *settings.where("llm", "google", None, None)) == ["a", "b"]
    assert asked[-1][1] == {"Authorization": "Bearer kept"}
    settings.models("llm", "anthropic", "https://api.anthropic.com/v1", "k")
    assert asked[-1][1]["x-api-key"] == "k" and asked[-1][2] == {"limit": 1000}
    assert settings.models("jev", "openjev", "", None) == ["openjev"]  # it can't list them: the ones it has
    settings.models("jev", "openrouter", "https://openrouter.ai/api/alpha/decisions", "k")
    assert asked[-1][0] == "https://openrouter.ai/api/v1/models?output_modalities=decisions"  # where it lists them

    monkeypatch.setattr(settings.requests, "get", lambda *args, **kwargs: Reply(401))
    with pytest.raises(ValueError, match="the key isn't accepted"):
        settings.test("llm", "openai", "https://api.openai.com/v1", "wrong", None)


def test_jev_tested_with_one_question(monkeypatch):
    sent = []
    monkeypatch.setattr(jev.requests, "post", lambda url, headers, json, timeout: sent.append(json) or Reply(200, {"answers": {}}))
    assert settings.test("jev", "openjev", "https://jev", "k", None) == {"ok": True}
    assert sent[0]["model"] == "openjev"  # its provider's
    monkeypatch.setattr(jev.requests, "post", lambda *args, **kwargs: Reply(400, {"error": {"message": "no such model"}}))
    with pytest.raises(ValueError, match="HTTP 400: no such model"):  # why, as it says it
        settings.test("jev", "custom", "https://jev", None, "m")
    monkeypatch.setattr(jev.requests, "post", lambda url, headers, json, timeout: sent.append(json) or Reply(200, {"answers": {}}))
    monkeypatch.setattr(settings.requests, "get", lambda *args, **kwargs: Reply(200, {"data": [{"id": "b"}, {"id": "a"}]}))
    assert settings.test("jev", "openrouter", "https://jev", "k", None) == {"ok": True}
    assert sent[-1]["model"] == "a"  # the first it lists
    with pytest.raises(ValueError, match="pick a model first"):  # it has none to start from
        settings.test("jev", "custom", "https://jev", "k", None)


def test_an_expression_evaluated_gives_its_value_and_type_or_why_not():
    Stream.now = datetime(2026, 10, 22, tzinfo=UTC)  # a cycle ran
    make_variable("queue", [1, 2, 3])
    assert editor.evaluate("queue[1:]")["value"] == [2, 3]
    assert "unknown name" in editor.evaluate("nope")["error"]


def test_ports_are_saved_validated_and_preserved_when_services_change(tmp_path):
    path = tmp_path / "config.toml"
    live = config.Settings()
    defaults = config.read_ports(path)
    assert (defaults.activitywatch, defaults.nats, defaults.tools) == (5600, 4222, 9144)
    shown = settings.save_ports(path, activitywatch=5610, nats=4230, tools=9150)
    assert shown["ports"] == {"activitywatch": 5610, "nats": 4230, "tools": 9150}
    assert config.PORTS == defaults  # saving must not disconnect the running app
    settings.save(live, path, "llm", "google", "gemini")
    assert config.read_ports(path).tools == 9150
    settings.save_ports(path, activitywatch=5611, nats=4231, tools=9151)
    assert config.read(path)["llm"].model == "gemini"
    assert config.read_ports(path).activitywatch == 5611


@pytest.mark.parametrize("changed", [
    {"activitywatch": 0}, {"nats": 65536}, {"tools": True}, {"tools": 9144.5},
    {"tools": "9144"}, {"nats": 5600},
])
def test_bad_ports_do_not_replace_saved_settings(tmp_path, changed):
    path = tmp_path / "config.toml"
    settings.save_ports(path, activitywatch=5600, nats=4222, tools=9144)
    before = path.read_text()
    with pytest.raises(ValueError):
        settings.save_ports(path, **({"activitywatch": 5600, "nats": 4222, "tools": 9144} | changed))
    assert path.read_text() == before


def test_startup_loads_ports_and_launcher_forwards_them(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    path = tmp_path / "config.toml"
    settings.save_ports(path, activitywatch=5612, nats=4232, tools=9152)
    monkeypatch.setattr(config, "PORTS", config.Ports())
    config.configure_ports(path)
    assert config.PORTS == config.Ports(activitywatch=5612, nats=4232, tools=9152)
    spec = importlib.util.spec_from_file_location("test_launch_ports", Path(__file__).resolve().parents[1] / "launch.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(launcher.platforms, "current", lambda: SimpleNamespace(EXE=".exe", NATS_DIRS=[], AW_DIRS=[]))
    monkeypatch.setattr(launcher, "find_commands", lambda names, *args: {name: [name] for name in names})
    monkeypatch.setattr(launcher.ActivityWatchClient, "buckets", lambda self: {})
    services = launcher.services(app=True)
    assert services["NATS"].commands["nats-server"][-1] == "4232"
    for command in services["ActivityWatch"].commands.values():
        assert command[-4:] == ["--host", "127.0.0.1", "--port", "5612"]
    assert services["ActivityWatch Input"].commands["aw-watcher-input"][-1] == "5612"
