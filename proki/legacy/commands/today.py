"""proki today / proki week: the scoreboard as the tray shows it, for checking the data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from proki.legacy import config as config_mod
from proki.legacy.commands.data import load_segments
from proki.legacy.metrics.quota import QuotaKeeper
from proki.legacy.metrics.day import day_bounds, summarize_day
from proki.legacy.metrics.keeper import ScoreKeeper
from proki.legacy.core.store import Store
from proki.legacy.ui.board import duration, scoreboard_lines


def keeper(config: config_mod.Config) -> ScoreKeeper:
    return ScoreKeeper(
        Store(config_mod.DB_PATH),
        lambda start, end: load_segments(config, start, end),
        config.focus,
        config.day_starts,
    )


def run_today(config: config_mod.Config) -> int:
    k = keeper(config)
    now = datetime.now(timezone.utc)
    added = k.update(now)
    quota = QuotaKeeper(k.store, config.quota, config.day_starts, config.focus.deep_threshold)
    today = k.today(now, quota.today(now, k.today(now).deep_minutes))
    print(f"{today.day:%A %Y-%m-%d} (minutes added now: {added})")
    for line in scoreboard_lines(today, config.focus.deep_threshold):
        print(" ", line)
    return 0


def run_week(config: config_mod.Config) -> int:
    k = keeper(config)
    now = datetime.now(timezone.utc)
    k.update(now)
    print(f"  {'day':<16}{'deep':>8}{'streak':>8}{'mean':>7}  goal")
    for back in range(6, -1, -1):
        day, start, end = day_bounds(now - timedelta(days=back), config.day_starts)
        entries = k.store.minutes(start, end)
        if not entries:
            continue
        d = summarize_day(day, entries, config.focus.deep_threshold, config.quota.start)
        mean = f"{d.mean_intensity:.2f}" if d.mean_intensity is not None else "   –"
        print(f"  {day:%a %Y-%m-%d}  {duration(d.deep_minutes):>8}{d.longest_streak:>7}m{mean:>7}  {d.goal_progress:.0%}")
    return 0
