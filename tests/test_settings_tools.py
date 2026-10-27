from __future__ import annotations

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


def test_a_service_set_is_kept_its_key_in_the_keychain_and_asked_at_once(tmp_path, keychain):
    path, live = tmp_path / "config.toml", config.Settings()
    shown = settings.save(live, path, "llm", "google", " gemini-2.5-flash ", key="k")
    google = config.PROVIDERS["llm"]["google"]["url"]
    assert tomllib.loads(path.read_text()) == {"llm": {"provider": "google", "url": google, "model": "gemini-2.5-flash"}}
    assert keychain == {("proki", "llm.google"): "k"}
    assert (live.llm.api_url, live.llm.api_key, live.llm.model) == (google, "k", "gemini-2.5-flash")  # asked from now on
    assert shown["services"] == {"llm": {"provider": "google", "url": google, "model": "gemini-2.5-flash"}, "jev": None}
    assert shown["providers"]["llm"]["google"]["key"] and not shown["providers"]["llm"]["openai"]["key"]

    settings.save(live, path, "jev", "custom", "m", url="http://localhost:8000/")  # no key given: none kept
    loaded = config.load(path)  # the next start
    assert (loaded.llm.model, loaded.llm.api_key) == ("gemini-2.5-flash", "k")
    assert (loaded.jev.api_url, loaded.jev.api_key, loaded.jev.model) == ("http://localhost:8000", None, "m")
    settings.save(live, path, "llm", "google", "gemini-2.5-flash", key="")  # empty: the key's taken away
    assert keychain == {} and live.llm.api_key is None
    assert config.load(tmp_path / "nothing.toml").llm.model == ""  # not set: every ask fails

    for args, problem in [(("llm", "nope", "m"), "no provider 'nope'"), (("llm", "custom", "m"), "needs its url"),
                          (("llm", "openai", " "), "needs a model")]:
        with pytest.raises(ValueError, match=problem):
            settings.save(live, path, *args)


def test_the_models_at_a_provider_with_the_key_given_or_kept(monkeypatch, keychain):
    asked = []
    monkeypatch.setattr(settings.requests, "get", lambda url, headers, params, timeout: asked.append((url, headers, params)) or
                        Reply(200, {"data": [{"id": "models/b"}, {"id": "a"}, {"id": "a"}]}))
    keychain[("proki", "llm.google")] = "kept"
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
