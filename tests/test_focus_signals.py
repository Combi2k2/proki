from datetime import datetime, timedelta, timezone

import pytest

from proki.services.activitywatch import Event, Record
from proki.core.signals import Depth, Primitive, Sector, Stream
from proki.compiler import compile_config

T0 = datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
KINDS = {"Code": "ide", "Google Chrome": "video_streaming", "Slack": "team_chat"}
DEPTH = {"ide": 1.0, "video_streaming": 0.0, "team_chat": 0.25}


def at(minutes):
    return T0 + timedelta(minutes=minutes)


def window(a, b, app):
    return Event(at(a), at(b), {"app": app, "title": ""})


def typing(a, b, presses):
    """Input events every 5 s from minute a to b, `presses` down + up each."""
    n = round((b - a) * 12)
    return [Event(at(a + i / 12), at(a + (i + 1) / 12), {"presses": presses, "clicks": 0}) for i in range(n)]


# 6 minutes coding with steady typing, then 4 minutes hopping between YouTube and Slack
# every 30 s, with only a click now and then
RECORDED = {
    "currentwindow": [window(0, 6, "Code")]
                     + [window(6 + i / 2, 6.5 + i / 2, "Google Chrome" if i % 2 == 0 else "Slack") for i in range(8)],
    "os.hid.input": typing(0, 6, 8)
                    + [Event(at(m), at(m + 1 / 12), {"presses": 0, "clicks": 1 if round(m * 12) % 6 == 0 else 0})
                       for m in [6 + i / 12 for i in range(48)]],
}


def run_to(minutes):
    return Primitive.run(at(minutes), Record.of(at(0), at(minutes), RECORDED))


@pytest.fixture
def signals():
    Sector.classify = lambda app, title: KINDS.get(app)
    Depth.depth_of = lambda app, title: DEPTH.get(KINDS.get(app, ""))
    signals = compile_config().streams
    out = {s.name: s for s in signals}
    Stream.now = at(0)
    return out


def test_coding_with_steady_typing_is_focus(signals):
    run_to(6)
    assert signals["deep_share"].current() == 1
    assert signals["switches"].current() == 0
    assert signals["engaged"].current() == 1
    assert signals["focus"].current() == pytest.approx(1)


def test_hopping_between_video_and_chat_is_not(signals):
    run_to(10)
    assert signals["deep_share"].current() == pytest.approx(0.125)  # video (0) and chat (0.25), nothing deep
    assert signals["switches"].current() == 4  # a switch every 30 s
    assert signals["engaged"].current() == 1  # a click now and then: at the computer
    assert signals["focus"].current() < 0.1  # low all the same: nothing deep, and hopping


def test_it_drops_as_the_hopping_starts(signals):
    run_to(7)  # one minute of hopping in the 2-minute window
    assert signals["deep_share"].current() == pytest.approx((6 * 1 + 3 * 0 + 3 * 0.25) / 12)  # a minute each
    assert 0 < signals["focus"].current() < 0.5
