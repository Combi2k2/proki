@echo off
rem proki for Windows: double-click to install (first time), update, and start proki.
rem Everything below the PowerShell marker is run by PowerShell.
title proki
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (Get-Content -Raw -LiteralPath '%~f0') -split ('#' + 'POWERSHELL#'); Invoke-Expression $s[1]"
if errorlevel 1 (
  echo.
  echo Something went wrong. Please send a screenshot of this window.
  pause
)
exit /b

#POWERSHELL#
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # much faster downloads
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = "https://github.com/Combi2k2/proki/archive/refs/heads/main.zip"
$Root = Join-Path $env:LOCALAPPDATA "proki-app"      # proki's program files (your data lives elsewhere)
$Source = Join-Path $Root "proki"
$Venv = Join-Path $Root "venv"
$AWDir = Join-Path $env:LOCALAPPDATA "Programs\ActivityWatch"
$Temp = Join-Path $env:TEMP "proki-install"

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }

New-Item -ItemType Directory -Force -Path $Root | Out-Null
if (Test-Path $Temp) { Remove-Item -Recurse -Force $Temp }
New-Item -ItemType Directory -Force -Path $Temp | Out-Null

# 1. Stop a running proki (its files can't be replaced while it runs)
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*-m proki*" } |
    ForEach-Object { Step "Stopping the running proki"; Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }

# 2. uv: installs Python and proki's libraries
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Step "Installing uv (Python package manager)"
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 3. ActivityWatch: records which window is in use (proki starts it itself)
$awInstalled = (Test-Path (Join-Path $AWDir "aw-server\aw-server.exe")) -or
               (Test-Path (Join-Path $env:ProgramFiles "ActivityWatch\aw-server\aw-server.exe"))
if (-not $awInstalled) {
    Step "Downloading ActivityWatch"
    $release = Invoke-RestMethod https://api.github.com/repos/ActivityWatch/activitywatch/releases/latest
    $asset = $release.assets | Where-Object { $_.name -like "*windows-x86_64.zip" } | Select-Object -First 1
    if (-not $asset) { throw "Couldn't find ActivityWatch's Windows download." }
    $zip = Join-Path $Temp "activitywatch.zip"
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    Expand-Archive $zip -DestinationPath (Join-Path $Temp "aw")
    $folder = Get-ChildItem (Join-Path $Temp "aw") -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force -Path (Split-Path $AWDir) | Out-Null
    if (Test-Path $AWDir) { Remove-Item -Recurse -Force $AWDir }
    Move-Item $folder.FullName $AWDir
}

# 4. proki itself: the latest version from GitHub
Step "Downloading the latest proki"
$zip = Join-Path $Temp "proki.zip"
Invoke-WebRequest $Repo -OutFile $zip
Expand-Archive $zip -DestinationPath (Join-Path $Temp "proki")
if (Test-Path $Source) { Remove-Item -Recurse -Force $Source }
Move-Item (Get-ChildItem (Join-Path $Temp "proki") -Directory | Select-Object -First 1).FullName $Source

Step "Installing Python and proki's libraries (the first time takes a few minutes)"
$env:UV_PROJECT_ENVIRONMENT = $Venv
uv sync --directory $Source --no-dev --python 3.12
if ($LASTEXITCODE -ne 0) { throw "Installing proki's libraries failed." }
$Python = Join-Path $Venv "Scripts\python.exe"
$PythonW = Join-Path $Venv "Scripts\pythonw.exe"

# 5. First time: settings file and API keys
$ConfigDir = & $Python -c "from proki.config import CONFIG_PATH; print(CONFIG_PATH.parent)"
$EnvFile = Join-Path $ConfigDir ".env"
if (-not (Test-Path $EnvFile)) {
    Step "API keys (optional: press Enter to skip; proki then asks you everything itself)"
    $jev = Read-Host "openjev (jev) API key"
    $gemini = Read-Host "Gemini API key (free at https://aistudio.google.com/apikey)"
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
    Set-Content -Path $EnvFile -Encoding ascii -Value @("JEV_KEY=$jev", "JEV_URL=https://api.openjev.sh/v1/systemone", "JEV_MODEL=openjev", "GEMINI_API_KEY=$gemini")
    & $Python -c "from proki.config import load; load()"   # creates the settings file with the defaults
    if ($jev) {   # turn jev on in the settings (Python edits it, keeping the file's encoding right)
        $script = Join-Path $Temp "enable_jev.py"
        Set-Content -Path $script -Encoding ascii -Value @'
import re
from proki.config import CONFIG_PATH as p
text = p.read_text(encoding="utf-8")
text = re.sub(r"(\[jev\][\s\S]*?)^enabled = false", r"\1enabled = true", text, count=1, flags=re.M)
p.write_text(text, encoding="utf-8")
'@
        & $Python $script
    }
}

# 6. A desktop shortcut, then start proki (it appears in the taskbar's hidden icons, next to the clock)
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "proki.lnk"))
$link.TargetPath = $PythonW
$link.Arguments = "-m proki"
$link.WorkingDirectory = $Root
$link.Description = "proki: procrastination killer"
$link.Save()

Step "Starting proki"
Start-Process -FilePath $PythonW -ArgumentList "-m", "proki" -WorkingDirectory $Root
Remove-Item -Recurse -Force $Temp -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "proki is running: look for its icon next to the clock (click ^ if it's hidden)." -ForegroundColor Green
Write-Host "Next time, start it from the 'proki' shortcut on the desktop. Run this file again to update."
Write-Host "Log file: $env:LOCALAPPDATA\proki\proki\Logs\proki.log"
Start-Sleep -Seconds 8
