"""Routine reminder rule: the share of past days already started by now (core/reminders.py)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, time
from typing import TYPE_CHECKING

from proki.legacy.rules.base import Rule, RuleParams

if TYPE_CHECKING:
    from proki.legacy.core.reminders import ReminderParams, Slot


@dataclass(frozen=True)
class SlotNow:
    slot: "Slot"
    now: datetime
    day_starts: time


class ReminderRule(Rule[SlotNow]):
    def __init__(self, params: "ReminderParams", rng: random.Random | None = None):
        super().__init__(RuleParams(threshold=params.threshold, softness=params.softness, range=(1e-9, None)), rng)

    def measure(self, c: SlotNow) -> float:
        from proki.legacy.core.reminders import started_share

        return started_share(c.slot, c.now, c.day_starts)

    @staticmethod
    def context(slot: "Slot", now: datetime, day_starts: time) -> SlotNow:
        return SlotNow(slot, now, day_starts)
