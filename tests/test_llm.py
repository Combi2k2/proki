"""The LLM client (services/llm.py), against a stand-in service."""
import json

import pytest

from proki.services import llm as service
from proki.errors import LlmError
from proki.settings import llm_families, llm_of
from proki.services.llm import Llm, parse_json


class Reply:
    def __init__(self, status, content=None):
        self.status_code, self.content = status, content

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


@pytest.fixture
def posts(monkeypatch):
    """What's posted; the replies come from `posts.replies`, in order."""
    class Sent(list):
        replies: list

    sent = Sent()
    sent.replies = []

    def post(url, headers, json, timeout):
        sent.append((url, headers, json))
        return sent.replies.pop(0)

    monkeypatch.setattr(service.requests, "post", post)
    return sent


def test_every_family_says_where_and_which_key():
    gemini = llm_families()["gemini"]
    assert gemini["url"].endswith("/openai") and gemini["key"] == "GEMINI_API_KEY" and gemini["models"]
    assert llm_families()["ollama"].get("key") is None  # local: no key


def test_a_family_needs_its_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LlmError, match="GEMINI_API_KEY isn't set"):
        llm_of("gemini")
    with pytest.raises(LlmError, match="no LLM family 'nope'"):
        llm_of("nope")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert llm_of("gemini/gemini-2.5-pro").model == "gemini-2.5-pro"
    assert llm_of("gemini").model == llm_families()["gemini"]["models"][0]  # the family's first


def test_asking_with_context(posts):
    posts.replies = [Reply(200, " Deep. ")]
    llm = Llm("https://x/v1", "k", "m")
    assert llm.ask("Deep or shallow?", context={"role": "You help with focus.", "activity": "thesis"}) == "Deep."
    url, headers, body = posts[0]
    assert url == "https://x/v1/chat/completions" and headers == {"Authorization": "Bearer k"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]  # the context, then the question
    assert '"activity": "thesis"' in body["messages"][0]["content"]


def test_structured_answers_and_a_service_without_them(posts):
    schema = {"type": "object", "properties": {"choice": {"type": "string"}}}
    posts.replies = [Reply(400), Reply(200, 'Sure: {"choice": "deep"}')]  # no structured output: in the prompt
    assert Llm("https://x/v1", None, "m").ask("Classify", schema=schema) == {"choice": "deep"}
    assert posts[0][2]["response_format"]["json_schema"]["schema"] == schema
    assert "response_format" not in posts[1][2] and json.dumps(schema) in posts[1][2]["messages"][-1]["content"]


def test_no_answer_raises(posts):
    posts.replies = [Reply(503), Reply(200, "  ")]
    llm = Llm("https://x/v1", None, "busy")
    with pytest.raises(LlmError, match="busy: HTTP 503"):
        llm.ask("hi")
    with pytest.raises(LlmError, match="an empty answer"):
        llm.ask("hi")


def test_json_in_a_reply():
    assert parse_json('```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}
    assert parse_json("[1, 2]") == [1, 2]
    with pytest.raises(LlmError, match="not JSON"):
        parse_json("no")
