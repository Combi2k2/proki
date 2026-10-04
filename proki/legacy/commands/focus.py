"""proki focus: focus intensity now, over the last hour, or replayed for a whole day."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from proki.legacy.commands.data import load_segments
from proki.legacy.config import Config
from proki.legacy.focus import FocusParams, Period, moment, series, summarize

SPARKS = "▁▂▃▄▅▆▇█"


def run(config: Config, span_minutes: int, day: str | None) -> int:
    if day:
        return replay_day(config, date.fromisoformat(day))
    params = config.focus
    now = datetime.now(timezone.utc)
    span = timedelta(minutes=span_minutes)
    segments = load_segments(config, now - span - 2 * max(params.horizons), now)

    print(f"Focus now ({now.astimezone():%H:%M}). intensity = depth × fit × hit rate × continuity")
    print("  window  active   depth   fit  hit rate  continuity (mean dwell)  intensity")
    for horizon in params.horizons:
        m = moment(segments, now, horizon, params)
        depth = f"{m.depth:.2f}" if m.depth is not None else "   –"
        print(f"  {_duration(horizon):>6}  {_duration(timedelta(seconds=m.window.active_seconds)):>6}"
              f"  {depth:>6}  {m.fit:4.2f}  {m.hit_rate:8.2f}  {m.continuity:10.2f} ({m.mean_dwell_seconds:4.0f}s)"
              f"      {_score(m.intensity)}")

    print(f"\nLast {span_minutes} min:")
    _print_period(summarize(segments, now - span, now, params), params)
    print(f"\nIntensity per minute, per window size ({_legend()}):")
    for horizon in params.horizons:
        marks = "".join(_spark(m.intensity) for m in series(segments, now, horizon, span, timedelta(minutes=1), params))
        print(f"  {_duration(horizon):>6}  {marks}")
    return 0


def replay_day(config: Config, day: date) -> int:
    """Replay a whole day hour by hour, to check the scores against your memory."""
    params = config.focus
    local = datetime.now().astimezone().tzinfo
    day_start = datetime.combine(day, time.min, local)
    day_end = min(day_start + timedelta(days=1), datetime.now(timezone.utc))
    segments = load_segments(config, day_start - 2 * params.main_horizon, day_end)

    print(f"{day:%A %Y-%m-%d}, main window {_duration(params.main_horizon)},"
          f" deep at intensity ≥ {params.deep_threshold} ({_legend()})")
    print("  hour   active  mean   deep  streak  intrusions/h  per minute")
    hour = day_start
    while hour < day_end:
        period = summarize(segments, hour, min(hour + timedelta(hours=1), day_end), params)
        if period.coverage > 0:
            marks = "".join(_spark(i) for i in period.intensities)
            print(f"  {hour:%H}:00  {period.coverage:5.0%}  {_score(period.mean_intensity)}"
                  f"  {period.deep_minutes:3d}m  {period.longest_deep_streak:4d}m  {period.intrusions_per_hour:11.1f}  {marks}")
        hour += timedelta(hours=1)

    print("\nWhole day:")
    _print_period(summarize(segments, day_start, day_end, params), params)
    return 0


def _print_period(period: Period, params: FocusParams) -> None:
    print(f"  mean intensity {_score(period.mean_intensity)} · deep {period.deep_minutes} min"
          f" · longest deep streak {period.longest_deep_streak} min"
          f" · {period.intrusions_per_hour:.1f} distraction switches/h · {period.coverage:.0%} active")


def _spark(intensity: float | None) -> str:
    if intensity is None:
        return "·"
    return SPARKS[min(len(SPARKS) - 1, int(intensity * len(SPARKS)))]


def _legend() -> str:
    return "▁ low … █ high, · mostly away"


def _score(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "   –"


def _duration(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds // 60}m{seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"
