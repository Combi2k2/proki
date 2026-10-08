"""Start at login through an XDG autostart entry. Not yet tested.

Works on GNOME, KDE, XFCE and most desktops. On Wayland, ActivityWatch needs
the `awatcher` window watcher, and popups cannot choose their position.
"""

import shlex
import subprocess
from pathlib import Path

from platformdirs import user_config_path

DESKTOP_FILE = user_config_path("autostart") / "proki.desktop"
ACTIVITYWATCH_DIRS = [Path.home() / "activitywatch", Path("/opt/activitywatch"), Path("/usr/lib/activitywatch")]
EXECUTABLE_SUFFIX = ""
NATS_DIRS = [Path("/usr/local/bin"), Path("/usr/bin"), Path.home() / ".local" / "bin", Path.home() / "go" / "bin"]

# the browsers, as ActivityWatch names them (the window's class). Not yet tested
BROWSER_APPS = {
    "Google-chrome", "Microsoft-edge", "Brave-browser", "Chromium", "Vivaldi-stable", "firefox", "Opera",
    "Google Chrome", "Microsoft Edge", "Brave Browser", "Vivaldi", "Firefox",
}

# the lock screen / screen saver: time on it is time away
LOCK_APPS = set()

# system windows that come and go on their own. Never worth a question
SYSTEM_APPS = {"gnome-shell", "plasmashell", "xfdesktop", "unknown"}


def install_autostart(command: list[str]) -> None:
    DESKTOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=proki\n"
        f"Exec={shlex.join(command)}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def uninstall_autostart() -> None:
    Path(DESKTOP_FILE).unlink(missing_ok=True)


def autostart_installed() -> bool:
    return DESKTOP_FILE.exists()


def lock_screen() -> None:
    subprocess.Popen(["loginctl", "lock-session"])


def close_tab(app: str, url: str) -> bool:
    return False  # not supported yet


def close_window(app: str, title: str) -> bool:
    return False  # not supported yet
