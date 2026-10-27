"""What proki raises (proki/errors/): one root, groups, and where it happened."""

import pytest

from conftest import built, programs_folder
from proki.errors import ExprError, ProgramError, RuleError


def test_a_mistake_says_where_it_is(tmp_path):
    for config, kind, where, message in [
        ({"rules": [{"name": "r", "lhs": "x", "cmp": "gt"}]}, RuleError, ["main.json"], "rule 'r': rhs is missing"),  # its shape
        ({"signals": [{"name": "s", "expr": "kes + 1"}]}, ExprError, ["signal 's'"], "unknown name 'kes'"),  # what it says
        ({"rules": [{"name": "r", "lhs": 1, "cmp": "eq", "rhs": 1}],
          "programs": [{"name": "p", "initial": "a", "states": {"a": {"next": [{"when": ["r"], "goto": "b"}]}}}]},
         ProgramError, ["p.a: way out to 'b'"], "p has no state 'b'"),
    ]:
        with pytest.raises(kind) as caught:
            built(programs_folder(tmp_path, config))
        assert caught.value.where == where and caught.value.message == message
        assert str(caught.value) == ": ".join([*where, message])
