"""Start at login with a LaunchAgent (from the next login on), restarted by launchd if it crashes."""

import plistlib
import subprocess
from pathlib import Path

from platformdirs import user_log_path

LABEL = "com.proki.agent"
ACTIVITYWATCH_DIRS = [
    Path("/Applications/ActivityWatch.app/Contents/MacOS"),
    Path.home() / "Applications" / "ActivityWatch.app" / "Contents" / "MacOS",
]
EXECUTABLE_SUFFIX = ""
NATS_DIRS = [Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path.home() / "go" / "bin"]  # Homebrew, go install

# the browsers, as ActivityWatch names them (the app's name)
BROWSER_APPS = {
    "Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium", "Vivaldi", "Arc",
    "Firefox", "Safari", "Opera",
}

# the lock screen / screen saver: time on it is time away
LOCK_APPS = {"loginwindow", "ScreenSaverEngine"}

# system windows that come and go on their own. Never worth a question
SYSTEM_APPS = {
    "loginwindow", "Dock", "SystemUIServer", "ControlCenter", "NotificationCenter",
    "UserNotificationCenter", "Spotlight", "ScreenSaverEngine", "SecurityAgent",
    "CoreServicesUIAgent", "universalAccessAuthWarn", "WindowManager", "Window Server",
}
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def install_autostart(command: list[str]) -> None:
    log = user_log_path("proki") / "proki.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(
        plistlib.dumps(
            {
                "Label": LABEL,
                "ProgramArguments": command,
                "RunAtLoad": True,
                "KeepAlive": {"SuccessfulExit": False},  # restart only after a crash
                "ProcessType": "Interactive",
                "StandardOutPath": str(log),
                "StandardErrorPath": str(log),
            }
        )
    )
    # Not loaded now: macOS loads LaunchAgents at the next login. Loading it
    # here would start a second proki next to the one that's running.


def uninstall_autostart() -> None:
    # Only unregister (effective from the next login). Unloading it now would
    # quit the proki that's running, if macOS started this one at login.
    PLIST.unlink(missing_ok=True)


def autostart_installed() -> bool:
    return PLIST.exists()


def lock_screen() -> None:
    # Display sleep locks the Mac when "require password after sleep" is on (the default).
    subprocess.Popen(["pmset", "displaysleepnow"])


# browsers whose tabs can be closed by AppleScript (Firefox has no AppleScript support)
_CHROMIUM = {"Google Chrome", "Brave Browser", "Microsoft Edge", "Chromium", "Vivaldi", "Arc"}


def _applescript_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def close_tab(app: str, url: str) -> bool:
    """Close the browser tab(s) showing `url`. False if it couldn't be done."""
    if app in _CHROMIUM:
        script = f"tell application {_applescript_string(app)} to close (every tab of every window whose URL is {_applescript_string(url)})"
    elif app == "Safari":
        script = f"tell application \"Safari\" to close (every tab of every window whose URL is {_applescript_string(url)})"
    else:
        return False
    return _osascript(script)


def close_window(app: str, title: str) -> bool:
    """Close the app's window with this title (apps that support AppleScript). False if it couldn't be done."""
    return _osascript(f"tell application {_applescript_string(app)} to close (every window whose name is {_applescript_string(title)})")


def _osascript(script: str) -> bool:
    # the first time, macOS asks the user to allow proki to control that app
    try:
        return subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
