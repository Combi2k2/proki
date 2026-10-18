"""@notes: what you note down, sorted into its bucket, with you to confirm it.

A note comes in through the global variable `note`, as a text: capture's question, shutdown's
"what's still open?", the UI's "New note…". It goes into the inbox at once, and is weighed on
its own (`Inlet`): jev guesses its bucket and how urgent it is, and you're asked whether to
deal with it now. OK asks its bucket right away.

Else it's sorted at its time, the oldest first, once you're at the computer and no question
is open (`due`):

    its own     you said "Later" to its bucket: two hours on
    shutdown's  the time you chose there, if it's after the note was noted
    04:00       else the first after it was noted: a day without a shutdown is sorted the
                next morning

The buckets are labels, each with what it means for jev. A note is of its bucket's kind: an
`UnsortedNote` in the inbox, then a `TodoNote`, an `IdeaNote` or a `ThoughtNote`. Each bucket
is a queue in proki's key store (`Notes`): a program downstream reads its own, and removes a
note once it's done with it. "Todo" is the task planner's.

    idle        the inbox's oldest note due, you there, no question open (`Look`)
    noidea      no guess from jev: which bucket is it? (`ConfirmNoIdea`)
    unsure      jev's bucket, jev under 40% sure (`ConfirmUnsure`)
    maybe       jev's bucket, jev 40 to 70% sure (`ConfirmMaybe`)
    sure        jev's bucket, jev 70% sure or more (`ConfirmSure`)

The bucket is chosen from them all, jev's picked already: OK keeps it. A long note is quoted
by its start. Only the note's text is sent to jev.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime, timedelta

from proki.core.programs import Program, State
from proki.core.signals import Stream, Variable
from proki.programs.code.base import Ritual, Step, ask_jev, ask_usr, make_branch, make_variable, popup_open
from proki.storage import StateDB

LATER   = timedelta(hours=2)   # "Later"
TIMEOUT = 300                  # how long a question waits for you, in seconds
SHORT   = 120                  # characters of a note, quoted in a question
SORT_AT = 4 * 60               # minutes into the day: a note's time, when shutdown chose none after it
URGENT  = [                    # jev's chance a note is urgent, at least, and what you're asked
    (0.7, "This sounds urgent. Deal with it now?"),
    (0.3, "Deal with this now?"),                         # jev's no guess too
    (0.0, "This can probably wait. Deal with it now anyway?"),
]

INBOX   = "Inbox"              # the notes not sorted yet
BUCKETS = [                    # each bucket, and what it means
    ("Todo",    "Something the person needs to do: a task"),
    ("Idea",    "An idea worth keeping: something to build, try or explore later"),
    ("Thought", "Just a thought, noted down to let it go: nothing to do, nor to keep"),
]
NAMES   = [name for name, _ in BUCKETS]
TODO    = NAMES[0]             # the task planner's


# --- notes ------------------------------------------------------------------------------------

@dataclass
class Note:
    """What you noted down, as noted."""

    id    : str
    text  : str
    at    : str                    # when it was noted, as ISO text


@dataclass
class UnsortedNote(Note):
    """In the inbox, to sort."""

    due   : str | None   = None    # when to sort it, as ISO text (None: with the others)
    guess : str | None   = None    # jev's bucket
    conf  : float | None = None    # how likely jev found it


@dataclass
class TodoNote(Note):
    """For the task planner to take."""


@dataclass
class IdeaNote(Note):
    """Kept, in the Notes view."""


@dataclass
class ThoughtNote(Note):
    """Kept, in the Notes view: noted down to let it go."""


KINDS = {INBOX: UnsortedNote, "Todo": TodoNote, "Idea": IdeaNote, "Thought": ThoughtNote}   # by bucket


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
        if bucket not in KINDS:
            raise ValueError(f"no bucket {bucket!r}")
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
        if note := self.remove(start, id):
            self.keep(to, [*self.read(to), KINDS[to](note.id, note.text, note.at)])

    def keep(self, bucket: str, notes: list[Note]) -> None:
        """The bucket, as `notes`."""
        if bucket not in KINDS:
            raise ValueError(f"no bucket {bucket!r}")
        self.kv.set(self.KEY, self.kv.get(self.KEY, {}) | {bucket: [asdict(note) for note in notes]})


def due(note: UnsortedNote) -> datetime:
    """When the note is sorted: its own time, else the one you chose in shutdown if it's after
    the note was noted, else the first 04:00 after it was."""
    if note.due:
        return datetime.fromisoformat(note.due)

    at     = datetime.fromisoformat(note.at)
    chosen = getattr(Stream.registry.get("notes_sort_at"), "value", None)   # minutes since 1970 (0 or None: none)
    if isinstance(chosen, int | float) and (then := datetime.fromtimestamp(chosen * 60, UTC)) >= at:
        return then

    local = at.astimezone()
    start = local.replace(hour=SORT_AT // 60, minute=SORT_AT % 60, second=0, microsecond=0)
    return start if start > local else start + timedelta(days=1)


def quoted(text: str) -> str:
    """A note as a question quotes it: its first line, its start if it's long."""
    line = text.strip().splitlines()[0]
    return f"“{line[:SHORT].rstrip()}…”" if len(line) > SHORT or "\n" in text.strip() else f"“{line}”"


class Inlet(Variable):
    """The global variable `note`, made before the config is built. A text written to it goes
    into the inbox at once, so none waits for a program to look, nor is lost while a question
    waits, and is weighed on its own (`weigh`). Without `notes`, it's only a variable."""

    def __init__(self, notes: Notes | None = None):
        super().__init__("note", None, desc="a note any program writes: into the inbox at once, for @notes to sort", persist=False)
        self.notes   = notes
        self.weighed : set[asyncio.Task] = set()   # the notes being weighed, until their questions are answered

    def set(self, value) -> None:
        super().set(value)
        if not self.notes or not isinstance(value, str) or not value.strip():
            return

        note = self.notes.add(INBOX, value.strip(), Program.now or datetime.now(UTC))
        try:
            task = asyncio.get_running_loop().create_task(self.weigh(note))
        except RuntimeError:  # no loop: not weighed, so sorted with the others
            return
        self.weighed.add(task)
        task.add_done_callback(self.weighed.discard)

    async def weigh(self, note: UnsortedNote) -> None:
        """jev's guesses, its bucket (kept with the note) and how urgent it is, then whether to
        deal with it now, asked in words by how urgent:

            OK                  its bucket, asked right away
            Later, no answer    sorted with the others, at its time
        """
        said   = f"A note someone wrote: {note.text}"
        odds   = await ask_jev(said, "What is this note?", BUCKETS)
        chance = await ask_jev(said, "Does this need dealing with right away, today?")
        if odds:
            best = max(odds, key=odds.get)
            self.notes.change(INBOX, note.id, guess=NAMES[best], conf=odds[best])

        says = next(says for least, says in URGENT if (0.5 if chance is None else chance) >= least)
        if await ask_usr(f"{quoted(note.text)}\n\n{says}", ["OK"], TIMEOUT) != 0:
            return
        if note := next((n for n in self.notes.read(INBOX) if n.id == note.id), None):  # with jev's guess, if still there
            await CONFIRMS[asked(note)].sort(self.notes, note)


# --- the program ------------------------------------------------------------------------------

class Look(Step):
    """The inbox's oldest note due, while you're at the computer and no question is open, and
    which question to ask about its bucket."""

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
            p.note, p.state = note, asked(note)


class Confirm(Step):
    """A note's bucket to give or confirm: the note, quoted, and its question over all the
    buckets, jev's picked already. OK puts the note in the one picked, Later (no answer) asks
    again in a while."""

    program: NoteKeeper
    SAYS: str

    async def apply(self) -> None:
        await self.sort(self.program.notes, self.program.note, self.id)

    @classmethod
    async def sort(cls, notes: Notes, note: UnsortedNote, id: str | None = None) -> None:
        """The note's bucket, asked: by its step, or by `Inlet.weigh` as you say to deal with it now."""
        has    = NAMES.index(note.guess) if note.guess else None   # its bucket's place, picked already (None: none)
        answer = await ask_usr(f"{quoted(note.text)}\n\n{cls.SAYS.format(bucket=note.guess)}", BUCKETS, TIMEOUT,
                               id=id, selected=has)
        if answer is None:  notes.change(INBOX, note.id, due=((Program.now or datetime.now(UTC)) + LATER).isoformat())
        else:               notes.move(note.id, INBOX, NAMES[answer])


class ConfirmNoIdea(Confirm):
    """A bucket to give: jev has no guess."""

    SAYS = "Is this a todo, an idea, or just a passing thought?"


class ConfirmUnsure(Confirm):
    """jev's bucket to confirm, jev under 40% sure."""

    SAYS = "I'd put this under {bucket}, but I'm not sure. Where does it go?"


class ConfirmMaybe(Confirm):
    """jev's bucket to confirm, jev 40 to 70% sure."""

    SAYS = "This looks like it goes under {bucket}. Is that right?"


class ConfirmSure(Confirm):
    """jev's bucket to confirm, jev 70% sure or more."""

    SAYS = "I'm pretty sure this goes under {bucket}. Right?"


CONFIRMS = {"noidea": ConfirmNoIdea, "unsure": ConfirmUnsure, "maybe": ConfirmMaybe, "sure": ConfirmSure}   # by state


def asked(note: UnsortedNote) -> str:
    """The state that asks a note's bucket, by how sure jev is of its guess."""
    if note.guess is None:   return "noidea"
    elif note.conf >= 0.7:   return "sure"
    elif note.conf >= 0.4:   return "maybe"
    else:                    return "unsure"


class NoteKeeper(Ritual):
    TAGS = ("notes",)

    def __init__(self, notes: Notes):
        self.notes = notes
        self.state : str | None          = None   # the state that asks, once looked
        self.note  : UnsortedNote | None = None   # and the note it asks about
        Inlet(notes)
        make_variable("notes_sort_at", None)
        go   = lambda state, desc: make_branch(state, desc, **{state: lambda: self.state == state})
        back = [make_branch("idle", "answered, or not")]
        wait = timedelta(0)  # each state's: on at once
        super().__init__("@notes", [
            State("idle",   do=[Look(self)],          every=wait, desc="a note to sort, and which question asks its bucket", next=[
                go("noidea", "no guess from jev"),
                go("unsure", "jev's bucket, jev under 40% sure"),
                go("maybe",  "jev's bucket, jev 40 to 70% sure"),
                go("sure",   "jev's bucket, jev 70% sure or more"),
                make_branch("idle", "nothing to do"),
            ]),
            State("noidea", do=[ConfirmNoIdea(self)], every=wait, desc="which bucket the note is for",               next=back),
            State("unsure", do=[ConfirmUnsure(self)], every=wait, desc="whether jev's bucket is right, jev unsure",  next=back),
            State("maybe",  do=[ConfirmMaybe(self)],  every=wait, desc="whether jev's bucket is right",              next=back),
            State("sure",   do=[ConfirmSure(self)],   every=wait, desc="whether jev's bucket is right, jev sure",    next=back),
        ])
