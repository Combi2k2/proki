"""Direction check of proki's focus metric on the public SWELL-KW dataset.

SWELL-KW (Koldijk et al., ICMI 2014; DANS, doi:10.17026/dans-x55-69zp, CC BY-NC-SA 4.0):
25 people did office work (reports, presentations, research) in three conditions:
N = normal, I = with email interruptions, T = under time pressure. Every minute is
labelled with its condition. If the metric works, interrupted minutes should score
lower than normal ones.

Usage:
    uv run python benchmarks/swell_kw.py DATA_DIR
DATA_DIR needs features.csv ("A - Computer interaction features (Ulog - All Features
per minute)-Sheet_1.csv") and logs/ with the raw uLog XML files (a_pp*_c*_uLog_*.xml).
"""

from __future__ import annotations

import csv
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from proki.core.events import Category, Segment
from proki.core.focus import FocusParams, moment
from proki.core.timeline import merge

LAB_TIME = ZoneInfo("Europe/Amsterdam")  # the experiment ran in the Netherlands
AWAY_AFTER = timedelta(minutes=3)  # like ActivityWatch: no input for 3 min → away
CATEGORIES = {
    "WINWORD": Category.DEEP,  # writing reports
    "POWERPNT": Category.DEEP,  # making presentations
    "iexplore": Category.DEEP,  # researching for the task
    "OUTLOOK": Category.SHALLOW,  # where the interrupting emails arrive
}  # anything else (explorer, csrss, uLog, vlc, ...) → neutral
CONDITIONS = {"N": "normal", "I": "email interruptions", "T": "time pressure"}
MIN_ALIGNMENT = 0.95  # keystrokes per minute: our count vs the dataset's own, per participant


def load_log(log: Path) -> tuple[list[Segment], Counter[datetime]]:
    """The window in focus over time, and keystrokes per minute, from one raw uLog file.

    Like ActivityWatch's window watcher: the focused app changes only when a
    window is activated. Other events (keys, clicks, and background processes
    such as csrss firing in between) only show that the user is active.
    Keystrokes are counted only to check that the dataset's labels match the log.
    """
    events: list[tuple[datetime, str | None]] = []  # (time, newly activated app or None)
    keys: Counter[datetime] = Counter()
    for _, element in ET.iterparse(log, events=("end",)):
        if element.tag == "Event":
            stamp = element.findtext("TimeStamp")
            activated = element.findtext("EventAction") == "Window Activated"
            app = element.findtext("Control/ControlApplication") if activated else None
            if stamp:
                at = datetime.fromisoformat(stamp[:26].rstrip("Z") + "+00:00")
                events.append((at, app))
                if element.findtext("EventType") == "Keyboard":
                    keys[at.replace(second=0, microsecond=0)] += 1
            element.clear()
    events.sort(key=lambda e: e[0])
    segments = []
    focused = "?"
    for (start, app), (end, _) in zip(events, events[1:]):
        if app and app != "uLog 3.2":  # activating the logger's own window isn't the user's work
            focused = app
        if end - start > AWAY_AFTER:
            segments.append(Segment(start, end, "(away)", away=True))
        else:
            segments.append(Segment(start, end, focused, category=CATEGORIES.get(focused, Category.NEUTRAL)))
    return merge(segments), keys


def load_labels(features: Path) -> tuple[dict[str, dict[datetime, str]], dict[str, dict[datetime, int]]]:
    """Participant → {minute start (UTC) → condition letter}, and → {minute → keystrokes}."""
    labels: dict[str, dict[datetime, str]] = defaultdict(dict)
    keys: dict[str, dict[datetime, int]] = defaultdict(dict)
    for row in csv.DictReader(features.open(encoding="utf-8", errors="replace")):
        local = datetime.strptime(row["timestamp"][:15], "%Y%m%dT%H%M%S").replace(tzinfo=LAB_TIME)
        minute = local.astimezone(timezone.utc)
        labels[row["PP"].upper()][minute] = row["Condition"]
        keys[row["PP"].upper()][minute] = int(row["SnKeyStrokes"] or 0)
    return labels, keys


def aligned(expected: dict[datetime, int], counted: Counter[datetime]) -> float:
    """Correlation of the dataset's keystrokes per minute with ours; 1.0 = labels match the log."""
    minutes = sorted(expected)
    ours = [counted[m] for m in minutes]
    if len(set(ours)) < 2:
        return 0.0
    return statistics.correlation([expected[m] for m in minutes], ours)


def main(data: Path) -> int:
    labels, expected_keys = load_labels(data / "features.csv")
    segments: dict[str, list[Segment]] = defaultdict(list)
    keys: dict[str, Counter[datetime]] = defaultdict(Counter)
    for log in sorted((data / "logs").glob("*.xml")):
        pp = re.match(r"a_(pp\d+)_", log.name, re.IGNORECASE).group(1).upper()
        log_segments, log_keys = load_log(log)
        segments[pp] += log_segments
        keys[pp] += log_keys

    for pp in sorted(labels, key=lambda p: int(p[2:])):
        r = aligned(expected_keys[pp], keys[pp])
        if r < MIN_ALIGNMENT:
            print(f"excluding {pp}: its labels don't match its log (keystroke correlation {r:.2f})")
            del labels[pp]

    params = FocusParams()
    for horizon in (timedelta(minutes=2), timedelta(minutes=10)):
        # participant → condition → list of moments
        scores: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        steps = int(horizon / timedelta(minutes=1))
        for pp, minutes in labels.items():
            for minute, condition in minutes.items():
                if condition not in CONDITIONS:
                    continue
                # only windows that lie completely inside one condition
                if any(minutes.get(minute - timedelta(minutes=k)) != condition for k in range(steps)):
                    continue
                m = moment(segments[pp], minute + timedelta(minutes=1), horizon, params)
                if m.intensity is not None:
                    scores[pp][condition].append(m)
        report(horizon, scores)
    return 0


def report(horizon: timedelta, scores: dict[str, dict[str, list]]) -> None:
    parts = {
        "intensity": lambda m: m.intensity,
        "depth": lambda m: m.depth,
        "fit": lambda m: m.fit,
        "hit rate": lambda m: m.hit_rate,
        "continuity": lambda m: m.continuity,
    }
    print(f"\n=== window {int(horizon.total_seconds() // 60)} min ===")
    counts = {c: sum(len(s[c]) for s in scores.values()) for c in CONDITIONS}
    print("scored minutes:", ", ".join(f"{CONDITIONS[c]} {n}" for c, n in counts.items()))
    print(f"{'':12}" + "".join(f"{CONDITIONS[c]:>22}" for c in CONDITIONS))
    for name, get in parts.items():
        means = []
        for c in CONDITIONS:
            values = [get(m) for s in scores.values() for m in s[c] if get(m) is not None]
            means.append(statistics.mean(values) if values else float("nan"))
        print(f"{name:12}" + "".join(f"{v:22.3f}" for v in means))

    # Same person, different condition: how many participants score lower when interrupted?
    for other in ("I", "T"):
        diffs = []
        for s in scores.values():
            if s["N"] and s[other]:
                diffs.append(statistics.mean(m.intensity for m in s[other])
                             - statistics.mean(m.intensity for m in s["N"]))
        lower = sum(d < 0 for d in diffs)
        if diffs:
            print(f"{CONDITIONS[other]} vs normal, per participant: lower for {lower} of {len(diffs)},"
                  f" median difference {statistics.median(diffs):+.3f}")


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
