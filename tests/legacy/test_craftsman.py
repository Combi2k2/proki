import random
from datetime import datetime, timedelta, timezone

from proki.legacy.core.craftsman import SiteWeek, WorthAsking, pick, site_weeks
from proki.core.events import Category, Segment

T0 = datetime(2026, 9, 28, 9, tzinfo=timezone.utc)


def seg(start_h, hours, domain):
    start = T0 + timedelta(hours=start_h)
    return Segment(start, start + timedelta(hours=hours), "Chrome", url=f"https://{domain}/", category=Category.DEEP)


def test_unserved_time_is_sites_that_serve_no_goal_and_gave_no_tasks():
    segments = [seg(0, 2, "github.com"), seg(3, 3, "facebook.com"), seg(7, 1, "mail.google.com")]
    sites = site_weeks(segments, {"github.com": {7}}, notes=[("mail.google.com", True), ("facebook.com", False)])
    assert sites["github.com"].serves == {7} and sites["github.com"].unserved == 0
    assert sites["facebook.com"].unserved == 180
    assert sites["mail.google.com"].unserved == 0  # a note there became a task


def test_rule_is_soft_around_two_hours():
    rule = WorthAsking()
    chance = lambda minutes: round(rule.chance(SiteWeek("x", minutes)), 2)
    assert chance(120) == 0.5 and chance(60) == 0.12 and chance(180) == 0.88


def test_pick_asks_about_the_biggest_unjudged_site():
    sites = {"facebook.com": SiteWeek("facebook.com", 300), "youtube.com": SiteWeek("youtube.com", 250),
             "github.com": SiteWeek("github.com", 20)}
    rule = WorthAsking(rng=random.Random(0))
    assert pick(sites, set(), rule).key == "facebook.com"
    assert pick(sites, {"facebook.com"}, rule).key == "youtube.com"
    assert pick({"github.com": sites["github.com"]}, set(), rule) is None


def test_work_tools_are_never_asked_about():
    rule = WorthAsking(rng=random.Random(0))
    terminal = SiteWeek("Terminal", 600, category=Category.DEEP)
    facebook = SiteWeek("facebook.com", 187, category=Category.DISTRACTION)
    assert pick({"Terminal": terminal, "facebook.com": facebook}, set(), rule).key == "facebook.com"
