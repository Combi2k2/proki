from datetime import datetime, timedelta, timezone

from proki.legacy.config import parse
from proki.legacy.core.events import Finding, Level, Segment
from proki.legacy.core.policy import NudgePolicy
from proki.legacy.rules.fragmentation import Fragmentation

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def alternating(n: int, seconds: int = 10) -> list[Segment]:
    """n segments that alternate between two apps, ending at NOW."""
    start = NOW - timedelta(seconds=n * seconds)
    return [
        Segment(start + timedelta(seconds=i * seconds), start + timedelta(seconds=(i + 1) * seconds), "AB"[i % 2])
        for i in range(n)
    ]


def test_allowlist_matches_app_and_optional_title():
    config = parse({"track": [{"app": "Code"}, {"app": "Chrome", "title": "GitHub"}]})
    assert config.is_tracked("Code", "anything")
    assert config.is_tracked("Chrome", "PR #1 · GitHub")
    assert not config.is_tracked("Chrome", "YouTube")
    assert not config.is_tracked("Slack", "")


def test_fragmentation_fires_only_above_threshold():
    rule = Fragmentation(window=timedelta(minutes=10), max_switches=25)
    assert rule.check(alternating(20), NOW) is None
    finding = rule.check(alternating(40), NOW)
    assert finding is not None and "39 times" in finding.message


def test_policy_enforces_gap_and_snooze():
    policy = NudgePolicy(min_between=timedelta(minutes=20))
    nudge = Finding("r", "m", Level.NOTIFY)
    assert policy.allow(nudge, NOW)
    policy.record(nudge, NOW)
    assert not policy.allow(nudge, NOW + timedelta(minutes=5))
    assert policy.allow(nudge, NOW + timedelta(minutes=20))
    policy.snooze(NOW + timedelta(hours=1))
    assert not policy.allow(nudge, NOW + timedelta(minutes=30))
    assert policy.allow(Finding("r", "m", Level.QUIET), NOW + timedelta(minutes=30))


def test_policy_never_nudges_while_away():
    policy = NudgePolicy(min_between=timedelta(minutes=20))
    assert not policy.allow(Finding("r", "m", Level.NOTIFY), NOW, away=True)
