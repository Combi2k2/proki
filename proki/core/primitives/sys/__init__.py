"""Primitives from this computer's clock, at each cycle's time. Their base.py holds what they share."""

from proki.core.primitives.sys.clock import Clock
from proki.core.primitives.sys.time import Time
from proki.core.primitives.sys.weekday import Weekday

__all__ = ["Clock", "Time", "Weekday"]
