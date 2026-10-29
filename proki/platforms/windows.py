"""Windows: where ActivityWatch and NATS are installed, which apps are browsers or the
system's, and locking the screen. Not yet tested.
"""

import os
import subprocess
from pathlib import Path

AW_DIRS   = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ActivityWatch",
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "ActivityWatch",
]
NATS_DIRS = [
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "nats-server",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nats-server",
    Path.home() / "go" / "bin",
]
EXE  = ".exe"

# the browsers, as ActivityWatch names them (the program's file name)
BROWSER_APPS = {
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "firefox.exe",
    "vivaldi.exe",
    "opera.exe"
}

# system windows that come and go on their own. Never worth a question
SYSTEM_APPS = {
    "LockApp.exe",
    "SearchHost.exe",
    "SearchApp.exe",
    "ShellExperienceHost.exe",
    "StartMenuExperienceHost.exe",
    "ApplicationFrameHost.exe",
    "explorer.exe",
    "Taskmgr.exe",
}


def lock_screen() -> None:
    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
