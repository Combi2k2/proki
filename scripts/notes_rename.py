"""Your notes renamed, once: `notes` as `note`, its signals as note.*, the inbox as Unsorted, and
each note given its link (none).

    uv run python scripts/notes_rename.py PATH      PATH: proki's database, or a copy of it

Done on a copy, then checked: your notes counted the same in each bucket, and your programs
built with them. Only then is PATH written over. Refused while proki runs on PATH, and once done.
Your programs: main.json yours, with the notes' names as proki ships them now; the programs that
read the notes as proki ships them now (you never changed them).
"""

import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

from proki import settings, storage
from proki.core.signals import Stream
from proki.engine import Engine
from proki.model import Defaults, Model
from proki.programs.code.base import Live, popup_open
from proki.programs.code.classify import AppDB, Apps, Track
from proki.programs.code.work import Work
from proki.programs.shipped import Shipped
from proki.serve import READS
from proki.services.nats import NatsBus

PROGRAMS = ["note_sorter", "capture", "shutdown", "task_planner", "task_picker", "task_reminder"]  # the ones that read the notes
BUCKETS  = {"Inbox": "Unsorted"}


def renamed(path: Path) -> None:
    """The notes at `path` renamed, or why not."""
    if path.resolve() == settings.DB_PATH.resolve() and NatsBus.is_up(settings.HOST, settings.TOOLS_PORT):
        sys.exit("proki is running: quit it first. Nothing was changed.")
    copy = Path(tempfile.mkdtemp()) / path.name
    with sqlite3.connect(path) as given:
        given.backup(db := sqlite3.connect(copy))

    specs   = storage.SpecDB(db).load()
    old     = next((v for v in specs.variables if v.name == "notes" and v.program is None), None)
    if old is None:
        sys.exit("no `notes`: renamed already. Nothing was changed.")
    shipped = Shipped(settings.SHIPPED_DIR, storage.StateDB(db))
    main    = Defaults.dump(specs, None)
    ships   = Defaults.dump(shipped.shipped(None), None)
    for kind in ("variables", "signals"):  # the notes' names as proki ships them, where yours were
        at   = next(i for i, s in enumerate(main[kind]) if s["name"].split(".")[0] == "notes")
        kept = [s for s in main[kind] if s["name"].split(".")[0] != "notes"]
        main[kind] = [*kept[:at], *(s for s in ships[kind] if s["name"].split(".")[0] == "note"), *kept[at:]]
    model = Model(specs)
    model.swap([None, *PROGRAMS], [Shipped.part(None, main), *(shipped.shipped(name) for name in PROGRAMS)])
    storage.SpecDB(db).save(model.specs)
    shipped.kv.set(Shipped.KEY_SHIPPED, {**shipped.taken(), **{Shipped.file(name): Defaults.dump(shipped.shipped(name), name) for name in PROGRAMS}})

    kept  = storage.VariableDB(db)
    notes = kept.load("notes", old.type)
    new   = next(v for v in model.specs.variables if v.name == "note" and v.program is None)
    kept.save("note", [{**n, "bucket": BUCKETS.get(n["bucket"], n["bucket"]), "link": n.get("link")} for n in notes], new.type)
    with db:
        db.execute("DELETE FROM variables WHERE name = 'notes'")
        db.execute("UPDATE variables SET name = 'note' || substr(name, 6) WHERE name LIKE 'notes.%'")
        db.execute("DROP TABLE var_notes")

    engine = Engine(model.specs, variables=storage.VariableDB(db), switches=storage.SwitchDB(db), reads=READS, programs=[
        Track(Apps(AppDB(db))).make,
        Work(db).make,
        lambda: Live("asking", popup_open, "whether a question waits for you", "boolean"),
    ])
    before = Counter(BUCKETS.get(n["bucket"], n["bucket"]) for n in notes)
    after  = Counter(n["bucket"] for n in Stream.registry["note"].current() or [])  # as the engine reads them
    print("before:", dict(sorted(before.items())), "after:", dict(sorted(after.items())))
    if before != after:
        sys.exit("the notes counted aren't the same: nothing was changed.")
    engine.close()
    with sqlite3.connect(path) as given:
        db.backup(given)
    print(f"renamed: {sum(after.values())} notes, your programs built with them")


if __name__ == "__main__":
    renamed(Path(sys.argv[1]))
