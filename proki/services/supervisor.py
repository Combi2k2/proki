"""A service's programs, run by proki: no tray app or launcher of its own needed.

    sup = Supervisor("NATS", {"server": [...], "client": [...]}, healthy, log_dir)
    sup.start()     the server first, the others once it's up: a short status for the tray
    sup.check()     the ones that stopped, started again: their names
    sup.stop()      all of them, the server last

A service already running is left alone, unless proki started it last time and didn't stop
it: then it's started again. Each program's output goes to its log in `log_dir`.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from proki.utils import (
    wait_until,
    wait_while
)

class Supervisor:
    def __init__(
        self,
        name: str,
        commands: dict[str, list[str]],
        healthy: Callable[[], bool],
        log_dir: Path,
        timeout: float = 10.0,
    ):
        self.name = name  # for the status: "ActivityWatch", "NATS", ...
        self.commands = commands  # each module's command line, by module name, the server first
        self.healthy = healthy  # whether the service answers
        self.timeout = timeout
        self.log_dir = log_dir
        self.pid_file = log_dir / "pids"
        self.processes: dict[str, subprocess.Popen] = {}
        self.external = False  # already running, not started here

    def clean(self) -> bool:
        """Stop what an earlier run started and never stopped: whether there was any."""
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
        """Start them all, the server first: a short status for the tray."""
        if self.clean():    wait_while(self.healthy, self.timeout)
        if self.healthy():
            self.external = True
            return f"{self.name} already running (not managed by proki)"

        server = next(iter(self.commands))
        for module in self.commands:
            self._launch(module)
            if module == server:
                wait_until(self.healthy, self.timeout)
                if not self.healthy():
                    self.stop()
                    return f"{self.name} server failed to start"

        self._save_pids()
        return f"{self.name} started by proki"

    def check(self) -> list[str]:
        """Start again the ones that stopped: their names."""
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
        """Stop the ones started here, the server last."""
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
