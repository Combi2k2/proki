"""The emojis you chose, as the ones proki ships.

For the dev phase: choose an action's pictures and sounds in the UI, then run this to make
them what a new user starts with.

    uv run python scripts/emojis.py           what it would write
    uv run python scripts/emojis.py --write   written

Taken: the questions' pool, and the picks of each action proki ships, by its id. Picks of an
action that isn't shipped (one of yours) are listed, not taken.
"""

import json
import sqlite3
import sys

from proki import settings

EMOJIS = settings.ASSETS_DIR / "emojis.json"


def main() -> None:
    db     = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    listed = lambda table, column, name: [key for (key,) in db.execute(
        f"SELECT key FROM {table} WHERE {column} = ? ORDER BY pos", (name,))]
    ids    = [f"{path.stem}.{state}.{action['name']}" for path in sorted(settings.SHIPPED_DIR.glob("*.json"))
              for state, spec in json.loads(path.read_text()).get("program", {}).get("states", {}).items()
              for action in spec.get("do", []) if "name" in action and ("poke" in action or "ask_usr" in action)]
    picked = {id for (id,) in db.execute("SELECT DISTINCT id FROM media_picks")}

    emojis = {
        "pools": {"questions": listed("media_pools", "pool", "questions")},
        "picks": {id: keys for id in ids if (keys := listed("media_picks", "id", id))},
    }
    lines  = lambda d: ",\n".join(f"    {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}" for k, v in d.items())
    text   = '{\n  "pools": {\n' + lines(emojis["pools"]) + '\n  },\n  "picks": {\n' + lines(emojis["picks"]) + "\n  }\n}\n"  # one per line
    print(text)
    if missing := [id for id in ids if id not in emojis["picks"]]:
        print("shipped, nothing picked:", ", ".join(missing))
    if others := sorted(picked - set(ids)):
        print("picked, not shipped (not taken):", ", ".join(others))
    if "--write" in sys.argv:
        EMOJIS.write_text(text)
        print(f"written: {EMOJIS}")


if __name__ == "__main__":
    main()
