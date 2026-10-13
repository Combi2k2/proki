"""Linux: where ActivityWatch and NATS are installed, which apps are browsers or the system's,
and locking the screen. Not yet tested. On Wayland, ActivityWatch needs the `awatcher`
window watcher, and popups cannot choose their position.
"""

import subprocess
from pathlib import Path

ACTIVITYWATCH_DIRS = [Path.home() / "activitywatch", Path("/opt/activitywatch"), Path("/usr/lib/activitywatch")]
EXECUTABLE_SUFFIX = ""
NATS_DIRS = [Path("/usr/local/bin"), Path("/usr/bin"), Path.home() / ".local" / "bin", Path.home() / "go" / "bin"]

# the browsers, as ActivityWatch names them (the window's class). Not yet tested
BROWSER_APPS = {
    "Google-chrome", "Microsoft-edge", "Brave-browser", "Chromium", "Vivaldi-stable", "firefox", "Opera",
    "Google Chrome", "Microsoft Edge", "Brave Browser", "Vivaldi", "Firefox",
}

# system windows that come and go on their own. Never worth a question
SYSTEM_APPS = {"gnome-shell", "plasmashell", "xfdesktop", "unknown"}


def lock_screen() -> None:
    subprocess.Popen(["loginctl", "lock-session"])
