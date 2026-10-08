"""Running the programs proki's services need, so their own tray apps or launchers aren't:
ActivityWatch's server and watchers, the NATS server.

A `Supervisor` runs a service's programs (its "modules": ActivityWatch has a server and a
few watchers, NATS just its server), found with `find_commands` (proki/utils.py). The first
module is the server, the one the others need up first:

    start()   start them, the server first, the others once `healthy()` says it's up.
              Returns a short status for the tray
    check()   restart any that stopped. Returns their names
    stop()    stop them, the server last

If the service is already running (`healthy()` before proki starts anything), proki leaves
it alone, unless those are programs proki started in an earlier run that ended without
cleaning up: proki remembers their process ids (a pid file in `log_dir`) and takes them over.
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
        self.name = name  # for the status: "ActivityWatch", "NATS"
        self.commands = commands  # each module's command line, by module name, the server first
        self.healthy = healthy  # whether the service answers
        self.timeout = timeout
        self.log_dir = log_dir
        self.pid_file = log_dir / "pids"
        self.processes: dict[str, subprocess.Popen] = {}
        self.external = False  # already running, not started by proki

    def clean(self) -> bool:
        """Stop the modules a previous proki run started but never stopped."""
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
        """Start every module, the server first. Returns a short status for the tray."""
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
        """Restart any module that has stopped. Returns the names restarted."""
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
        """Stop the modules proki started, the server last."""
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
