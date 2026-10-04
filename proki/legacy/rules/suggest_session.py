"""Outside a session, focus is building up: suggest starting one (a pipeline)."""

from __future__ import annotations

from proki.legacy.rules.pipeline import Pipeline, SignalRule, all_of, is_false, is_true, majority


def suggest_session() -> Pipeline:
    return Pipeline("suggest a session", [
        all_of(                                                    # level 1
            is_false("in_session"),
            is_false("shutdown_done"),
            is_false("popup_open"),
            SignalRule("minutes_since_suggested", threshold=45, softness=10),
        ),
        majority(                                                  # level 2
            SignalRule("focus_rise", threshold=0.15, softness=0.05),  # 2-min focus now − 2 minutes ago
            SignalRule("focus_5m", threshold=0.5, softness=0.1),
            is_true("on_deep"),
        ),
    ])
