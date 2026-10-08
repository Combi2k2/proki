"""What proki raises (proki/errors/): one root, groups, and where it happened."""
import json

import pytest

from proki.compiler import compile_config
from proki.errors import ConfigError, ExprError, LlmError, ProgramError, ProkiError, RuleError, ServiceError


def test_the_groups():
    assert issubclass(RuleError, ConfigError) and issubclass(ConfigError, ProkiError)
    assert issubclass(ConfigError, ValueError)  # a value proki can't use: old `except ValueError` still catch it
    assert issubclass(LlmError, ServiceError) and not issubclass(LlmError, ValueError)


def test_a_mistake_says_where_it_is(tmp_path):
    path = tmp_path / "config.json"
    for config, kind, where, message in [
        ({"rules": [{"name": "r", "lhs": "x", "cmp": "gt"}]}, RuleError, ["config.json", "rule 'r'"], "rhs is missing"),
        ({"signals": [{"name": "s", "expr": "kes + 1"}]}, ExprError, ["config.json", "signal 's'"], "unknown name 'kes'"),
        ({"rules": [{"name": "r", "lhs": 1, "cmp": "eq", "rhs": 1}],
          "programs": [{"name": "p", "initial": "a", "states": {"a": {"next": [{"if": ["r"], "goto": "b"}]}}}]},
         ProgramError, ["config.json", "p.a"], "p has no state 'b'"),
    ]:
        path.write_text(json.dumps(config))
        with pytest.raises(kind) as caught:
            compile_config(path)
        assert caught.value.where == where and caught.value.message == message
        assert str(caught.value) == ": ".join([*where, message])
