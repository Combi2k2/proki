"""macOS: where ActivityWatch and NATS are installed, which apps are browsers or the system's,
and locking the screen."""

import subprocess
from pathlib import Path

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

# system windows that come and go on their own. Never worth a question
SYSTEM_APPS = {
    "loginwindow", "Dock", "SystemUIServer", "ControlCenter", "NotificationCenter",
    "UserNotificationCenter", "Spotlight", "ScreenSaverEngine", "SecurityAgent",
    "CoreServicesUIAgent", "universalAccessAuthWarn", "WindowManager", "Window Server",
}


def lock_screen() -> None:
    # Display sleep locks the Mac when "require password after sleep" is on (the default).
    subprocess.Popen(["pmset", "displaysleepnow"])
