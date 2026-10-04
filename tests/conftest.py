from datetime import timedelta

import pytest

from proki.core.rules import Rule
from proki.core.signals import Depth, Primitive, Sector, Stream, Variable


@pytest.fixture(autouse=True)
def fresh_signals():
    """Each test starts with no signals, no rules and no run (the registry and the clock are global)."""
    saved, saved_rules = dict(Stream.registry), dict(Rule.registry)
    Stream.registry.clear()
    Rule.registry.clear()
    Primitive.rec = None
    Stream.now = None
    Stream.cycle = timedelta(seconds=10)
    Variable.store = None
    classify, depth_of = Sector.classify, Depth.depth_of
    yield
    Sector.classify, Depth.depth_of = classify, depth_of
    Stream.registry.clear()
    Stream.registry.update(saved)
    Rule.registry.clear()
    Rule.registry.update(saved_rules)
