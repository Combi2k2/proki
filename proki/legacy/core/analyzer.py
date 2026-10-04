from __future__ import annotations

from datetime import datetime
from typing import Protocol

from proki.legacy.core.events import Finding, Segment


class Rule(Protocol):
    name: str

    def check(self, segments: list[Segment], now: datetime) -> Finding | None: ...


class Analyzer:
    """Runs every rule over the same slice of recent activity."""

    def __init__(self, rules: list[Rule]):
        self.rules = rules

    def run(self, segments: list[Segment], now: datetime) -> list[Finding]:
        findings = []
        for rule in self.rules:
            finding = rule.check(segments, now)
            if finding is not None:
                findings.append(finding)
        return findings
