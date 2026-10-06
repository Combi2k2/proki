"""The only OS-specific code. Each module exposes the same interface:

    install_autostart(command: list[str]) -> None
    uninstall_autostart() -> None
    autostart_installed() -> bool
    ACTIVITYWATCH_DIRS: list[Path]   where ActivityWatch's programs usually are
    EXECUTABLE_SUFFIX: str           "" or ".exe"
    BROWSER_APPS: set[str]           the browsers, as ActivityWatch names them
    LOCK_APPS: set[str]              the lock screen / screen saver (time on it counts as away)
    SYSTEM_APPS: set[str]            system windows never worth a question (plus the `ignore_apps` setting)
    lock_screen() -> None            lock the screen / put the display to sleep
    close_tab(app, url) -> bool      close a browser tab (False: couldn't)
    close_window(app, title) -> bool close an app's window (False: couldn't)
"""

import sys
from types import ModuleType

from proki.errors import PlatformError


def current() -> ModuleType:
    if sys.platform == "darwin":
        from proki.platforms import macos as mod
    elif sys.platform == "win32":
        from proki.platforms import windows as mod
    elif sys.platform.startswith("linux"):
        from proki.platforms import linux as mod
    else:
        raise PlatformError(f"Unsupported platform: {sys.platform}")
    return mod
