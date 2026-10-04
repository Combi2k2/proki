import requests

from proki.legacy.core.ai import AISettings, TaskHelper, _json_list


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self.payload = status, payload

    def json(self):
        return self.payload


def reply(text):
    return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": text}]}}]})


def test_falls_back_to_the_next_model_when_one_is_busy(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append(url.split("/models/")[1].split(":")[0])
        return FakeResponse(503) if "flash-lite" not in url else reply('["step one", "step two"]')

    monkeypatch.setattr(requests, "post", post)
    helper = TaskHelper("key", AISettings())
    assert helper.steps("Revise for the final", "", 240, "too_long") == ["step one", "step two"]
    assert calls == ["gemini-3.5-flash", "gemini-3.5-flash-lite"]


def test_after_every_model_fails_the_ai_is_skipped_for_a_while(monkeypatch):
    calls = []
    monkeypatch.setattr(requests, "post", lambda url, **k: calls.append(url) or FakeResponse(503))
    helper = TaskHelper("key", AISettings())
    assert helper.steps("x", "", 90, "too_long") is None
    assert helper.steps("x", "", 90, "too_long") is None
    assert len(calls) == 2  # the second request didn't wait for any model


def test_thought_parts_are_ignored(monkeypatch):
    payload = {"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": "Stats final"}]}}]}
    monkeypatch.setattr(requests, "post", lambda url, **k: FakeResponse(200, payload))
    assert TaskHelper("key", AISettings()).group_name("revise", "") == "Stats final"


def test_json_list_parsing():
    assert _json_list('Sure!\n["a", "b"]') == ["a", "b"]
    assert _json_list("no list here") is None and _json_list("[]") is None
