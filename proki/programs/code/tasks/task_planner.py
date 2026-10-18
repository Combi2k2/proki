"""@task_planner: your todos, planned into groups of tasks, a few next tasks at a time.

A group (`TaskGr`) is what a todo's tasks go in: a project, or just what an errand takes. The
todos are the notes in the "Todo" bucket (notes.py), taken a note at a time, when no question
is open:

    todo ─ jev: goes with a group you have? ─ you confirm ─ its changes still suggested? you
    review them first ─ jev: clear what to do? ─ no: what exactly? (and again, until it is) ─
    yes: the LLM's changes to the group's tasks ─ suggested on the group (a new one, tagged
    by jev), its card opened for you to accept

- which group: jev picks among your open groups, or a new one, and you confirm it, jev's
  picked already. Later (no answer) asks again in a while
- review first: a group's changes still suggested are reviewed before it's refined again.
  OK opens its card, and the todo waits until they're all accepted or not (a while at most).
  Later (no answer) asks again in a while
- what exactly: jev reads the note (and the group it goes with) for whether it's clear what
  to do first. Only when jev is fairly sure it isn't, the next question, and jev reads
  again, three questions at most. A clear note asks nothing. No answer goes on with what
  there is
- the next tasks: the LLM sees the group as it is (what it's about, its tasks by their
  handles, done or not) and refines it (`Refinement`): it adds tasks, changes or removes open
  ones. As few as it takes: an errand's one or two, a piece of work's a few at a time, a
  flow you laid out all of it. A task is planned the way work is broken down well:

      short         its name a few words, a verb first, its details in `desc`. Its handle is
                    its name, slugified: how the LLM says which task it means
      small         each one focused session or less. Longer, or "and" in its name: two
                    tasks
      a slice       once it's done, something is done, works or exists that wasn't before,
                    not one layer of it
      checkable     what "done" looks like, three checks at most (`done_when`)
      ordered       each after the tasks it needs (`after`, by handles), the riskiest and most
                    unknown early, so a wrong assumption shows soon
      checkpoints   in longer work, after every two or three tasks, a short one to check it
                    all works together and decide what's next. Nothing planned past what's
                    known: if the work goes on, the last task is a checkpoint to plan the
                    next ones
      questions     what only you can answer, kept with the group

  Each change is only suggested: an op on the group's card (tasks/base.py), for you to
  accept or not. A change to a task done, or unknown, is left out.
- the group itself, refined with each todo: its title, its description, its tags (jev's
  likeliest for it, three at most, each likely enough, else the LLM's)

Without jev: you pick the group, and one answer is enough. Without an LLM: the todo waits a
while.

    idle        every cycle: a todo to take (`Look`)
    matching    which group it goes with (`Match`)
    reviewing   its changes still suggested, reviewed first? (`Review`)
    waiting     every cycle: until they're reviewed, a while at most
    clarifying  what exactly (`Clarify`)
    refining    the next tasks, suggested on the group (`Refine`)
    confirming  the group's card opened, its ops for you to accept (`Confirm`)
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import UTC, datetime, timedelta

from proki.channels import Popup, llm
from proki.core.programs import Program, State
from proki.programs.code.base import Ritual, Step, ask_jev, ask_usr, make_branch, popup_open
from proki.programs.code.notes import TODO, Notes, TodoNote
from proki.programs.code.tasks.base import MAX_TAGS, OP_FIELDS, ROW, TAGS, Board, Task, TaskGr, TaskOp, unique
from proki.typehint import schema
from proki.utils import slugify

TIMEOUT    = 24 * 3600            # how long a question waits for you, in seconds
LATER      = timedelta(hours=2)   # "Later", asked which group
UNCLEAR    = 0.3                  # jev's probability of "clear" below which you're asked more
TAG_MIN    = 0.1                  # jev's probability of a tag, to give it
NEXT_TASKS = 5                    # new tasks at most, at a time: more only for a flow laid out
SESSION    = 50                   # minutes: the longest a task should take
NEW        = ("A new group", "Tasks that go with none of the groups here yet")
FOLLOW_UPS = [
    "What do you need to do, exactly?",
    "What would “done” look like?",
    "What's the very first thing you'd do?",
]
PROMPT = """You help someone turn what they need to do into its next tasks: an errand, a chore,
or a piece of work.

{group}

What they need to do now, in their words:
{note}

First, hold what they wrote up against each of the group's tasks, done or not, by what it
does, not by its words: two tasks overlap when doing one does much of the other.
- a task covers it already: no change, or a "change" to that task if what they wrote adds to it
  (a detail, a check, a deadline). Not a new task
- their tasks cover it all already: no changes at all. That's a fine answer

Then plan the next tasks, as changes to the group's tasks:
- "add" a task, only for what no task of theirs does, nor any other task you add. As few as it takes: an errand or a chore is often one or two. A piece of work
  is planned a few tasks at a time, {tasks} at most. If they laid out steps, plan every one of
  them, in their order
- "change" an open task, by its handle: only the fields that change
- "remove" an open task, by its handle, only if what they wrote now makes it unneeded
Each task:
- its name a few words (6 at most), starting with a verb, specific enough to start right
  away. Keep their words where you can. Anything more goes in its desc
- its handle is its name in lowercase, words joined by "_": "Buy milk and eggs" is "buy_milk_and_eggs"
- one sitting: {session} minutes or less, with your estimate in minutes. If it would take longer, it's two tasks
- once it's done, something is done, works or exists that wasn't before, not just one layer of it
- with what "done" looks like: at most 3 checks anyone could make
- "after": the handles of the tasks it needs done first, theirs or yours. The riskiest and
  most unknown ones early, so a wrong assumption shows soon
- in work of more than 3 tasks, after every 2 or 3 tasks, a checkpoint: a short task to check it all works together and decide
  what's next. Don't plan past what's known: if the work goes on, the last task is a checkpoint to plan the next tasks
Then the group itself, with what they wrote now taken in:
- its title, a few words ("Groceries", "Thesis"). A group they have keeps its own, unless it no
  longer fits what the group has become
- its description, a sentence or two: what it's for and where it stands. Not their words as
  they are: what anyone would read on its card
- up to three tags for what part of their life it's for, the most likely first
- the open questions only they can answer, if any"""
FORCED = ("name", "desc", "done_when", "after", "checkpoint", "estimate")   # a task's fields, the LLM's to give
SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "desc": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string", "enum": TAGS}, "maxItems": MAX_TAGS},
        "questions": {"type": "array", "items": {"type": "string"}},
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    **schema(Task, [f.name for f in fields(Task) if f.name not in FORCED]),
                    "op"    : {"type": "string", "enum": ["add", "change", "remove"]},
                    "task"  : {"type": "string", "description": "change, remove: the task's handle"},
                    "after" : {"type": "array",  "items": {"type": "string"}, "description": "the handles of the tasks it needs done first"},   # handles, not a task's ids
                },
                "required": ["op"],
            },
        },
    },
    "required": ["title", "desc", "tags", "questions", "changes"],
}


@dataclass(frozen=True)
class Refinement:
    """The LLM's refinement of a group's tasks: a note into its next tasks, or a plan further.

        title       the group's, a few words
        changes     its changes to the group's tasks, as the LLM gives them: by handles
        desc        the group's, what it's for and where it stands
        tags        the group's
        questions   what only you can answer
    """

    title     : str
    changes   : list[dict]
    desc      : str       = ""
    tags      : list[str] = field(default_factory=list)
    questions : list[str] = field(default_factory=list)


def context(group: TaskGr | None, tasks: list[Task]) -> str:
    """The group as the LLM sees it: what it's about, and its tasks so far by their handles,
    each with its desc and what "done" looks like (dropped ones left out)."""
    if group is None:
        return "It goes with none of their groups of tasks: a new group."
    named  = {task.id: task.handle for task in tasks}
    listed = "\n".join(f"- [{' ' if task.status == 'open' else 'x'}] {task.handle}: {task.name}"
                       + (f" (after {', '.join(named[k] for k in task.after if k in named)})" if task.after else "")
                       + (f"\n  {task.desc}" if task.desc else "")
                       + (f"\n  done when: {'; '.join(task.done_when)}" if task.done_when else "")
                       for task in tasks if task.status != "dropped")
    return (f"It goes with their group of tasks “{group.name}”: {group.desc or '(no description)'}"
            f" (tags: {', '.join(group.tags) or 'none'})\n\n"
            f"Its tasks so far:\n{listed or '(none yet)'}")


def quoted(text: str, short: int = 120) -> str:
    """A todo as a question quotes it: its first line, its start if it's long."""
    line = text.strip().splitlines()[0]
    return f"“{line[:short].rstrip()}…”" if len(line) > short or "\n" in text.strip() else f"“{line}”"


class Look(Step):
    """The first todo, when no question is open, and not asked to wait."""

    program: TaskPlanner

    async def apply(self) -> None:
        p      = self.program
        p.todo = None if popup_open() or p.later > Program.now else next(iter(p.notes.read(TODO)), None)


class Match(Step):
    """Which group the todo goes with: jev's pick among your open ones, or a new one, for you
    to confirm."""

    program: TaskPlanner

    async def apply(self) -> None:
        p, note = self.program, self.program.todo
        groups  = [group for group in p.board.read().groups if group.status == "open"]
        p.key   = None
        p.state = "clarifying"
        if not groups:
            return  # a new one

        options = [NEW, *((group.name, group.desc[:200] or group.name) for group in groups)]
        odds    = await ask_jev(f"A todo someone wrote: {note.text}", "Which of their groups of tasks does this todo go with?", options)
        answer  = await ask_usr(f"{quoted(note.text)}\n\nDoes this go with tasks you already have?", options, TIMEOUT,
                                id=self.id, selected=max(odds, key=odds.get) if odds else None)
        if answer is None:  p.state, p.later = None, Program.now + LATER
        elif answer > 0:    p.key = groups[answer - 1].id
        if p.key and p.pending():
            p.state = "reviewing"


class Review(Step):
    """The group's changes still suggested, for you to review first: OK opens its card."""

    program: TaskPlanner

    async def apply(self) -> None:
        p, now = self.program, Program.now
        many   = len(p.pending())
        answer = await ask_usr(f"{quoted(p.todo.text)}\n\n“{p.board.read().of[p.key].name}” still has {many} suggested "
                               f"change{'s' if many > 1 else ''}. Review {'them' if many > 1 else 'it'} first? It won't take long.",
                               ["OK"], TIMEOUT, id=self.id)
        p.state, p.later = "waiting" if answer == 0 else None, now + LATER
        if answer == 0:
            Popup.send({"type": "open", "view": "tasks", "group": p.key})


class Clarify(Step):
    """What exactly: asked until jev finds it clear, three questions at most."""

    program: TaskPlanner

    async def apply(self) -> None:
        p         = self.program
        group     = p.board.read().of.get(p.key)
        note      = p.todo.text
        about     = f"It goes with their group of tasks “{group.name}”: {group.desc}\n" if group else ""
        p.context = note
        for question in FOLLOW_UPS:
            clear = await ask_jev(f"A todo someone wrote for themselves: {about}{p.context}",
                                  "Is it clear what they need to do, enough to start on it? Short notes are fine: they know their own work.")
            if clear is None or clear >= UNCLEAR:
                break  # jev isn't fairly sure it's unclear
            if not (answer := await ask_usr(f"{quoted(note)}\n\n{question}", None, TIMEOUT, id=self.id)):
                break  # on with what there is
            p.context = f"{p.context}\n{answer}"


class Refine(Step):
    """The LLM's refinement, the group and its tasks so far in sight: its title, description and
    tags refined (a new group: made), and its changes suggested on its card, each change an op,
    each task by its handle. An add's is given now, for the ones after it. A change to a task
    unknown or not open is left out, and so is one that isn't an op. No changes: the group
    covers it already, you're told so, and the todo's taken."""

    program: TaskPlanner

    async def apply(self) -> None:
        p, now  = self.program, Program.now
        work    = p.board.read()
        group   = work.of.get(p.key)
        known   = [task for task in work.tasks if task.group == p.key]
        prompt  = PROMPT.format(group=context(group, known), note=p.context, tasks=NEXT_TASKS, session=SESSION)
        answer  = await llm.ask(prompt, schema=SCHEMA, timeout=60)
        p.state = None
        try:
            refined = Refinement(**answer)
            if not (group or refined.title and refined.changes):
                raise ValueError("a new group needs a title, and tasks")
        except (TypeError, ValueError):  # no LLM, no answer, or not one
            p.later = now + LATER
            return
        if not refined.changes:
            Popup.poke(f"Nothing to add: “{group.name}” already covers {quoted(p.todo.text)}.")
            p.notes.remove(TODO, p.todo.id)
            return

        tags = await tags_of(refined.desc or p.context) or [tag for tag in refined.tags if tag in TAGS][:MAX_TAGS]   # the LLM's, only ones there are
        if group:
            p.board.change("group", p.key, now,
                name=refined.title or group.name,
                desc=refined.desc or group.desc,
                tags=tags or group.tags,
                questions=[*group.questions, *refined.questions]
            )
        else:
            p.key = p.board.add("group", now,
                name=refined.title,
                desc=refined.desc,
                tags=tags,
                questions=refined.questions
            )

        open_ = {task.handle for task in known if task.status == "open"}
        taken = {task.handle for task in known}
        new   = {}                                   # each add's handle, by its change's place
        for i, change in enumerate(refined.changes):
            if change.get("op") == "add":
                new[i] = unique(slugify(str(change.get("name", ""))) or "task", taken)
                taken.add(new[i])

        for i, change in enumerate(refined.changes):
            op, task = change.get("op"), slugify(str(change.get("task", "")))
            if op != "add" and task not in open_:
                continue
            fields = {name: value for name, value in change.items() if name in OP_FIELDS} | ({"handle": new[i]} if i in new else {})
            after  = change.get("after")
            after  = [h for h in map(slugify, map(str, after)) if h in taken and h != new.get(i)] if isinstance(after, list) else None
            try:
                p.board.add("op", group=p.key, op=op, task=None if op == "add" else task, fields=fields, after=after)
            except ValueError:
                continue  # not an op
        p.state = "confirming"


class Confirm(Step):
    """The group's card opened, for you to accept its ops or not."""

    program: TaskPlanner

    async def apply(self) -> None:
        p = self.program
        p.notes.remove(TODO, p.todo.id)
        Popup.send({"type": "open", "view": "tasks", "group": p.key})


async def tags_of(text: str) -> list[str]:
    """jev's likeliest tags for what someone has to do, three at most, each likely enough (none
    without jev)."""
    odds   = await ask_jev(f"Something someone has to do: {text}", "What part of their life is it for?",
                           [(tag, ROW[tag]) for tag in TAGS])
    likely = sorted(odds.items(), key=lambda pair: -pair[1])
    return [TAGS[i] for i, chance in likely[:MAX_TAGS] if chance >= TAG_MIN]


class TaskPlanner(Ritual):
    TAGS = ("tasks", "notes")

    def pending(self) -> list[TaskOp]:
        """The group's changes still suggested."""
        return [op for op in self.board.read().ops if op.group == self.key]

    def __init__(self, board: Board, notes: Notes):
        self.board   = board
        self.notes   = notes
        self.todo    : TodoNote | None = None   # the todo to take, once looked
        self.key     : int | None      = None   # the group it goes with (None: a new one, until it's made)
        self.state   : str | None      = None   # where the todo goes on, once matched, reviewed or refined
        self.context : str             = ""     # the todo, and what you said of it
        self.later   : datetime        = datetime.min.replace(tzinfo=UTC)   # "Later": not before then (waiting: not past)
        super().__init__("@task_planner", [
            State("idle",       do=[Look(self)],    every=timedelta(0), desc="a todo, no question open", next=[
                make_branch("matching", "a todo to take",              todo=lambda: self.todo is not None),
                make_branch("idle"),
            ]),
            State("matching",   do=[Match(self)],   every=timedelta(0), desc="which group it goes with", next=[
                make_branch("clarifying", "a group, or a new one",       clarifying=lambda: self.state == "clarifying"),
                make_branch("reviewing",  "its changes still suggested", reviewing=lambda: self.state == "reviewing"),
                make_branch("idle",       "later"),
            ]),
            State("reviewing",  do=[Review(self)],  every=timedelta(0), desc="its changes, reviewed first?", next=[
                make_branch("waiting",    "you review them",             waiting=lambda: self.state == "waiting"),
                make_branch("idle",       "later"),
            ]),
            State("waiting",    do=[],              every=timedelta(0), desc="until they're reviewed", next=[
                make_branch("clarifying", "reviewed",                    reviewed=lambda: not self.pending()),
                make_branch("idle",       "a while",                     late=lambda: Program.now >= self.later),
                make_branch("waiting"),
            ]),
            State("clarifying", do=[Clarify(self)], every=timedelta(0), desc="what exactly", next=[
                make_branch("refining"),
            ]),
            State("refining",   do=[Refine(self)],  every=timedelta(0), desc="the next tasks, suggested", next=[
                make_branch("confirming", "refined",                     refined=lambda: self.state == "confirming"),
                make_branch("idle",       "later"),
            ]),
            State("confirming", do=[Confirm(self)], every=timedelta(0), desc="its card opened for you", next=[
                make_branch("idle"),
            ]),
        ])
