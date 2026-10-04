"""proki categorize: list remembered categories, or set one."""

from __future__ import annotations

from datetime import datetime, timezone

from proki.legacy import config as config_mod
from proki.core.events import Category
from proki.legacy.core.store import Store


def run(key: str | None, category: str | None) -> int:
    store = Store(config_mod.DB_PATH)
    if key and category:
        store.set_category(key, Category(category), "user", datetime.now(timezone.utc))
        print(f"{key} → {category}")
        return 0
    if key:
        print("Give a category too: " + ", ".join(c.value for c in Category))
        return 2
    rows = store.all_categories()
    for k, c, source in rows:
        print(f"  {c.value:<11}  {k}  ({source})")
    if not rows:
        print("No remembered categories yet (config rules are in the config file).")
    return 0
