"""proki calibrate: how well the focus score agrees with your own 1–5 ratings."""

from __future__ import annotations

from datetime import timedelta

from proki.legacy import config as config_mod
from proki.legacy.commands.data import load_segments
from proki.legacy.core.calibration import Agreement, evaluate, sweep
from proki.legacy.core.store import Store

ENOUGH_TO_TUNE = 20


def run(config: config_mod.Config) -> int:
    ratings = [(r.answered_at, r.rating) for r in Store(config_mod.DB_PATH).ratings() if r.rating is not None]
    if not ratings:
        print("No focus ratings yet. proki asks a few times a day; you can also use"
              " \"Rate my focus now\" in the tray menu.")
        return 0
    spread = sorted({r for _, r in ratings})
    print(f"{len(ratings)} ratings, values used: {spread}")

    params = config.focus
    first, last = ratings[0][0], ratings[-1][0]
    segments = load_segments(config, first - 2 * max(params.horizons) - timedelta(minutes=20), last)

    print("\nAgreement with your ratings (rank correlation, −1..1; higher = the score")
    print("ranks moments the way you do; n = ratings with enough activity to score):")
    names = ["intensity", "depth", "fit", "hit rate", "continuity"]
    print(f"  {'window':>7}" + "".join(f"{n:>12}" for n in names))
    for horizon, measures in evaluate(ratings, segments, params).items():
        print(f"  {int(horizon.total_seconds() // 60):>5}m " + "".join(f"{_fmt(measures[n]):>12}" for n in names))

    if len(ratings) < ENOUGH_TO_TUNE:
        print(f"\nTry other settings once there are at least {ENOUGH_TO_TUNE} ratings"
              f" ({ENOUGH_TO_TUNE - len(ratings)} to go). Ratings across the whole 1–5 range help most.")
        return 0
    print("\nOther settings, one at a time (agreement of the main-window intensity):")
    for name, results in sweep(ratings, segments, params).items():
        best = max(results, key=lambda r: r[1].correlation if r[1].correlation is not None else -2)
        row = "  ".join(f"{label}: {_fmt(a)}" for label, a in results)
        print(f"  {name:<22} {row}   → best {best[0]}")
    print("\nSuggestions only: change a value in the config if it clearly agrees better.")
    return 0


def _fmt(a: Agreement) -> str:
    return f"{a.correlation:+.2f} (n={a.n})" if a.correlation is not None else f"– (n={a.n})"
