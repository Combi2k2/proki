"""@notes: what you note down, sorted into its bucket, asking you to confirm.

A note comes in through the global variable `note`, as a text: capture's question,
shutdown's "what's still open?", the UI's "New note…". `note` is an `Inlet`, made here
before the config is built: what's written to it goes into the inbox at once. Then, on its
own, how urgent it is: jev guesses, and you say to deal with it now (OK) or later
(`Inlet.weigh`).

A note in the inbox is sorted at its time (`due`), the oldest first, once you're at the
computer and no question is open:

    now         you said to deal with it now
    shutdown's  the time you chose there (`notes_sort_at`), if it's after the note was noted
    04:00       else the first after it was noted (`SORT_AT`): a day without a shutdown is
                sorted the next morning

The buckets are labels, each with what it means (`BUCKETS`): to jev, and to you as you hover
it. A note is of its bucket's kind (`KINDS`): an `UnsortedNote` in the inbox, then a
`TodoNote`, an `IdeaNote` or a `ThoughtNote`. Each bucket is a queue in proki's key store
(`Notes`): a program downstream reads its own, and removes a note once it's done with it.
"Todo" is the task planner's.

    idle        the inbox's oldest note due, you there, no question open (`Look`)
    sorting     jev's bucket for the note, once: which question to ask, by how sure jev
                is of it (`Sort`)
    noidea      no bucket from jev: which is it? (`ConfirmNoIdea`)
    unsure      jev's bucket, jev under 40% sure (`ConfirmUnsure`)
    maybe       jev's bucket, jev 40 to 70% sure (`ConfirmMaybe`)
    sure        jev's bucket, jev 70% sure or more (`ConfirmSure`)

The bucket is chosen from them all (to confirm jev's: it's picked already, OK keeps it). A
long note is quoted by its start (`SHORT`). No answer ("Later") asks about that note again in
`LATER`. Only the note's text is sent to jev.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta

from proki.channels import Popup, jev
from proki.core.programs import Program, State
from proki.core.signals import Stream, Variable
from proki.programs.code.base import Ritual, Step, make_branch, make_variable, popup_open
from proki.storage import StateDB

LATER   = timedelta(hours=2)   # "Later"
TIMEOUT = 300                  # how long a question waits for you, in seconds
SHORT   = 120                  # characters of a note, quoted in a question
SORT_AT = 4 * 60               # minutes into the day: a note's time, when shutdown chose none after it
URGENT  = [                    # jev's chance a note is urgent, at least, and what you're asked
    (0.7, "This sounds urgent. Deal with it now?"),
    (0.3, "Deal with this now, or leave it for later?"),   # jev's no guess too
    (0.0, "This can probably wait. Deal with it now anyway?"),
]

INBOX   = "Inbox"              # the notes not sorted yet
BUCKETS = [                    # each bucket, and what it means (`TODO`: the planner's)
    ("Todo",           "Something the person needs to do: a task"),
    ("Idea",           "An idea worth keeping: something to build, try or explore later"),
    ("Random thought", "Just a thought, noted down to let it go: nothing to do, nor to keep"),
]
NAMES   = [name for name, _ in BUCKETS]
TODO    = NAMES[0]


# --- notes ------------------------------------------------------------------------------------

@dataclass
class Note:
    """What you noted down, as noted."""

    id    : str
    text  : str
    at    : str                   # when it was noted, as ISO text


@dataclass
class UnsortedNote(Note):
    """In the inbox, to sort."""

    due   : str | None   = None   # when to sort it, as ISO text (None: with the others, `due`)
    guess : str | None   = None   # jev's bucket
    conf  : float | None = None   # how likely jev found it


@dataclass
class TodoNote(Note):
    """For the task planner to take."""


@dataclass
class IdeaNote(Note):
    """Kept, in the Notes view."""


@dataclass
class ThoughtNote(Note):
    """Kept, in the Notes view: noted down to let it go."""


KINDS = {INBOX: UnsortedNote, "Todo": TodoNote, "Idea": IdeaNote, "Random thought": ThoughtNote}   # by bucket


class Notes:
    """The buckets, in the key store ("notes": {bucket: [note, ...]}), each in the order noted.

        read(bucket)                    its notes, of its kind
        add(bucket, text, at, **more)   a new one, last: the note (`more`: its kind's fields)
        change(bucket, id, **fields)    some of its fields
        remove(bucket, id)              out of the bucket: the note (None: not there)
        move(id, start, to)             into the end of bucket `to`, of its kind
    """

    KEY = "notes"

    def __init__(self, kv: StateDB):
        self.kv = kv

    def read(self, bucket: str) -> list[Note]:
        """Fields of another kind are left out: a note kept before kinds had the inbox's
        everywhere."""
        kind  = KINDS.get(bucket, Note)
        names = {f.name for f in fields(kind)}
        return [kind(**{k: v for k, v in note.items() if k in names}) for note in self.kv.get(self.KEY, {}).get(bucket, [])]

    def add(self, bucket: str, text: str, at: datetime, **more) -> Note:
        if bucket not in KINDS:  raise ValueError(f"no bucket {bucket!r}")
        note = KINDS[bucket](uuid.uuid4().hex[:8], text, at.astimezone(UTC).isoformat(), **more)
        self.keep(bucket, [*self.read(bucket), note])
        return note

    def change(self, bucket: str, id: str, **changed) -> None:
        self.keep(bucket, [type(note)(**asdict(note) | changed) if note.id == id else note for note in self.read(bucket)])

    def remove(self, bucket: str, id: str) -> Note | None:
        notes = self.read(bucket)
        found = next((note for note in notes if note.id == id), None)
        self.keep(bucket, [note for note in notes if note.id != id])
        return found

    def move(self, id: str, start: str, to: str) -> None:
        """As it was noted: what its kind in `start` had more is left behind."""
        if note := self.remove(start, id):  self.keep(to, [*self.read(to), KINDS[to](note.id, note.text, note.at)])

    def keep(self, bucket: str, notes: list[Note]) -> None:
        """The bucket, as `notes`."""
        if bucket not in KINDS:  raise ValueError(f"no bucket {bucket!r}")
        self.kv.set(self.KEY, self.kv.get(self.KEY, {}) | {bucket: [asdict(note) for note in notes]})


def due(note: UnsortedNote) -> datetime:
    """When the note is sorted: its own time, else the one you chose in shutdown if it's after
    the note was noted, else the first 04:00 (`SORT_AT`) after it was."""
    if note.due:  return datetime.fromisoformat(note.due)

    at     = datetime.fromisoformat(note.at)
    chosen = getattr(Stream.registry.get("notes_sort_at"), "value", None)   # minutes since 1970 (0 or None: none)
    if isinstance(chosen, int | float) and (then := datetime.fromtimestamp(chosen * 60, UTC)) >= at:  return then

    local = at.astimezone()
    start = local.replace(hour=SORT_AT // 60, minute=SORT_AT % 60, second=0, microsecond=0)
    return start if start > local else start + timedelta(days=1)


def quoted(text: str) -> str:
    """A note as a question quotes it: its first line, its start if it's long."""
    line = text.strip().splitlines()[0]
    return f"“{line[:SHORT].rstrip()}…”" if len(line) > SHORT or "\n" in text.strip() else f"“{line}”"


class Inlet(Variable):
    """The global variable `note`: each note written to it, a text, goes into the inbox at once,
    so none waits for a program to look, nor is missed while a question waits. Then how urgent
    it is is asked, on its own (`weigh`). Without `notes`, it's only a variable."""

    def __init__(self, notes: Notes | None = None):
        super().__init__("note", None, desc="a note any program writes: into the inbox at once, for @notes to sort", persist=False)
        self.notes   = notes
        self.weighed : set[asyncio.Task] = set()   # the questions asked, kept until answered

    def set(self, value) -> None:
        super().set(value)
        if not self.notes or not isinstance(value, str) or not value.strip():  return

        note = self.notes.add(INBOX, value.strip(), Program.now or datetime.now(UTC))
        try:
            task = asyncio.get_running_loop().create_task(self.weigh(note))
        except RuntimeError:  # no loop: not asked, so sorted with the others
            return
        self.weighed.add(task)
        task.add_done_callback(self.weighed.discard)

    async def weigh(self, note: UnsortedNote) -> None:
        """How urgent the note is: jev's chance, worded by `URGENT`, for you to say. OK: now, so
        it's due; Later, or no answer: with the others."""
        answers = await jev.ask(f"A note someone wrote: {note.text}", {"urgent": {
            "type": "noul", "instructions": "Does this need dealing with right away, today?"}})
        chance  = ((answers or {}).get("urgent") or {}).get("noul")
        says    = next(says for least, says in URGENT if (0.5 if chance is None else chance) >= least)
        if await Popup.ask(f"{quoted(note.text)}\n\n{says}", ["Now"], TIMEOUT) == 0:
            self.notes.change(INBOX, note.id, due=datetime.now(UTC).isoformat())


# --- the program ------------------------------------------------------------------------------

class Look(Step):
    """The inbox's oldest note due: while you're at the computer, and no question is open."""

    program: NoteKeeper

    @staticmethod
    def away() -> bool:
        """Whether you're away (no `active`: you're taken to be there)."""
        return "active" in Stream.registry and not Stream.registry["active"].current()

    async def apply(self) -> None:
        p = self.program
        p.state = None

        if popup_open():  return
        if self.away():   return

        if note := next((n for n in p.notes.read(INBOX) if due(n) <= Program.now), None):
            p.note, p.state = note, "sorting"


class Sort(Step):
    """jev's bucket for the note, once, and which question to ask by how sure jev is of it."""

    program: NoteKeeper

    async def apply(self) -> None:
        p, note = self.program, self.program.note
        if note.id not in p.asked:
            p.asked.add(note.id)
            answers = await jev.ask(f"A note someone wrote: {note.text}", {"bucket": {  # jev gets plain keys: o0, o1, ...
                "type": "choice", "instructions": "What is this note?",
                "criteria": {f"o{i}": means for i, (_, means) in enumerate(BUCKETS)}}})
            odds = ((answers or {}).get("bucket") or {}).get("probabilities") or {}
            if chances := {name: c for i, name in enumerate(NAMES) if (c := odds.get(f"o{i}"))}:
                best = max(chances, key=chances.get)
                p.notes.change(INBOX, note.id, guess=best, conf=chances[best])
                p.note = note = next(n for n in p.notes.read(INBOX) if n.id == note.id)

        if note.guess is None:   p.state = "noidea"
        elif note.conf >= 0.7:   p.state = "sure"
        elif note.conf >= 0.4:   p.state = "maybe"
        else:                    p.state = "unsure"


class Confirm(Step):
    """A bucket to confirm: the note, quoted, and what it `SAYS`, over all the buckets, jev's
    picked already. OK puts the note in the one picked, Later (no answer) asks again in `LATER`."""

    program: NoteKeeper
    SAYS: str

    async def apply(self) -> None:
        p, note = self.program, self.program.note
        has     = NAMES.index(note.guess) if note.guess else None   # its bucket's place, picked already (None: none)
        says    = f"{quoted(note.text)}\n\n{self.SAYS.format(bucket=note.guess)}"
        answer  = await Popup.ask(says, BUCKETS, TIMEOUT, id=self.id, selected=has)
        if answer is None:  p.notes.change(INBOX, note.id, due=(Program.now + LATER).isoformat())
        else:               p.notes.move(note.id, INBOX, NAMES[answer])


class ConfirmNoIdea(Confirm):
    """A bucket to give: jev has no guess."""

    SAYS = "This note confused me. Is it a todo, an idea, or a random thought?"


class ConfirmUnsure(Confirm):
    """jev's bucket to confirm, jev under 40% sure."""

    SAYS = "I'd put this under {bucket}, but I'm not sure. Where does it go?"


class ConfirmMaybe(Confirm):
    """jev's bucket to confirm, jev 40 to 70% sure."""

    SAYS = "This looks like it goes under {bucket}. Is that right?"


class ConfirmSure(Confirm):
    """jev's bucket to confirm, jev 70% sure or more."""

    SAYS = "I'm pretty sure this goes under {bucket}. What do you say?"


class NoteKeeper(Ritual):
    TAGS = ("notes",)

    def __init__(self, notes: Notes):
        self.notes = notes
        self.asked : set[str]            = set()   # the notes jev was asked about
        self.state : str | None          = None    # the question's state, once looked
        self.note  : UnsortedNote | None = None    # and the note it's about
        Inlet(notes)
        make_variable("notes_sort_at", None)
        go   = lambda state, desc: make_branch(state, desc, **{state: lambda: self.state == state})
        back = [make_branch("idle", "answered, or not")]
        wait = timedelta(0)  # each state's: the next cycle
        super().__init__("@notes", [
            State("idle", do=[Look(self)], every=wait, desc="a note to sort", next=[
                go("sorting", "a note in the inbox due, you there, no question open"),
                make_branch("idle", "nothing to do"),
            ]),
            State("sorting", do=[Sort(self)], every=wait, desc="which question to ask about the note's bucket", next=[
                go("noidea", "no bucket from jev"),
                go("unsure", "jev's bucket, jev under 40% sure"),
                go("maybe", "jev's bucket, jev 40 to 70% sure"),
                go("sure", "jev's bucket, jev 70% sure or more"),
            ]),
            State("noidea", do=[ConfirmNoIdea(self)], every=wait, desc="which bucket the note is for", next=back),
            State("unsure", do=[ConfirmUnsure(self)], every=wait, desc="whether jev's bucket is right, jev unsure", next=back),
            State("maybe", do=[ConfirmMaybe(self)], every=wait, desc="whether jev's bucket is right", next=back),
            State("sure", do=[ConfirmSure(self)], every=wait, desc="whether jev's bucket is right, jev sure", next=back),
        ])
