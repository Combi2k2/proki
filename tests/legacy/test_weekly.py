from datetime import date, timedelta

from proki.legacy.core.weekly import WeekFacts, review_due, review_text, week_start

MON = date(2026, 9, 28)
FRI, SAT = MON + timedelta(days=4), MON + timedelta(days=5)
WORKDAYS = ("mon", "tue", "wed", "thu", "fri")


def test_week_starts_on_monday():
    assert week_start(FRI) == MON and week_start(MON) == MON


def test_due_on_the_last_workday_once_a_week():
    assert not review_due(MON + timedelta(days=3), None, WORKDAYS)
    assert review_due(FRI, None, WORKDAYS)
    assert not review_due(FRI, MON, WORKDAYS)  # done this week
    assert review_due(SAT, MON - timedelta(days=7), WORKDAYS)  # Friday's was missed


def test_missed_last_week_comes_up_at_the_next_shutdown():
    next_tuesday = MON + timedelta(days=8)
    assert review_due(next_tuesday, MON - timedelta(days=7), WORKDAYS)  # last week not reviewed
    assert not review_due(next_tuesday, MON, WORKDAYS)  # last week reviewed: wait for Friday


def test_review_text():
    facts = WeekFacts(
        deep_by_day={MON: 250, MON + timedelta(days=1): 120, MON + timedelta(days=2): 245},
        daily_goal=240,
        by_group=[("Thesis", "normal", 300), ("Grant", "high", 0)],
        chain=2, consistency="Start time: usually 09:10 · on time 2 of the last 5 days",
        last_answer="start before checking email",
        top_deep=[("github.com", 310), ("Code", 180), ("overleaf.com", 80), ("arxiv.org", 20)],
    )
    text = review_text(facts)
    assert "This week: 10h 15m of deep work." in text
    assert "reached on 2 of 3 workdays" in text
    assert "No deep work on high-priority Grant" in text
    assert "“start before checking email”" in text
    assert "Most deep hours: github.com 5h 10m · Code 3h 00m · overleaf.com 1h 20m" in text
