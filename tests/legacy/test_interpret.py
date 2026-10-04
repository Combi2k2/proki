from datetime import datetime, timedelta, timezone

from proki.legacy.core.events import Category, Segment
from proki.legacy.core.interpret import tools_take_context, watching_is_not_away

T0 = datetime(2026, 9, 30, 20, tzinfo=timezone.utc)
KINDS = {"youtube.com": "video_streaming", "zoom.us": "video_calls", "google.com": "search_engine",
         "claude.ai": "ai_assistant", "github.com": "code_hosting", "mail.google.com": "email"}
kind_of = lambda s: KINDS.get(s.key)


def seg(start, end, domain=None, category=None, away=False):
    url = f"https://{domain}/" if domain else None
    return Segment(T0 + timedelta(minutes=start), T0 + timedelta(minutes=end), "Chrome" if domain else "(away)",
                   url=url, category=category, away=away)


def test_no_input_while_watching_is_watching_not_away():
    out = watching_is_not_away([seg(0, 5, "youtube.com", Category.DISTRACTION), seg(5, 30, away=True)], kind_of)
    assert [(s.key, s.away, s.category) for s in out] == [("youtube.com", False, Category.DISTRACTION)] * 2
    assert out[1].end == T0 + timedelta(minutes=30)


def test_watching_is_capped_then_away_again():
    out = watching_is_not_away([seg(0, 5, "youtube.com"), seg(5, 300, away=True)], kind_of)
    assert out[1].end == T0 + timedelta(minutes=185) and out[2].away and out[2].start == out[1].end


def test_away_after_other_sites_stays_away():
    out = watching_is_not_away([seg(0, 5, "mail.google.com"), seg(5, 30, away=True)], kind_of)
    assert out[1].away


def test_tools_take_the_category_of_the_work_before():
    out = tools_take_context([seg(0, 10, "github.com", Category.DEEP), seg(10, 11, "google.com", Category.NEUTRAL),
                              seg(11, 12, "claude.ai", Category.DEEP), seg(12, 20, "mail.google.com", Category.SHALLOW),
                              seg(20, 21, "google.com", Category.NEUTRAL)], kind_of)
    assert [s.category for s in out] == [Category.DEEP, Category.DEEP, Category.DEEP, Category.SHALLOW, Category.SHALLOW]


def test_tools_without_recent_work_keep_their_own_category():
    out = tools_take_context([seg(0, 5, "github.com", Category.DEEP), seg(30, 31, "google.com", Category.NEUTRAL)], kind_of)
    assert out[1].category is Category.NEUTRAL


def test_a_locked_screen_counts_as_away(tmp_path):
    from proki.legacy.config import Config
    from proki.legacy.core.categories import Categorizer, prepare
    from proki.legacy.core.store import Store

    config = Config()
    locked = Segment(T0, T0 + timedelta(hours=8), "loginwindow")
    out = prepare([locked], config, Categorizer(config.categories, Store(tmp_path / "db")))
    assert all(s.away for s in out)
