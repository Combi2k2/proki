"""Metrics: what today (and past days) looked like.

    ledger.py       one entry per minute: focus intensity + what you mostly did  (the data)
    day.py          a day's summary from those entries: deep minutes, streaks,
                    time per activity, progress toward the daily goal           (the numbers)
    keeper.py       scores new minutes as time passes and saves them; today()   (the glue)
    quota.py        the daily deep-work quota (rises with you, never drops by itself)
    consistency.py  how consistently sessions start at the usual time
    history.py      sessions and the chain of kept days

All are UI-independent: the tray, developer tools and a later GUI read the same data.
Import from the modules (e.g. `proki.legacy.metrics.keeper`); this package imports nothing itself.
"""
