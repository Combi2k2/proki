"""proki check: recent activity with categories, and rule findings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from proki.legacy.commands.data import load_segments
from proki.legacy.config import Config
from proki.legacy.core.analyzer import Analyzer
from proki.legacy.core.categories import label, summary, unknown
from proki.legacy.rules.fragmentation import default_rules
from proki.legacy.core.timeline import BROWSER_APPS


def run(config: Config, show_all: bool) -> int:
    now = datetime.now(timezone.utc)
    segments = load_segments(config, now - timedelta(minutes=config.lookback_minutes), now)

    shown = segments if show_all else segments[-15:]
    print(f"{len(segments)} segments in the last {config.lookback_minutes} min"
          + ("" if show_all else f" (last {len(shown)} shown, --all for every one)"))
    for s in shown:
        print(f"  {s.start.astimezone():%H:%M:%S}  {s.duration.total_seconds():6.0f}s  {label(s):<12}  {s.key}")
    print(summary(segments, config.lookback_minutes))

    if any(s.app in BROWSER_APPS and not s.url for s in segments if not s.away):
        print("\nBrowser time without website info: install the ActivityWatch web extension"
              " so websites can be classified one by one.")

    unclassified = unknown(segments, timedelta(0))
    if unclassified:
        print("\nNot classified yet (proki categorize KEY CATEGORY):")
        for key, total in unclassified:
            print(f"  {total.total_seconds() / 60:5.1f} min  {key}")

    findings = Analyzer(default_rules()).run(segments, now)
    print("\nFindings:" if findings else "\nFindings: none")
    for f in findings:
        print(f"  [{f.rule}] {f.message}")
    return 0
