from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from proki.legacy.ui.icon import scope_icon

SCOREBOARD_LINES = 14  # the day's numbers, shallow budget, block, chain, sessions, start time, 30-day test, tasks, sleep


class Tray:
    """Menu bar (macOS) / system tray (Windows, Linux) icon with the scoreboard."""

    def __init__(
        self,
        on_session: Callable[[], None],
        on_tasks: Callable[[], None],
        on_new_task: Callable[[], None],
        on_task_done: Callable[[], None],
        on_walk: Callable[[], None],
        on_grand: Callable[[], None],
        on_experiment: Callable[[], None],
        on_sprint: Callable[[], None],
        on_rate: Callable[[], None],
        on_snooze: Callable[[], None],
        on_settings: Callable[[], None],
        on_autostart: Callable[[bool], None],
        autostart_enabled: bool,
        on_quit: Callable[[], None],
    ):
        self._icon = QSystemTrayIcon(scope_icon(0))
        self._progress = 0.0
        self._menu = QMenu()
        self._status = self._info("proki: starting…")
        self._board = [self._info("") for _ in range(SCOREBOARD_LINES)]
        for line in self._board:
            line.setVisible(False)
        self._menu.addSeparator()
        self._session = self._add("Start focus session", on_session)
        self._add("Current task done → next", on_task_done)
        self._add("New task…", on_new_task)
        self._add("Sprint (beat the clock)…", on_sprint)
        self._add("Thinking walk…", on_walk)
        self._add("Grand gesture…", on_grand)
        self._add("30-day test…", on_experiment)
        self._add("Tasks…", on_tasks)
        self._add("Rate my focus now…", on_rate)
        self._add("Snooze nudges for 1 hour", on_snooze)
        self._menu.addSeparator()
        self._add("Open settings…", on_settings)
        autostart = self._add("Start at login", lambda: None)
        autostart.setCheckable(True)
        autostart.setChecked(autostart_enabled)
        autostart.toggled.connect(on_autostart)
        self._add("Quit proki", on_quit)
        self._icon.setContextMenu(self._menu)
        self._icon.setToolTip("proki")
        self._icon.show()

    def _info(self, text: str) -> QAction:
        action = self._menu.addAction(text)
        action.setEnabled(False)  # read-only line
        return action

    def _add(self, label: str, callback: Callable[[], None]) -> QAction:
        action = QAction(label, self._menu)
        action.triggered.connect(callback)
        self._menu.addAction(action)
        return action

    def set_status(self, text: str) -> None:
        self._status.setText(f"proki: {text}")
        self._icon.setToolTip(f"proki: {text}")

    def set_scoreboard(self, lines: list[str], progress: float) -> None:
        for i, action in enumerate(self._board):
            action.setVisible(i < len(lines))
            if i < len(lines):
                action.setText(lines[i])
        if round(progress, 2) != round(self._progress, 2):  # redraw only when it visibly changes
            self._progress = progress
            self._icon.setIcon(scope_icon(progress))

    def set_session(self, elapsed_minutes: int | None, countdown: str | None = None) -> None:
        """None = no session running. `countdown`: a sprint's time left, shown instead."""
        if elapsed_minutes is None:
            self._session.setText("Start focus session")
            self._icon.setToolTip("proki")
        elif countdown:
            self._session.setText(f"Stop sprint  ({countdown})")
            self._icon.setToolTip(f"proki · sprint: {countdown}")
        else:
            self._session.setText(f"Stop focus session  ({elapsed_minutes} min)")

    def notify(self, title: str, message: str) -> None:
        self._icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)
