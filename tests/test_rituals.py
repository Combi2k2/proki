"""Programs: program files, the UI messages, the shipped config's programs, and the programs
written in code (classify, the planner)."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from conftest import built, programs_folder, replay_cycle, settle, tick, with_notes
from proki import settings
from proki.core.programs import Program
from proki.core.signals import Stream
from proki.channels import Popup
from proki.engine import Engine
from proki.programs.code.work import TaskOp, Work
from proki.tools import records
from proki.storage import SCHEMA
from proki.utils import minutes, moment
from proki.services.activitywatch import Record


class Store:
    """proki.db's tables the planner uses: the board."""

    def __init__(self, db):
        self.board = Work(db)

    def names(self):
        """The open tasks' names, in order."""
        return [task["name"] for task in self.board.tasks.current() if task["status"] == "open"]


@pytest.fixture
def store(tmp_path):
    import sqlite3
    db = sqlite3.connect(tmp_path / "proki.db")
    db.executescript(SCHEMA)
    return Store(db)


def read(bucket):
    """The notes in `bucket`, the first noted first."""
    return [note for note in Stream.registry["notes"].current() or [] if note["bucket"] == bucket]


def add(bucket, text, at=None, due=None):
    """A note in `bucket`, noted `at` (None: now), sorted at `due` (None: the next 04:00)."""
    at, notes = (at or Program.now or datetime.now(timezone.utc)).astimezone(), Stream.registry["notes"]
    four = at.replace(hour=4, minute=0, second=0, microsecond=0)
    made = {"id": max((n["id"] for n in notes.current() or []), default=0) + 1, "content": text, "bucket": bucket,
            "at": minutes(at), "due": minutes(due or (four if four > at else four + timedelta(days=1)))}
    notes.set([*(notes.current() or []), made])
    return made


def due(note):
    """When a note is sorted."""
    return moment(note["due"])


def tasks(store):
    now = datetime.now(timezone.utc)
    thesis = records.add("work.groups", now, name="Thesis", tags=["papers"])
    records.add("work.tasks", now, group=thesis, name="Write the intro", estimate=40, deadline=now + timedelta(days=1))
    records.add("work.tasks", now, group=thesis, name="Fix the figures", estimate=30, deadline=now + timedelta(days=2))


def config(tmp_path, data, files=None):
    return programs_folder(tmp_path, data, files)


# --- program files -----------------------------------------------------------------------

def test_a_program_brings_its_own_file(tmp_path):
    path = config(tmp_path, {"variables": [{"name": "x", "value": 1}]}, {"bump": {
        "rules": [{"name": "low_x", "lhs": "x", "cmp": "lt", "rhs": 3}],
        "program": {"initial": "s", "states": {"s": {
            "do": [{"add": {"name": "x", "expr": 1}}], "next": [{"when": ["low_x"], "goto": "s"}]}}}}})
    compiled = built(path)
    assert [p.name for p in compiled.programs] == ["bump"] and "low_x" in {r.name for r in compiled.rules}
    Stream.registry.clear(), Program.registry.clear()
    assert built(path, programs=[]).programs == []  # which files, by name


def test_program_files_are_checked(tmp_path):
    for spec, problem in [({"program": {"name": "p", "initial": "s", "states": {"s": {}}}}, "program: unknown name"),
                          ({"program": {"initial": "s", "states": {"s": {}}}, "inputs": []}, "unknown inputs"),
                          ({"programs": []}, "unknown programs")]:
        path = config(tmp_path, {}, {"p": spec})
        with pytest.raises(ValueError, match=problem):
            built(path)
    with pytest.raises(ValueError, match="p.json: not JSON.*line 1"):
        (path / "p.json").write_text("{")
        built(path)


def test_a_mistake_in_a_program_file_names_that_file(tmp_path):
    path = config(tmp_path, {}, {"p": {"signals": [{"name": "s", "expr": "nothing + 1"}],
                                       "program": {"initial": "a", "states": {"a": {"next": "a"}}}}})
    with pytest.raises(ValueError, match=r"signal 's': unknown name 'nothing'"):
        built(path)


# --- questions, the UI, slow calls ---------------------------------------------------------

async def test_text_questions_and_urgent_ones_while_popup_open_says_so(ui):
    from proki.programs.code.base import ask_usr, popup_open

    typed = asyncio.create_task(Popup.ask("Anything still open?"))
    picked = asyncio.create_task(ask_usr("Focus is slipping", ["Back on it"], urgent=True))
    await settle()
    text, urgent = ui.questions()
    assert text["options"] is None and set(text["show"]) == {"media"} and urgent["show"]["urgent"] is True  # a picture from the questions' pool
    assert popup_open()
    await ui.click("buy milk", text)
    assert popup_open()  # one still waits
    await ui.click("Back on it", urgent)
    assert await typed == "buy milk" and await picked == 0 and not popup_open()


def shipped(tmp_path, *names, variables=()):
    """A config with the shipped program files `names`, the clock, and stand-in variables."""
    import shutil

    path = config(tmp_path, with_notes({"inputs": [{"name": "daytime"}, {"name": "time"}, {"name": "weekday"}],
                                        "variables": [{"name": n, "value": v} for n, v in variables],
                                        "signals": [{"name": "today", "expr": "time - daytime - (daytime < 240) * 1440"}]}))
    for name in names:
        shutil.copyfile(settings.SHIPPED_DIR / f"{name}.json", path / f"{name}.json")
    return path


def local(day, hour, minute, second=0):
    return datetime(2026, 10, day, hour, minute, second).astimezone()


def runner(e):
    """`run(until)`: the engine's cycles every 10 s up to `until`, as the app runs them
    (`jump`: one cycle straight to `until`, like after a sleep)."""
    at = []

    async def run(until, step=timedelta(seconds=10), jump=False, **values):
        for name, value in values.items():
            Stream.registry[name].set(value)
        t = until if jump or not at else at[-1] + step
        while t <= until:
            await replay_cycle(e, t, rec=Record.of(t - timedelta(minutes=1), t, {}))
            at.append(t)
            t += step
    return run


async def test_bedtime_from_the_config_pokes_then_rings(tmp_path, ui):
    e = Engine(shipped(tmp_path, "bedtime", variables=[("active", True)]))
    bedtime, run = Program.registry["bedtime"], runner(e)
    await run(local(5, 21, 0))
    await run(local(5, 21, 59))
    assert not ui.questions()  # the day
    await run(local(5, 22, 0, 10))
    [poke] = ui.questions()
    assert ui.labels(poke) == ["Later", "OK", "Lock screen"]
    assert poke["context"].startswith("It's 22:00. Time to wrap up")
    await ui.click("Later")
    await run(local(5, 22, 9))
    assert len(ui.questions()) == 1  # snoozed until 22:10
    await run(local(5, 22, 11))
    assert ui.labels(ui.questions()[-1]) == ["OK", "Lock screen"]  # one snooze a night
    await ui.click("OK")  # (a question holds bedtime till it's answered, or 2 min)
    await run(local(5, 23, 59, 50), jump=True)
    await run(local(6, 0, 0, 10))  # past the hard stop
    asked = ui.questions()[-1]
    rings = lambda: [m for m in ui.sent if m.get("title") == "Past your stop time"]
    [ringing] = rings()
    assert ringing["sound"].endswith("alarm-clock.mp3") and ringing["media"].endswith("bugcat/good_night.gif")
    assert bedtime.current == "past_midnight"  # it rings until you close it
    assert asked["context"] == "Lock the screen and go to sleep?"
    await ui.click(None, asked)  # no answer: asked again
    await run(local(6, 0, 0, 20))
    await run(local(6, 0, 0, 30))
    assert ui.questions()[-1] is not asked and ui.questions()[-1]["context"] == asked["context"]
    assert len(rings()) == 2  # and it rings again
    await ui.click("Lock screen")
    await run(local(6, 0, 11), active=False)  # locked: away
    assert {"type": "lock"} in ui.sent and bedtime.current == "idle"


async def test_capture_asks_once_a_shallow_window_and_hands_the_note_to_notes(tmp_path, ui):
    e = Engine(shipped(tmp_path, "capture", "note_sorter", variables=[("session.active", False), ("shutdown_done", False), ("active", True),
                                                                ("app_name", '"Mail"'), ("app_title", '"Inbox"'), ("depth", 0.5)]))
    run = runner(e)
    await run(local(5, 10, 0))
    await run(local(5, 10, 0, 10))
    assert not ui.questions()  # not 15 seconds on it yet
    await run(local(5, 10, 0, 30))
    await run(local(5, 10, 0, 40))  # on it 15 seconds: asked at the next cycle
    [question] = ui.questions()
    assert question["context"].startswith("Anything worth noting from Mail?") and question["options"] is None
    await ui.click("reply to Sam about Friday")
    assert [n["content"] for n in read("Inbox")] == ["reply to Sam about Friday"]  # in at once, for notes to sort
    await run(local(5, 10, 0, 50))
    urgency = await asked(ui, 2)  # the note's own: how urgent, no jev
    assert urgency["context"] == "“reply to Sam about Friday”\n\nDeal with this now?" and ui.labels(urgency) == ["OK"]
    await ui.click(None)  # later
    await run(local(5, 10, 1, 0))
    assert read("Inbox")[0]["urgency"] == 0.5 and Program.registry["note_sorter"].current in ("idle", "due")  # weighed: no jev
    await run(local(5, 10, 3, 0))
    assert len(ui.questions()) == 2  # once a window
    await run(local(5, 10, 3, 10), app_title='"Sam: Friday?"')
    await run(local(5, 10, 3, 40))
    assert len(ui.questions()) == 3  # another window: asked again


async def test_the_shutdown_from_the_config(tmp_path, ui):
    e = Engine(shipped(tmp_path, "shutdown", "note_sorter", variables=[("session.active", False), ("active", True), ("focus_5m", 0.1),
                                                                 ("deep_24h", 150)]))
    shutdown, run = Program.registry["shutdown"], runner(e)
    clock = [local(5, 10, 0)]

    async def asked() -> dict:  # the cycles until shutdown's next question (each note's urgency: later)
        for _ in range(10):
            clock[0] += timedelta(seconds=10)
            await run(clock[0])
            waiting = [q for q in ui.questions() if q["id"] in ui.answers]
            for urgency in [q for q in waiting if "Deal with this now" in q["context"]]:
                urgent.append(urgency["context"])
                await ui.click(None, urgency)
            if waiting := [q for q in waiting if "Deal with this now" not in q["context"]]:
                return waiting[-1]
        raise AssertionError("nothing asked")
    urgent = []

    await run(clock[0], shutdown_requested=True)  # asked for (Monday)
    assert (await asked())["context"].startswith("Wrap up your day")
    await ui.click("email the supervisor")
    assert (await asked())["context"] == "Anything else?"
    await ui.click("book the room")
    assert (await asked())["context"] == "Anything else?"
    await ui.click(None)  # that's all
    when = await asked()
    assert when["context"].startswith("When do you want to come back and sort")
    assert ui.labels(when) == ["Now", "7:00", "7:30", "8:00", "8:30", "9:00", "9:30", "10:00", "10:30", "11:00", "11:30", "12:00"]
    await ui.click("8:00")
    summary = await asked()
    assert [n["content"] for n in read("Inbox")] == ["email the supervisor", "book the room"]  # for notes to sort
    assert [u.split("\n")[0] for u in urgent] == ["“email the supervisor”", "“book the room”"]  # each note's urgency
    assert summary["context"] == "Today: 2.5 h of deep work.\nTomorrow starts with ."
    await ui.click("OK")
    await run(clock[0] + timedelta(seconds=10)), await run(clock[0] + timedelta(seconds=20))
    assert shutdown.current == "idle" and Stream.registry["shutdown_done"].current() is True
    assert [due(n) for n in read("Inbox")] == [local(6, 8, 0)] * 2  # tomorrow at 8:00, each set by the sorter
    await run(local(6, 9, 0), jump=True)
    assert Stream.registry["shutdown_done"].current() is False  # a new day


async def test_the_morning_from_the_config(tmp_path, ui):
    e = Engine(shipped(tmp_path, "morning", variables=[("active", False), ("session.active", False),
                                                       ("session.requested", False), ("todays_work", "\"Thesis first.\"")]))
    morning, run = Program.registry["morning"], runner(e)
    await run(local(6, 3, 0))
    await run(local(6, 6, 59), jump=True)  # asleep since 03:00
    await run(local(6, 7, 0), active=True)  # picked up the laptop
    greeting = ui.questions()[-1]
    assert "Thesis first." in greeting["context"] and "60 min" in ui.labels(greeting)
    await ui.click("15 min")  # 15 minutes and a 5-minute buffer: until 07:20
    await run(local(6, 7, 1))
    assert morning.current == "routine"
    await run(local(6, 7, 5))
    await run(local(6, 7, 9), active=False)  # in the shower: away after 3 minutes
    assert morning.current == "away"
    await run(local(6, 7, 10), active=True)  # back early
    assert ui.questions()[-1]["context"] == "Finished your morning routine?"
    await ui.click("Later")  # a minute more: until 07:21
    await run(local(6, 7, 20))
    await run(local(6, 7, 21, 30))
    assert morning.current == "overdue" and ui.questions()[-1]["context"].startswith("Morning routine time is over")
    await ui.click("Start session")
    await run(local(6, 7, 22))
    assert Stream.registry["session.requested"].value is True  # the session program starts it
    assert morning.current == "done"
    await run(local(7, 6, 0), jump=True, active=False)  # a new day
    assert morning.current == "idle"


# --- classify: what the window in focus is -------------------------------------------------

def classifying(tmp_path, apps):
    """The shipped classify, on `apps`, Krita in focus."""
    from proki.programs.code.base import Live, popup_open
    from proki.programs.code.classify import Track

    window = [("app_name", '"Krita"'), ("app_title", '"untitled"'), ("tab_url", None), ("active", True)]
    return Engine(shipped(tmp_path, "classify", variables=window), programs=[Track(apps).make, lambda: Live("asking", popup_open)])


def apps():
    import sqlite3
    from proki.programs.code.classify import AppDB, Apps
    return Apps(AppDB(sqlite3.connect(":memory:")))


async def test_classify_asks_whether_to_track_an_app_then_what_it_is(tmp_path, ui):
    from proki.channels import Channels
    from proki.programs.code.classify import SHIPPED

    names = [label["name"] for label in SHIPPED["labels"]]

    async def jev(request):  # jev's worker: it's design
        design = names.index("Design")
        labels = lambda q: list(q["criteria"])
        return {"answer": {name: {"choice": labels(q)[design], "probabilities": {labels(q)[design]: 0.9, labels(q)[0]: 0.1}, "confidence": 0.9}
                           for name, q in request["questions"].items()}}

    await Channels.bus.subscribe("proki.ask.jev", jev)
    known = apps()
    run = runner(classifying(tmp_path, known))
    await run(local(5, 10, 0))
    await run(local(5, 10, 1, 0))
    assert not ui.questions()  # not a minute on it yet
    await run(local(5, 10, 1, 30))
    assert (await asked(ui, 1))["context"] == "You're using “Krita”, which I haven't track yet. Track it?"
    await ui.click("OK")
    await run(local(5, 10, 2, 20))  # tracked: jev asked, 90% sure, its label next
    sure = await asked(ui, 2)
    assert sure["context"] == "I'm pretty sure “Krita” is Design. What do you say?"
    assert ui.labels(sure) == names and ui.labels(sure)[sure["show"]["selected"]] == "Design"
    await ui.click("Design")  # jev's, picked already: OK keeps it
    await run(local(5, 10, 2, 40))
    assert known.get("Krita").confirmed and Program.registry["classify"].current == "looking"


async def test_classify_waits_while_another_question_waits(tmp_path, ui):
    run = runner(classifying(tmp_path, apps()))
    asyncio.create_task(Popup.ask("Something else?"))
    await settle()
    await run(local(5, 10, 0))
    await run(local(5, 10, 2, 0))
    assert [q["context"] for q in ui.questions()] == ["Something else?"]  # one question at a time


async def test_classify_asks_a_label_from_them_all_when_jev_gives_none(tmp_path, ui):
    known = apps()
    known.keep("Krita", datetime.now(timezone.utc), track=True)
    run = runner(classifying(tmp_path, known))
    await run(local(5, 10, 0))
    await run(local(5, 10, 1, 30))  # jev gives none
    asked_ = await asked(ui, 1)
    assert asked_["context"] == "What is “Krita”?" and ui.labels(asked_) == [label.name for label in known.known().values()]
    await ui.click("Design")
    await run(local(5, 10, 1, 50))
    assert known.get("Krita").confirmed and known.get("Krita").label == known.named("Design")
    await run(local(5, 10, 9, 0))
    assert len(ui.questions()) == 1  # yours: never asked again


@pytest.mark.parametrize("conf, says", [
    (0.5, "“Krita” looks like Design to me. Is that right?"),
    (0.2, "“Krita” might be Design, but I'm not so sure. What is it?"),
])
async def test_classify_asks_a_label_as_sure_as_jev_is_of_it(tmp_path, ui, conf, says):
    known = apps()
    known.keep("Krita", datetime.now(timezone.utc), track=True, label=known.named("Design"), source="jev", conf=conf)
    run = runner(classifying(tmp_path, known))
    await run(local(5, 10, 0))
    await run(local(5, 10, 1, 30))
    question = await asked(ui, 1)
    assert question["context"] == says and ui.labels(question)[question["show"]["selected"]] == "Design"


# --- the planner's task reminder -----------------------------------------------------------

def reminding(tmp_path, store, session=False):
    """The shipped task reminder, on the store's board and notes: `run(until)` its cycles, a minute apart."""
    e = Engine(shipped(tmp_path, "task_reminder", variables=[("session.active", session), ("session.requested", False), ("next_task", None)]),
               programs=[store.board.make])
    run = runner(e)
    return lambda until, **values: run(until, step=timedelta(minutes=1), **values)  # the first: straight to `until`


async def questions(ui, n, run, until):
    """`run` up to `until`, then the UI's question `n` (a question waits on the popup's answer)."""
    await run(until)
    return await asked(ui, n)


async def test_the_task_reminder_reminds_of_the_nearest_deadline_now_and_then(tmp_path, ui, store):
    tasks(store)  # "Write the intro" due tomorrow, "Fix the figures" the day after
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    run = reminding(tmp_path, store)
    await run(now)
    minutes = lambda m: now + timedelta(minutes=m)
    asked_ = await questions(ui, 1, run, minutes(2))  # waiting: it looks, then reminds
    assert asked_["context"].startswith("“Write the intro” (about 40 min) is due tomorrow")
    await ui.click("Done")
    await run(minutes(3))
    assert store.names() == ["Fix the figures"]

    await run(minutes(60))
    await run(minutes(181), **{"session.active": True})
    assert len(ui.questions()) == 1  # not again within 2 hours, nor in a session
    await run(minutes(185), **{"session.active": False})
    assert (await asked(ui, 2))["context"].startswith("“Fix the figures”")
    Program.stop()


async def test_a_task_put_off_again_and_again_is_asked_whats_in_the_way(tmp_path, ui, store):
    tasks(store)  # "Write the intro" due tomorrow, "Fix the figures" the day after
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    run, at = reminding(tmp_path, store), 2
    await run(now)

    async def asked_next():
        nonlocal at
        n = len(ui.questions())
        for _ in range(4):
            await run(now + timedelta(minutes=at))
            if len(ui.questions()) > n:  return ui.questions()[-1]
            at += 60
        raise AssertionError("not asked")

    turns = []
    while not (asked_ := await asked_next())["context"].startswith("You've put off"):  # a Later lowers it: the other may get its turn
        turns.append(asked_["context"].split("”")[0] + "”")
        await ui.click("Later")
    assert turns.count("“Write the intro”") == 3 and "“Fix the figures”" in turns
    assert asked_["context"].startswith("You've put off “Write the intro” (about 40 min) 3 times, and it's due")  # no reminder: a question
    assert asked_["context"].endswith(". What's in the way?")
    await ui.click("It's too big")
    await run(now + timedelta(minutes=at + 1))
    assert [n["content"] for n in read("Todo")] == [
        "Split “Write the intro”, in “Thesis”, into smaller tasks: it's more than one sitting"]  # for the planner
    assert "“Fix the figures”" in (await asked_next())["context"]  # the intro rests: the figures' turn
    Program.stop()


async def test_a_task_away_from_the_computer_is_planned_for_and_one_stuck_asks_whats_in_the_way(tmp_path, ui, store):
    from proki.core.records.field import Field

    tasks(store)  # "Write the intro" due tomorrow, "Fix the figures" the day after
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    run = reminding(tmp_path, store)
    intro, figures = (next(t["id"] for t in store.board.tasks.current() if t["name"] == name) for name in ("Write the intro", "Fix the figures"))
    board = store.board.tasks
    board.define(Field("offline", srcs=[{"from": "user"}, {"from": "expr", "expr": "False"}]))   # a field of yours, and away by it
    board.define(Field("away", srcs=[{"from": "expr", "expr": "me.offline"}]))
    board.add_row(board.get_row(intro) | {"offline": True})
    await run(now)
    asked_ = await questions(ui, 1, run, now + timedelta(minutes=2))
    assert asked_["context"] == ("“Write the intro” (about 40 min) is due tomorrow. It's done away from the computer: "
                                 "set an alarm, or block time for it?")
    await ui.click("I've planned it")
    await run(now + timedelta(minutes=3))
    assert Stream.registry["work.task"].value is None  # no session for it: it rests a day

    board.add_row(board.get_row(figures) | {"spent": 60})
    asked_ = await questions(ui, 2, run, now + timedelta(minutes=125))
    assert asked_["context"] == "You've spent 60 min on “Fix the figures” (about 30 min). What's in the way?"
    await ui.click("It just needs more time")
    await run(now + timedelta(minutes=126))
    assert [t["estimate"] for t in store.board.tasks.current() if t["id"] == figures] == [75]  # what's spent, and half its estimate more
    Program.stop()


# --- notes: a note sorted into its bucket, and the task planner: a todo into a group ------------

class SayingJev:
    """A stand-in jev: for a noul, the probability of yes by a word in what it reads (in turn,
    when there are several; no word: no answer). For a choice, the probabilities by a word in it,
    each option's by its place."""

    def __init__(self, answers, choice=None):
        self.answers = {word: list(ps) for word, ps in answers.items()}
        self.choice = choice or {}

    def ask(self, state, questions):
        return {key: answer for key, question in questions.items() if (answer := self.answer(f"{state}\n{question['instructions']}", question)) is not None}

    def answer(self, said, question):
        if question["type"] == "choice":
            ps = next((ps for w, ps in self.choice.items() if w in said), {})
            return {"probabilities": {list(question["criteria"])[i]: p for i, p in ps.items()}, "confidence": max(ps.values())} if ps else None
        word = next((w for w in self.answers if w in said), None)
        if word is None:  return None
        ps = self.answers[word]
        return {"noul": ps.pop(0) if len(ps) > 1 else ps[0]}


class BreakingLlm:
    def __init__(self):
        self.prompts = []

    def ask(self, prompt, schema=None):
        self.prompts.append(prompt)
        self.schema = schema
        return {"name": "Thesis" if "“Thesis”" in prompt else "Related work", "desc": "The thesis's related-work chapter: the field surveyed, papers first.",
                "tags": ["papers", "research"], "questions": ["Which venue is it for?"],
                "changes": [{"op": "add", "name": "List the key papers", "estimate": 30, "done_when": ["10 papers listed"]},
                            {"op": "add", "name": "Check the list", "desc": "covers the field? Plan the next tasks", "estimate": 15,
                             "after": ["List the key papers", "outline_the_chapters", "nope"], "checkpoint": True}]}


async def asked(ui, n, seconds=2.0):
    """Wait until the UI has `n` questions (the workers answer on threads)."""
    for _ in range(int(seconds / 0.01)):
        if len(ui.questions()) >= n:  return ui.questions()[n - 1]
        await asyncio.sleep(0.01)
    raise AssertionError(f"{len(ui.questions())} questions, not {n}: {[q['context'] for q in ui.questions()]}")


async def until(condition, seconds=2.0):
    for _ in range(int(seconds / 0.01)):
        if condition():  return
        await asyncio.sleep(0.01)
    raise AssertionError("not in time")


async def cycles(start, n, seconds=10):
    """`n` cycles, `seconds` apart, from `start`."""
    for i in range(n):
        await tick(start + timedelta(seconds=seconds * i))
        await settle()


async def sort_inbox_at(t):
    """Every note in the inbox so far sorted at `t`, as shutdown picks it."""
    Stream.registry["notes.sort_at"].set(t.timestamp() / 60)


def sorting(tmp_path, active=True):
    """The shipped notes program."""
    return Engine(shipped(tmp_path, "note_sorter", variables=[("active", active)]))


async def test_the_inbox_is_sorted_at_the_time_shutdown_chose(tmp_path, ui):
    from proki.channels import Channels, jev

    await jev.serve(Channels.bus, SayingJev({}, choice={"note": {0: 0.2, 1: 0.75, 2: 0.05}}))
    run = runner(sorting(tmp_path))
    await run(local(5, 21, 0))
    add("Inbox", "a focus timer that learns my rhythm")
    add("Inbox", "call the bank\nabout the card")  # at once: both in
    assert [n["content"] for n in read("Inbox")] == ["a focus timer that learns my rhythm", "call the bank\nabout the card"]
    for i in (1, 2):  # how urgent each is: later
        await run(local(5, 21, 0, 10 * i))
        await asked(ui, i)
        await ui.click(None, ui.questions()[i - 1])
    await run(local(5, 21, 0, 30))
    assert [(n["guess"], n["conf"], n["urgency"]) for n in read("Inbox")] == [("Idea", 0.75, 0.5)] * 2  # guessed as they were noted
    await sort_inbox_at(local(5, 22, 0))  # shutdown's
    for i in (4, 5, 6):  # set on each, one a cycle
        await run(local(5, 21, 0) + timedelta(seconds=10 * i))
    await run(local(5, 21, 59, 50), jump=True)
    assert len(ui.questions()) == 2  # not their time yet

    await run(local(5, 22, 0, 10))  # jev's bucket, guessed as it was noted, an idea 75% sure
    question = await asked(ui, 3)
    assert question["context"] == "“a focus timer that learns my rhythm”\n\nI'm pretty sure this goes under Idea. Right?"
    assert ui.labels(question) == ["Todo", "Idea", "Thought"] and question["show"]["selected"] == 1
    await ui.click("Idea")
    await run(local(5, 22, 0, 40))
    [idea] = read("Idea")
    assert idea["content"] == "a focus timer that learns my rhythm"  # as it was noted

    question = await asked(ui, 4)  # the next one
    assert question["context"].startswith("“call the bank\nabout the card”")  # as it was noted
    await ui.click("Todo")
    await run(local(5, 22, 1, 10))
    assert read("Inbox") == [] and len(read("Todo")) == 1  # all sorted


async def test_a_note_is_sorted_at_four_unless_shutdown_says_when(tmp_path, ui):
    run = runner(sorting(tmp_path, active=False))
    await run(local(5, 21, 0))
    assert moment(Stream.registry["notes.next_due"].current()) == local(6, 4, 0)  # a new note's: the next 04:00
    add("Inbox", "call mom"), add("Inbox", "buy a gift"), add("Idea", "a desk")
    await sort_inbox_at(local(6, 8, 0))  # shutdown's
    for i in range(1, 5):
        await run(local(5, 21, 0, 10 * i))
    assert [due(n) for n in read("Inbox")] == [local(6, 8, 0)] * 2 and Stream.registry["notes.sort_at"].current() is None
    assert due(read("Idea")[0]) == local(6, 4, 0)  # not in the inbox: its own
    await run(local(6, 2, 0), jump=True)
    assert moment(Stream.registry["notes.next_due"].current()) == local(6, 4, 0)  # past midnight: that night's


async def test_the_inbox_waits_while_youre_away(tmp_path, ui):
    run = runner(sorting(tmp_path, active=False))
    await run(local(5, 10, 0))
    add("Inbox", "buy a gift")
    await run(local(5, 10, 0, 10))
    await asked(ui, 1)
    await ui.click(None)  # how urgent: later
    await sort_inbox_at(local(5, 10, 0))  # its time: now
    await run(local(5, 10, 1, 0))
    assert len(ui.questions()) == 1  # away
    await run(local(5, 10, 1, 10), active=True)
    await run(local(5, 10, 1, 30))
    assert (await asked(ui, 2))["context"].startswith("“buy a gift”\n\nIs this a todo, an idea")


async def test_a_note_to_deal_with_now_is_sorted_then_one_for_later_waits(tmp_path, ui):
    from proki.channels import Channels, jev

    await jev.serve(Channels.bus, SayingJev({"right away": [0.9, 0.1]}))  # urgent, then not
    run = runner(sorting(tmp_path))
    await run(local(5, 10, 0))
    add("Inbox", "renew the visa, it expires Friday")
    await run(local(5, 10, 0, 10))
    urgency = await asked(ui, 1)
    assert urgency["context"] == "“renew the visa, it expires Friday”\n\nThis sounds urgent. Deal with it now?"
    await ui.click("OK")
    question = await asked(ui, 2)  # its bucket, at once: no cycle waited for. No bucket from jev
    assert question["context"].startswith("“renew the visa, it expires Friday”\n\nIs this a todo, an idea")
    await ui.click(None)  # later: this note, in 2 hours
    await run(local(5, 10, 0, 30))
    assert due(read("Inbox")[0]) > local(5, 11, 59)

    add("Inbox", "try a standing desk")
    await run(local(5, 10, 0, 50))
    assert (await asked(ui, 3))["context"].endswith("This can probably wait. Deal with it now anyway?")
    await ui.click(None)  # later: with the others, 04:00
    await run(local(5, 10, 1, 20))
    assert len(ui.questions()) == 3 and [n["content"] for n in read("Inbox")] == ["renew the visa, it expires Friday", "try a standing desk"]
    assert due(read("Inbox")[1]) == local(6, 4, 0)


@pytest.mark.parametrize("ps, says", [
    ({0: 0.25, 1: 0.5,  2: 0.25}, "This looks like it goes under Idea. Is that right?"),
    ({0: 0.3,  1: 0.38, 2: 0.32}, "I'd put this under Idea, but I'm not sure. Where does it go?"),
])
async def test_a_note_is_asked_as_sure_as_jev_is_of_its_bucket(tmp_path, ui, ps, says):
    from proki.channels import Channels, jev

    await jev.serve(Channels.bus, SayingJev({"right away": [0.9]}, choice={"desk": ps}))
    run = runner(sorting(tmp_path))
    await run(local(5, 10, 0))
    add("Inbox", "a standing desk")
    await run(local(5, 10, 0, 10))
    await asked(ui, 1)
    await ui.click("OK")  # now: its bucket, at once
    question = await asked(ui, 2)
    assert question["context"] == f"“a standing desk”\n\n{says}" and question["show"]["selected"] == 1


def planning(tmp_path, store):
    """The shipped task planner, on the store's board and notes: `go(until)` runs its cycles,
    10 s apart, until `until()` holds."""
    e = Engine(shipped(tmp_path, "task_planner"), programs=[store.board.make])
    run, at = runner(e), [datetime.now(timezone.utc)]

    async def go(until=None, cycles=40):
        for _ in range(cycles):
            at[0] += timedelta(seconds=10)
            await run(at[0])
            await settle()
            if until and until():  return
            await asyncio.sleep(0.01)
        if until:  raise AssertionError("not in time")
    return go


async def test_a_todo_is_talked_through_and_planned_into_a_new_group(tmp_path, ui, store):
    from proki.channels import Channels, jev, llm

    await jev.serve(Channels.bus, SayingJev({"clear": [0.1, 0.2, 0.9]}, choice={"life": {8: 0.7, 3: 0.2, 6: 0.05}}))
    await llm.serve(Channels.bus, breaking := BreakingLlm())
    go = planning(tmp_path, store)
    add("Todo", "Write the related-work section", datetime.now(timezone.utc))
    await go(lambda: ui.questions())  # no groups yet: a new one, not asked

    assert (await asked(ui, 1))["context"].endswith("What do you need to do, exactly?")
    await ui.click("cover the 10 key papers on attention")
    await go(lambda: len(ui.questions()) == 2)
    assert (await asked(ui, 2))["context"].endswith("What would “done” look like?")  # jev: not clear yet
    await ui.click("a 3-page draft")
    await go(lambda: len(store.board.ops.read()) == 2)  # jev: clear. The LLM's next tasks, a cycle each
    assert "a new group." in breaking.prompts[0] and "a 3-page draft" in breaking.prompts[0]
    asked_in = breaking.schema["properties"]  # the plan's type: not its group, nor a change's id or key
    assert "group" not in asked_in and {"id", "key"}.isdisjoint(asked_in["changes"]["items"]["properties"]) and asked_in["tags"]["maxItems"] == 3

    board = store.board
    [group] = board.groups.current()
    assert (group["name"], group["tags"], group["questions"]) == ("Related work", ["papers", "research"], ["Which venue is it for?"])
    assert group["desc"] == "The thesis's related-work chapter: the field surveyed, papers first."  # the LLM's, not the note
    first, check = sorted(board.ops.read(), key=lambda op: op.id)
    assert board.tasks.current() == [] and (first.op, first.group) == ("add", group["id"])  # suggested, for you to accept
    assert first.fields == {"name": "List the key papers", "estimate": 30, "done_when": ["10 papers listed"], "key": "list_the_key_papers"}
    assert (check.after, check.fields["checkpoint"]) == (["list_the_key_papers"], True)  # unknown keys left out
    await go(lambda: ui.sent and ui.sent[-1].get("type") == "open")
    assert ui.sent[-1] == {"type": "open", "path": f"tasks/{group['id']}"}  # its card, to edit
    assert read("Todo") == []  # taken
    Program.stop()


async def test_a_todo_for_a_group_you_have_is_planned_with_it(tmp_path, ui, store):
    from proki.channels import Channels, jev, llm

    now = datetime.now(timezone.utc)
    thesis = records.add("work.groups", now, name="Thesis", desc="my master's thesis", tags=["papers"])
    outline = records.add("work.tasks", now, group=thesis, name="Outline the chapters")
    records.change("work.tasks", outline, now, status="done")
    await jev.serve(Channels.bus, SayingJev({"clear": [0.9]}, choice={"groups": {0: 0.1, 1: 0.85}}))
    await llm.serve(Channels.bus, breaking := BreakingLlm())
    go = planning(tmp_path, store)
    add("Todo", "the related-work section", now)
    await go(lambda: ui.questions())

    question = await asked(ui, 1)
    assert question["context"] == "“the related-work section”\n\nDoes this go with tasks you already have?"
    assert [o[0] for o in question["options"]] == ["A new group", "Thesis"] and question["show"]["selected"] == 1  # jev's
    await ui.click("Thesis")
    await go(lambda: len(store.board.ops.read()) == 2)  # clear: nothing more asked
    assert len(ui.questions()) == 1
    assert "group of tasks “Thesis”: my master's thesis" in breaking.prompts[0] and "- [x] outline_the_chapters: Outline the chapters" in breaking.prompts[0]
    assert "(tags: papers)" in breaking.prompts[0]

    board = store.board
    assert [p["name"] for p in board.groups.current()] == ["Thesis"] and board.groups.current()[0]["questions"] == ["Which venue is it for?"]
    assert board.groups.current()[0]["desc"] == "The thesis's related-work chapter: the field surveyed, papers first."  # refined
    assert board.groups.current()[0]["tags"] == ["papers", "research"]
    first, check = sorted(board.ops.read(), key=lambda op: op.id)
    assert (first.group, check.after) == (thesis, ["list_the_key_papers", "outline_the_chapters"])  # a new one, and the one it had
    Program.stop()


async def test_a_todo_its_group_covers_already_is_said_so_and_taken(tmp_path, ui, store):
    from proki.channels import Channels, llm

    now = datetime.now(timezone.utc)
    groceries = records.add("work.groups", now, name="Groceries")
    records.add("work.tasks", now, group=groceries, name="Buy milk")
    go = planning(tmp_path, store)
    add("Todo", "milk", now)
    answer = {"name": "", "desc": "", "tags": [], "questions": [], "changes": []}
    await llm.serve(Channels.bus, type("Saying", (), {"ask": lambda self, prompt, schema=None: answer})())
    await go(lambda: ui.questions())
    await ui.click("Groceries")  # no jev: clear enough

    await go(lambda: any(sent.get("type") == "poke" for sent in ui.sent))
    assert next(sent for sent in ui.sent if sent.get("type") == "poke")["text"] == "Nothing to add: “Groceries” already covers “milk”."
    assert read("Todo") == [] and store.board.ops.read() == []  # taken
    Program.stop()


async def test_a_plan_left_to_review_is_reviewed_before_another_is_made(tmp_path, ui, store):
    from proki.channels import Channels, jev, llm
    from proki.storage import StateDB

    now = datetime.now(timezone.utc)
    thesis = records.add("work.groups", now, name="Thesis", desc="my master's thesis")
    waiting = store.board.ops.create(TaskOp(None, group=thesis, op="add", fields={"name": "Outline the chapters"}))
    StateDB(store.board.db).set("work_plan", {"name": "Thesis"})  # the plan, its change still on the card
    await jev.serve(Channels.bus, SayingJev({"clear": [0.9]}, choice={"groups": {0: 0.1, 1: 0.85}}))
    await llm.serve(Channels.bus, breaking := BreakingLlm())
    go = planning(tmp_path, store)
    add("Todo", "the related-work section", now)
    await go(lambda: ui.questions())

    review = await asked(ui, 1)
    assert review["context"].endswith("“Thesis” still has 1 planned change. Review it first? It won't take long.")
    await ui.click("OK")
    await go(lambda: ui.sent and ui.sent[-1] == {"type": "open", "path": f"tasks/{thesis}"})
    await go(cycles=3)
    assert breaking.prompts == [] and len(ui.questions()) == 1  # not planned again while it waits

    store.board.ops.delete(waiting)  # reviewed
    await go(lambda: len(ui.questions()) == 2)
    await ui.click("Thesis")
    await go(lambda: len(store.board.ops.read()) == 2)  # planned again
    assert "Outline the chapters" not in breaking.prompts[0]
    Program.stop()


async def test_the_reminder_counts_whats_open_and_suggests_a_task(tmp_path, ui, store):
    from proki.programs.code.base import find_variable

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    run = reminding(tmp_path, store, session=True)  # no reminder
    await run(now)
    assert find_variable("next_task").value == "a clean slate: no tasks yet"
    tasks(store)
    await run(now + timedelta(minutes=2))
    assert find_variable("tasks_open").value == 2 and find_variable("next_task").value == "“Write the intro” (about 40 min)"
    Program.stop()


async def test_notes_are_a_list_a_program_appends_to_and_removes_from(tmp_path):
    from proki.core.actions import Append, Remove
    from proki.core.signals import Expr

    built(shipped(tmp_path / "programs", "note_sorter", variables=[("active", True)]))
    value = lambda expr: Expr(expr).value()
    add("Inbox", "buy milk"), add("Idea", "a desk")
    await Append(name="notes", expr={"id": "notes.next_id", "content": "'plan the trip'", "bucket": "'Todo'"}).apply()
    assert value("notes.todos.content") == ["plan the trip"] and value("notes.todos[0].id") == 3  # where it says, its id the next
    await Remove(name="notes", id="notes.todos[0].id").apply()
    assert [n["content"] for n in Stream.registry["notes"].current()] == ["buy milk", "a desk"]  # that one gone, the rest kept
