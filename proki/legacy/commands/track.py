"""proki track / untrack: which apps are recorded by name."""

from __future__ import annotations

from datetime import datetime, timezone

from proki.legacy import config as config_mod
from proki.legacy.core.store import Store


def run(config: config_mod.Config, app: str | None, remove: bool) -> int:
    store = Store(config_mod.DB_PATH)
    now = datetime.now(timezone.utc)
    if remove:
        if app not in store.tracked_apps():
            print(f"{app} isn't tracked through proki (apps in the config file are removed there).")
            return 1
        store.forget_tracking(app)  # proki may ask about it again later
        print(f"No longer tracking {app}. Restart proki for the tray app to notice.")
        return 0
    if app:
        store.set_tracking(app, True, now)
        print(f"Tracking {app}. Restart proki for the tray app to notice.")
        return 0
    from_config = sorted({m.app for m in config.track})
    print("From the config file:", ", ".join(from_config) or "none")
    print("Added in proki:", ", ".join(store.tracked_apps()) or "none")
    return 0
