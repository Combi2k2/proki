"""Start at login through the per-user registry Run key. Not yet tested.

A Windows Service would not work here: services run in an isolated session
and cannot show tray icons or popups.
"""

import os
import subprocess
import winreg
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "proki"
ACTIVITYWATCH_DIRS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ActivityWatch",
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "ActivityWatch",
]
EXECUTABLE_SUFFIX = ".exe"
NATS_DIRS = [
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "nats-server",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nats-server",
    Path.home() / "go" / "bin",
]

# the browsers, as ActivityWatch names them (the program's file name)
BROWSER_APPS = {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "vivaldi.exe", "opera.exe"}

# the lock screen / screen saver: time on it is time away
LOCK_APPS = {"LockApp.exe"}

# system windows that come and go on their own. Never worth a question
SYSTEM_APPS = {
    "LockApp.exe", "SearchHost.exe", "SearchApp.exe", "ShellExperienceHost.exe",
    "StartMenuExperienceHost.exe", "ApplicationFrameHost.exe", "explorer.exe", "Taskmgr.exe",
}


def install_autostart(command: list[str]) -> None:
    # pythonw.exe: the same Python without a console window
    pythonw = Path(command[0]).with_name("pythonw.exe")
    if Path(command[0]).name.lower() == "python.exe" and pythonw.exists():
        command = [str(pythonw), *command[1:]]
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))


def uninstall_autostart() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, NAME)
    except FileNotFoundError:
        pass


def autostart_installed() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, NAME)
        return True
    except FileNotFoundError:
        return False


def lock_screen() -> None:
    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])


def close_tab(app: str, url: str) -> bool:
    return False  # not supported yet


def close_window(app: str, title: str) -> bool:
    return False  # not supported yet
