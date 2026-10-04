"""Run ActivityWatch's background programs instead of its tray app.

ActivityWatch's tray app (aw-qt) only starts a few programs and shows an icon.
proki does the same from its own tray icon: start the server and watchers, restart
crashes, and stop them on quit. If ActivityWatch is already running, proki leaves it
alone, unless those are programs proki started in an earlier run that ended without
cleaning up; proki remembers their process ids and takes them over.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from proki.utils import wait_until, wait_while


class ActivityWatchSupervisor:
    def __init__(
        self,
        commands: dict[str, list[str]],
        healthy: Callable[[], bool],
        log_dir: Path,
        timeout: float = 10.0,
    ):
        self.processes: dict[str, subprocess.Popen] = {}
        self.commands = commands
        self.healthy = healthy
        self.timeout = timeout
        self.log_dir = log_dir
        self.pid_file = log_dir / "pids"
        self.external = False

    def clean(self) -> bool:
        """Stop programs a previous proki run started but never stopped."""
        if not self.pid_file.exists():
            return False
        found = False
        win32 = sys.platform == "win32"

        for line in self.pid_file.read_text().split():
            if not line.isdigit():
                continue  # a damaged file: skip what isn't a pid
            pid = int(line)
            if win32:   command = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
            else:       command = ["ps", "-o", "command=", "-p", str(pid)]
            try:
                output = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                ).stdout
                if win32:   ours = any(Path(cmd[0]).name.lower() in output.lower() for cmd in self.commands.values())
                else:       ours = any(cmd[0] in output for cmd in self.commands.values())
                if ours:
                    os.kill(pid, signal.SIGTERM)
                    found = True
            except OSError:
                pass
        self.pid_file.unlink()
        return found

    def start(self) -> str:
        """Start everything; returns a short status for the tray."""
        if self.clean():    wait_while(self.healthy, self.timeout)
        if self.healthy():
            self.external = True
            return "ActivityWatch already running (not managed by proki)"

        for module in sorted(self.commands, key=lambda module: module != "aw-server"):  # server first
            self._launch(module)
            if module == "aw-server":
                wait_until(self.healthy, self.timeout)
                if not self.healthy():
                    self.stop()
                    return "ActivityWatch server failed to start"

        self._save_pids()
        return "ActivityWatch started by proki"

    def check(self) -> list[str]:
        """Restart any module that has stopped; returns the names restarted."""
        if self.external:
            return []
        restarted = []
        for module, process in self.processes.items():
            if process.poll() is not None:
                self._launch(module)
                restarted.append(module)
        if restarted:
            self._save_pids()
        return restarted

    def stop(self) -> None:
        """Stop the modules proki started, watchers first and the server last."""
        for module in reversed(list(self.processes)):
            process = self.processes.pop(module)
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        self.pid_file.unlink(missing_ok=True)

    def _save_pids(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text("\n".join(str(p.pid) for p in self.processes.values()))

    def _launch(self, module: str) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with (self.log_dir / f"{module}.log").open("ab") as log:
            self.processes[module] = subprocess.Popen(
                self.commands[module],
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
