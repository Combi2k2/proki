"""Your notes' names gone, once: note.sort_at and the note.* signals out of main.json, the
programs that read them as proki ships them now, and the counters nothing read with them.

    uv run python scripts/notes_fields.py PATH      PATH: proki's database, or a copy of it

Done on a copy, then checked: your programs built with your notes, as many as before. Only then
is PATH written over. Refused while proki runs on PATH, and once done. main.json stays yours, as
it is but for the notes' names; the programs that read them are as proki ships them now (you
never changed them).
"""

import sqlite3
import sys
import tempfile
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

PROGRAMS = ["note_sorter", "capture", "shutdown", "task_planner", "task_picker", "task_reminder", "day"]  # the ones that read them
GONE     = ["note.sort_at", "week_change", "distracted_today", "focused_month", "focused_year"]          # the values kept of them


def cleared(path: Path) -> None:
    """The notes' names at `path` gone, or why not."""
    if path.resolve() == settings.DB_PATH.resolve() and NatsBus.is_up(settings.HOST, settings.TOOLS_PORT):
        sys.exit("proki is running: quit it first. Nothing was changed.")
    copy = Path(tempfile.mkdtemp()) / path.name
    with sqlite3.connect(path) as given:
        given.backup(db := sqlite3.connect(copy))

    specs = storage.SpecDB(db).load()
    main  = Defaults.dump(specs, None)
    if not any(s["name"].startswith("note.") for kind in ("variables", "signals") for s in main[kind]):
        sys.exit("no note.* names: done already. Nothing was changed.")
    for kind in ("variables", "signals"):
        main[kind] = [s for s in main[kind] if not s["name"].startswith("note.")]
    shipped = Shipped(settings.SHIPPED_DIR, storage.StateDB(db))
    model   = Model(specs)
    model.swap([None, *PROGRAMS], [Shipped.part(None, main), *(shipped.shipped(name) for name in PROGRAMS)])
    storage.SpecDB(db).save(model.specs)
    shipped.kv.set(Shipped.KEY_SHIPPED, {**shipped.taken(), **{Shipped.file(name): Defaults.dump(shipped.shipped(name), name) for name in [None, *PROGRAMS]}})
    with db:
        db.executemany("DELETE FROM variables WHERE name = ?", [(name,) for name in GONE])

    typed  = next(v.type for v in model.specs.variables if v.name == "note" and v.program is None)
    noted  = len(storage.VariableDB(db).load("note", typed) or [])
    engine = Engine(model.specs, variables=storage.VariableDB(db), switches=storage.SwitchDB(db), reads=READS, programs=[
        Track(Apps(AppDB(db))).make,
        Work(db).make,
        lambda: Live("asking", popup_open, "whether a question waits for you", "boolean"),
    ])
    read = len(Stream.registry["note"].current() or [])  # as the engine reads them
    print("notes before:", noted, "after:", read)
    if noted != read:
        sys.exit("the notes counted aren't the same: nothing was changed.")
    engine.close()
    with sqlite3.connect(path) as given:
        db.backup(given)
    print(f"done: {read} notes, your programs built with them")


if __name__ == "__main__":
    cleared(Path(sys.argv[1]))
