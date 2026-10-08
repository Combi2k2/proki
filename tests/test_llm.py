"""The LLM client (services/llm.py), against a stand-in service."""
import json

import pytest

from proki.services import llm as service
from proki.errors import LlmError
from proki.services.llm import Llm, families, parse_json


class Reply:
    def __init__(self, status, content=None, lines=()):
        self.status_code, self.content, self.lines = status, content, lines

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}

    def iter_lines(self, decode_unicode=True):
        return iter(self.lines)


@pytest.fixture
def posts(monkeypatch):
    """What's posted; the replies come from `posts.replies`, in order."""
    class Sent(list):
        replies: list

    sent = Sent()
    sent.replies = []

    def post(url, headers, json, timeout, stream=False):
        sent.append((url, headers, json))
        return sent.replies.pop(0)

    monkeypatch.setattr(service.requests, "post", post)
    return sent


def test_every_family_says_where_and_which_key():
    gemini = families()["gemini"]
    assert gemini.url.endswith("/openai") and gemini.key == "GEMINI_API_KEY" and gemini.models
    assert families()["ollama"].key is None  # local: no key


def test_a_family_needs_its_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LlmError, match="GEMINI_API_KEY isn't set"):
        Llm.of("gemini")
    with pytest.raises(LlmError, match="no LLM family 'nope'"):
        Llm.of("nope")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert Llm.of("gemini/gemini-2.5-pro").models == ("gemini-2.5-pro",)
    assert len(Llm.of("gemini", fallbacks=1).models) == 2


def test_asking_with_context(posts):
    posts.replies = [Reply(200, " Deep. ")]
    llm = Llm("https://x/v1", api_key="k", model="m", system="You help with focus.")
    assert llm.ask("Deep or shallow?", context={"activity": "thesis"}) == "Deep."
    url, headers, body = posts[0]
    assert url == "https://x/v1/chat/completions" and headers == {"Authorization": "Bearer k"}
    assert [m["role"] for m in body["messages"]] == ["system", "system", "user"]
    assert '"activity": "thesis"' in body["messages"][1]["content"]


def test_structured_answers_and_a_service_without_them(posts):
    schema = {"type": "object", "properties": {"choice": {"type": "string"}}}
    posts.replies = [Reply(400), Reply(200, 'Sure: {"choice": "deep"}')]  # no structured output: in the prompt
    assert Llm("https://x/v1", model="m").ask("Classify", schema=schema) == {"choice": "deep"}
    assert posts[0][2]["response_format"]["json_schema"]["schema"] == schema
    assert "response_format" not in posts[1][2] and json.dumps(schema) in posts[1][2]["messages"][-1]["content"]


def test_the_next_model_when_one_is_busy_then_a_pause(posts):
    posts.replies = [Reply(503), Reply(200, "hi")]
    assert Llm("https://x/v1", model=["busy", "free"]).ask("hi") == "hi"
    assert [body["model"] for _, _, body in posts] == ["busy", "free"]
    posts.replies = [Reply(503)]
    llm = Llm("https://x/v1", model="busy")
    with pytest.raises(LlmError, match="busy: HTTP 503"):
        llm.ask("hi")
    with pytest.raises(LlmError, match="skipped"):
        llm.ask("hi")  # every model failed recently: not asked again for a while
    assert llm.complete("hi") is None


def test_streaming(posts):
    events = ['data: {"choices": [{"delta": {"content": "1 "}}]}', "", ": keep-alive",
              'data: {"choices": [{"delta": {"content": "2"}}]}', "data: [DONE]"]
    posts.replies = [Reply(200, lines=events)]
    assert list(Llm("https://x/v1", model="m").ask("count", stream=True)) == ["1 ", "2"]
    assert posts[0][2]["stream"] is True


def test_json_in_a_reply():
    assert parse_json('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}
    assert parse_json("[1, 2]") == [1, 2]
    with pytest.raises(LlmError, match="not JSON"):
        parse_json("no")
