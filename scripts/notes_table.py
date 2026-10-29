"""Your notes made a table, once: each kept note a record of `note`, its id kept, noted when it was
(`created_at`); its id and at out of note's type in main.json, now the record's own.

    uv run python scripts/notes_table.py PATH      PATH: proki's database, or a copy of it

Done on a copy, then checked: the engine reads your notes from the table, as many as before and
each as it was. Only then is PATH written over. Refused while proki runs on PATH, and once done.
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from proki import settings, storage
from proki.core.records import Records
from proki.core.signals import Stream
from proki.engine import Engine
from proki.model import Defaults, Model
from proki.programs.code.base import Live, popup_open
from proki.programs.code.classify import AppDB, Apps, Track
from proki.programs.code.work import Work
from proki.programs.shipped import Shipped
from proki.serve import READS
from proki.services.nats import NatsBus

STAMPED = ("id", "at")  # a note's own, now its record's


def tabled(path: Path) -> None:
    """The notes at `path` a table, or why not."""
    if path.resolve() == settings.DB_PATH.resolve() and NatsBus.is_up(settings.HOST, settings.TOOLS_PORT):
        sys.exit("proki is running: quit it first. Nothing was changed.")
    copy = Path(tempfile.mkdtemp()) / path.name
    with sqlite3.connect(path) as given:
        given.backup(db := sqlite3.connect(copy))
    if not db.execute("SELECT 1 FROM variables WHERE name = 'note'").fetchone():
        sys.exit("no notes kept as a list: done already. Nothing was changed.")

    specs = storage.SpecDB(db).load()
    typed = next(v.type for v in specs.variables if v.name == "note" and v.program is None)
    kept  = storage.VariableDB(db).load("note", typed) or []
    main  = Defaults.dump(specs, None)
    for spec in main["variables"]:
        if spec["name"] == "note":
            spec.pop("value", None)
            spec["type"]["items"]["properties"] = {k: t for k, t in spec["type"]["items"]["properties"].items() if k not in STAMPED}
    model = Model(specs)
    model.swap([None], [Shipped.part(None, main)])
    storage.SpecDB(db).save(model.specs)
    with db:
        db.execute("DELETE FROM variables WHERE name = 'note'")
        for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND (name = 'var_note' OR name LIKE 'var\\_note\\_%' ESCAPE '\\')").fetchall():
            db.execute(f'DROP TABLE "{table}"')

    engine = Engine(model.specs, variables=storage.VariableDB(db), switches=storage.SwitchDB(db), reads=READS, programs=[
        Track(Apps(AppDB(db))).make,
        Work(db).make,
        lambda: Live("asking", popup_open, "whether a question waits for you", "boolean"),
    ])
    with db:
        db.executemany(f"INSERT INTO records_note (id, position, created_at, updated_at, kept, cache) VALUES (?, ?, ?, ?, ?, '{{}}')",
                       [(n["id"], i, n["at"], n["at"], json.dumps({k: v for k, v in n.items() if k not in STAMPED})) for i, n in enumerate(kept)])
    Records.writes += 1
    read = [{k: dict.get(r, k) for k in ("id", "content", "bucket", "due", "link")} for r in Stream.registry["note"].current()]
    said = [{k: n.get(k) for k in ("id", "content", "bucket", "due", "link")} for n in kept]
    print("notes before:", len(said), "after:", len(read))
    if read != said:
        sys.exit("the notes read aren't the ones kept: nothing was changed.")
    engine.close()
    with sqlite3.connect(path) as given:
        db.backup(given)
    print(f"done: {len(read)} notes, a table")


if __name__ == "__main__":
    tabled(Path(sys.argv[1]))
