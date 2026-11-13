"""An installed app's icon, by its name, kept once found (a website's favicon the app asks the website for itself):

    icons(keys)   {key: a png data URL} for each app found here (macOS, Windows); the rest are left out

One not found is looked for again after a week.
"""

from __future__ import annotations

import asyncio
import base64
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from proki.settings import DATA_DIR

KEPT  = DATA_DIR / "icons"
AGAIN = 7 * 24 * 3600  # seconds before one not found is looked for again

_bundles: dict[str, Path] | None = None


def bundles() -> dict[str, Path]:
    """Each installed app's bundle, by every name it goes by (lower case)."""
    global _bundles
    if _bundles is not None:
        return _bundles
    found: dict[str, Path] = {}
    listed = subprocess.run(["mdfind", "kMDItemContentType == 'com.apple.application-bundle'"], capture_output=True, text=True, timeout=10).stdout
    for line in listed.splitlines():
        app = Path(line)
        try:
            info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
        except (OSError, plistlib.InvalidFileException, ValueError):
            continue
        for name in (app.stem, info.get("CFBundleName"), info.get("CFBundleDisplayName")):
            if isinstance(name, str) and name:
                found.setdefault(name.lower(), app)
    _bundles = found
    return found


# Windows: the program's file, from a running copy or else where it's registered, and its icon as a png
FROM_EXE = r"""
$n = $env:PROKI_APP
$p = (Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($n)) -ErrorAction SilentlyContinue | Where-Object Path | Select-Object -First 1).Path
foreach ($h in 'HKCU:', 'HKLM:') {
  $k = "$h\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\$n"
  if (-not $p -and (Test-Path $k)) { $p = (Get-ItemProperty $k).'(default)' }
}
if (-not $p) { exit 1 }
$p = $p.Trim('"')
if (-not (Test-Path $p)) { exit 1 }
Add-Type -AssemblyName System.Drawing
$m = New-Object IO.MemoryStream
[Drawing.Icon]::ExtractAssociatedIcon($p).ToBitmap().Save($m, [Drawing.Imaging.ImageFormat]::Png)
[Convert]::ToBase64String($m.ToArray())
"""


def of_exe(key: str) -> bytes | None:
    """A Windows program's icon, by its file name ("Code.exe"), as a 32px png (None: not found here)."""
    done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", FROM_EXE], capture_output=True, text=True, timeout=20,
                          env={**os.environ, "PROKI_APP": key}, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        return base64.b64decode(done.stdout.strip(), validate=True) if done.returncode == 0 and done.stdout.strip() else None
    except ValueError:
        return None


def of_app(key: str) -> bytes | None:
    """An app's icon as a 32px png (None: not installed here)."""
    if sys.platform == "win32":
        return of_exe(key)
    if (app := bundles().get(key.lower())) is None:
        return None
    try:
        info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    named = str(info.get("CFBundleIconFile") or info.get("CFBundleIconName") or "AppIcon")
    icns  = app / "Contents" / "Resources" / (named if named.endswith(".icns") else f"{named}.icns")
    if not icns.is_file():
        return None
    with tempfile.TemporaryDirectory() as room:
        out  = Path(room) / "icon.png"
        done = subprocess.run(["sips", "-s", "format", "png", "-Z", "32", str(icns), "--out", str(out)], capture_output=True, timeout=10)
        return out.read_bytes() if done.returncode == 0 and out.is_file() else None


def found(key: str) -> str | None:
    """`key`'s icon as a data URL, looked for once and kept (None: it has none)."""
    KEPT.mkdir(parents=True, exist_ok=True)
    file = KEPT / re.sub(r"[^\w.-]", "_", key)
    if file.exists() and (file.stat().st_size or time.time() - file.stat().st_mtime < AGAIN):
        image = file.read_bytes()
    else:
        image = of_app(key) or b""
        file.write_bytes(image)  # empty: none, looked for again after a while
    return f"data:image/png;base64,{base64.b64encode(image).decode()}" if image else None


async def icons(keys: list[str]) -> dict[str, str]:
    """Each key's icon as a data URL; a key with none is left out."""
    if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
        raise ValueError(f"keys is a list of app names ({keys!r})")
    if sys.platform not in ("darwin", "win32"):
        return {}
    def look() -> dict[str, str]:
        if sys.platform == "darwin":  bundles()  # once, before the threads
        with ThreadPoolExecutor(8) as pool:
            return {k: url for k, url in zip(keys, pool.map(found, keys)) if url}
    return await asyncio.to_thread(look)
