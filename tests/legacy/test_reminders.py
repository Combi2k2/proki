import random
from datetime import date, datetime, time, timedelta

from proki.legacy.core.reminders import RoutineReminders, done_today, routine_slots, started_share

DAY_STARTS = time(4)
TODAY = date(2026, 10, 5)


def at(days_ago: int, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(TODAY - timedelta(days=days_ago), time(hour, minute)).astimezone()


def history():
    rows = []
    for d, (h, m) in enumerate([(12, 20), (12, 40), (12, 30), (13, 0), (12, 10)], start=1):
        rows.append((at(d, h, m), at(d, h, m) + timedelta(minutes=40), "meal"))  # lunch
    for d in (1, 2, 4):
        rows.append((at(d, 19), at(d, 19, 45), "meal"))  # dinner, 3 days
    rows.append((at(2, 7, 30), at(2, 8), "meal"))  # one breakfast: not a routine yet
    rows.append((at(1, 18), at(1, 19), "workout"))  # once: not a routine
    rows.append((at(1, 23), at(1, 23) + timedelta(hours=8), "sleep"))
    return rows


def test_usual_times_per_activity_with_several_per_day():
    slots = routine_slots(history(), DAY_STARTS)
    assert [(s.activity, s.peak) for s in slots] == [("meal", time(12, 30)), ("meal", time(19, 0))]


def test_chance_is_the_share_of_days_already_started_by_now():
    lunch = routine_slots(history(), DAY_STARTS)[0]
    assert started_share(lunch, at(0, 11), DAY_STARTS) == 0
    assert started_share(lunch, at(0, 12, 30), DAY_STARTS) == 0.6  # 12:10, 12:20, 12:30 of 5
    assert started_share(lunch, at(0, 13, 30), DAY_STARTS) == 1


def test_done_today_by_a_matching_or_unlabelled_absence():
    lunch = routine_slots(history(), DAY_STARTS)[0]
    assert done_today(lunch, [(at(0, 12, 15), at(0, 12, 50), None)], DAY_STARTS)
    assert not done_today(lunch, [(at(0, 12, 15), at(0, 12, 50), "workout")], DAY_STARTS)
    assert not done_today(lunch, [(at(0, 9), at(0, 9, 40), None)], DAY_STARTS)  # outside the window
    assert not done_today(lunch, [(at(0, 12, 15), at(0, 12, 20), None)], DAY_STARTS)  # too short


def test_reminders_are_sampled_every_15_minutes_and_settled_for_the_day():
    slots = routine_slots(history(), DAY_STARTS)
    reminders = RoutineReminders(rng=random.Random(1))
    assert reminders.step(at(0, 11), slots, [], DAY_STARTS) is None  # before any past lunch
    assert reminders.step(at(0, 11, 5), slots, [], DAY_STARTS) is None  # 5 min later: not checked again yet
    slot = None
    for minutes in range(0, 120, 15):  # after every past lunch had started: 92% per check
        slot = slot or reminders.step(at(0, 13, 30) + timedelta(minutes=minutes), slots, [], DAY_STARTS)
    assert slot.peak == time(12, 30)
    reminders.settle(slot, at(0, 13, 30), DAY_STARTS)
    assert reminders.step(at(0, 14, 0), slots, [], DAY_STARTS) is None


def test_reminder_chance_is_soft_around_half_the_days():
    from proki.legacy.core.reminders import ReminderParams
    from proki.legacy.rules.reminder import ReminderRule, SlotNow

    lunch = routine_slots(history(), DAY_STARTS)[0]
    rule = ReminderRule(ReminderParams())
    chance = lambda h, m=0: round(rule.chance(SlotNow(lunch, at(0, h, m), DAY_STARTS)), 2)
    assert chance(11) == 0  # before any past lunch
    assert chance(12, 30) == 0.62 and chance(13, 30) == 0.92
