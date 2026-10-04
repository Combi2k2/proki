"""proki autostart install|uninstall|status: start proki at login."""

from __future__ import annotations

import sys

from proki import platforms


def run(action: str) -> int:
    os_support = platforms.current()
    if action == "install":
        os_support.install_autostart([sys.executable, "-m", "proki"])
        print("proki will now start at login.")
    elif action == "uninstall":
        os_support.uninstall_autostart()
        print("proki will no longer start at login.")
    else:
        print("installed" if os_support.autostart_installed() else "not installed")
    return 0
