# F-010 Metrics

| Status | Area | Code |
| --- | --- | --- |
| 🟡 Needs polish | Insight | `ui/src/views/metrics.tsx`, `proki/metrics.py`, `proki/backfill.py` |

Your focus and activity across days and weeks.

## How it works
- Charts: each reported signal over a horizon, in buckets that fit it.
- Signals: every global signal, to report or not. A persisted one also sets how long it's kept
  and how its buckets are made (mean, sum, ...).
- The shipped ones: `focus_history` and `engaged_history` (a week), `session.daily` (a year).
- `proki-backfill --days 14` fills a persisted signal's past from what ActivityWatch recorded.

## Limits
- Only persisted signals have a past; a new one starts from when it's added, unless backfilled.
