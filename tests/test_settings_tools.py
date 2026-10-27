from __future__ import annotations

import tomllib
from datetime import UTC, datetime

import pytest

from proki import editor
from proki.core.signals import Stream
from proki.programs.code.base import make_variable
from proki.tools import settings


def test_settings_changed_are_kept_in_the_file_and_a_key_beside_it(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[nats]\nport = 4222\n[llm]\nmodel = "gemini"\n')
    read = settings.write(path, {"jev": {"enabled": True, "url": "http://jev", "key": "secret"}, "nats": {"port": None}},
                          {"GEMINI_API_KEY": "k"})
    assert tomllib.loads(path.read_text()) == {"llm": {"model": "gemini"}, "jev": {"enabled": True, "url": "http://jev", "key": "secret"}}
    assert read["sections"]["jev"]["key"]["value"] == {"set": True} and read["sections"]["nats"]["port"]["value"] == 4222
    assert read["keys"]["GEMINI_API_KEY"] == {"set": True, "in_file": True}
    settings.write(path, {}, {"GEMINI_API_KEY": ""})
    assert "GEMINI_API_KEY" not in (tmp_path / ".env").read_text()
    for sections, keys, problem in [({"nope": {}}, {}, "no section"), ({"nats": {"port": "x"}}, {}, "is a integer"),
                                    ({"llm": {"model": "nope/x"}}, {}, "no LLM family"), ({}, {"NOPE": "x"}, "no key")]:
        with pytest.raises(ValueError, match=problem):
            settings.write(path, sections, keys)


def test_an_expression_evaluated_gives_its_value_and_type_or_why_not():
    Stream.now = datetime(2026, 10, 22, tzinfo=UTC)  # a cycle ran
    make_variable("queue", [1, 2, 3])
    assert editor.evaluate("queue[1:]")["value"] == [2, 3]
    assert "unknown name" in editor.evaluate("nope")["error"]
