from datetime import date, datetime, timedelta, timezone

import requests

from proki.legacy.core.backlog import (
    Assessment, Group, Task, breakdown_reason, due_text, estimate_mismatch, next_task, pick_group, urgency, workable,
)
from proki.legacy.core.jev import assess_task, suggest_group
from proki.services.jev import Jev
from proki.legacy.metrics.quota import QuotaParams, next_base, today_quota
from proki.legacy.core.store import Store

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 9, 29)


def task(id, estimate=30, deadline=None, group=1, parent=None, status="open", position=0):
    return Task(id, group, parent, f"t{id}", "", deadline, estimate, None, status, position or id)


# --- atomic or not ---------------------------------------------------------------------

def test_breakdown_reason():
    clear = Assessment("deep", 40, 0.9)
    assert breakdown_reason(30, clear) is None
    assert breakdown_reason(50, clear) is None  # exactly one session is fine
    assert breakdown_reason(90, clear) == "too_long"  # the user's estimate decides length
    assert breakdown_reason(30, Assessment("deep", 40, 0.2)) == "vague"
    assert breakdown_reason(30, Assessment("deep", None, 0.9)) == "vague"  # openjev can't size it
    assert breakdown_reason(30, None) is None  # no openjev: trust the user


def test_estimate_mismatch_both_ways():
    assert estimate_mismatch(30, Assessment("deep", 85, 0.9))  # openjev thinks much longer
    assert estimate_mismatch(120, Assessment("deep", 15, 0.9))  # or much shorter
    assert not estimate_mismatch(30, Assessment("deep", 40, 0.9))
    assert not estimate_mismatch(30, Assessment("deep", None, 0.9))


# --- what can be worked on, and in which order ------------------------------------------

def test_a_broken_down_task_is_worked_through_its_steps():
    tasks = [task(1, 120), task(2, parent=1), task(3, parent=1)]
    assert [t.id for t in workable(tasks)] == [2, 3]
    tasks = [task(1, 120), task(2, parent=1, status="done"), task(3, parent=1, status="done")]
    assert [t.id for t in workable(tasks)] == [1]  # all steps done: the task itself can be closed


def test_next_task_earliest_deadline_first():
    tasks = [task(1, deadline=TODAY + timedelta(days=5)), task(2, deadline=TODAY + timedelta(days=1)), task(3)]
    assert next_task(tasks, 1).id == 2


def test_urgency_is_work_left_over_time_left():
    soon = [task(1, 120, deadline=TODAY)]  # 2 h due tonight
    later = [task(2, 120, deadline=TODAY + timedelta(days=7))]
    assert urgency(soon, NOW) > urgency(later, NOW) > 0
    assert urgency([], NOW) == 0


def test_pick_group_weighs_urgency_by_priority_and_skips_excluded():
    groups = [Group(1, "exam", "normal"), Group(2, "proki", "high")]
    tasks = [task(1, 60, TODAY + timedelta(days=2), group=1), task(2, 60, TODAY + timedelta(days=3), group=2)]
    assert pick_group(groups, tasks, NOW).name == "proki"  # a bit later, but twice as important
    assert pick_group(groups, tasks, NOW, exclude={2}).name == "exam"
    assert pick_group(groups, [], NOW) is None


def test_due_text():
    assert due_text(TODAY, TODAY) == "due today"
    assert due_text(TODAY + timedelta(days=1), TODAY) == "due tomorrow"
    assert due_text(TODAY - timedelta(days=2), TODAY) == "overdue by 2 days"
    assert due_text(None, TODAY) == "no deadline"


# --- the quota --------------------------------------------------------------------------------

P = QuotaParams()


def test_today_quota_rises_past_80_percent():
    assert today_quota(240, 0, P) == 240
    assert today_quota(240, 191, P) == 240
    assert today_quota(240, 192, P) == 300  # 80% of 4 h → 5 h today
    assert today_quota(240, 240, P) == 360  # 80% of 5 h passed too → 6 h
    assert today_quota(540, 600, P) == 600  # never above 10 h


def test_base_rises_after_3_days_in_a_row():
    good = {TODAY - timedelta(days=i): 200 for i in (1, 2, 3)}
    assert next_base(240, good, TODAY, P) == 300
    one_short = dict(good) | {TODAY - timedelta(days=2): 100}
    assert next_base(240, one_short, TODAY, P) == 240
    assert next_base(600, {d: 600 for d in good}, TODAY, P) == 600


# --- openjev ----------------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_assess_task(monkeypatch):
    answers = {"kind": {"choice": "deep"}, "size": {"choice": "50_to_120"}, "specific": {"noul": 0.9}}
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse({"answers": answers}))
    assert assess_task(Jev("http://jev.test", "key"), "read chapter 3") == Assessment("deep", 85, 0.9)


def test_suggest_group_picks_an_existing_one_or_none(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(
        {"answers": {"group": {"choice": "g1", "confidence": 0.9}}}))
    assert suggest_group(Jev("http://jev.test", "key"), "fix the Safari bug", ["Statistics final", "proki"]) == "proki"
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResponse(
        {"answers": {"group": {"choice": "new", "confidence": 0.9}}}))
    assert suggest_group(Jev("http://jev.test", "key"), "book dentist", ["proki"]) is None
    assert suggest_group(Jev("http://jev.test", "key"), "anything", []) is None  # no groups yet


# --- storage ------------------------------------------------------------------------------------

def test_backlog_round_trip(tmp_path):
    store = Store(tmp_path / "db")
    g = store.add_group("proki", "high", NOW)
    assert store.add_group("proki", "low", NOW) == g  # same name, same group
    parent = store.add_task(g, "planning feature", "", TODAY, 180, NOW, assessment=Assessment("deep", 150, 0.4))
    store.add_task(g, "task form", "", TODAY, 40, NOW, parent_id=parent)
    tasks = store.tasks()
    assert [(t.title, t.parent_id, t.kind) for t in tasks] == [("planning feature", None, "deep"), ("task form", parent, None)]
    store.update_task(parent, estimate=200, deadline=TODAY + timedelta(days=1))
    assert store.tasks()[0].estimate == 200
    store.set_task_status(tasks[1].id, "done", NOW)
    assert len(store.tasks()) == 1 and store.tasks_done_between(NOW - timedelta(hours=1), NOW + timedelta(hours=1)) == 1
    assert store.groups() == [Group(g, "proki", "high")]


def test_state_values(tmp_path):
    store = Store(tmp_path / "db")
    assert store.get_state("quota_base") is None
    store.set_state("quota_base", "300")
    assert store.get_state("quota_base") == "300"
