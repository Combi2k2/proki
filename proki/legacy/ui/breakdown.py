"""Break a task into steps, each doable in one focus session. The user writes (or
edits the AI's suggested) steps; the task becomes the parent of those steps."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from proki.legacy.core.backlog import SESSION_MINUTES, Task, minutes_text
from proki.legacy.ui.background import Background

Suggest = Callable[[], "list[str] | None"]
SaveSteps = Callable[[Task, list[tuple[str, int]]], None]

REASONS = {
    "too_long": "This is more than one focus session ({estimate}). Break it into steps you can each finish "
                "in one session (up to 50 min).",
    "vague": "This is hard to size: it's not clear what exactly it involves or when it's done. "
             "Break it into concrete steps.",
}


class BreakdownDialog(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)  # see ui/popup.py
        self.setWindowTitle("proki: break down")
        self.background = Background(self)
        self._task: Task | None = None
        self._on_save: SaveSteps | None = None
        self._rows: list[tuple[QLineEdit, QSpinBox, QPushButton]] = []

        self.heading = QLabel(wordWrap=True)
        self.hint = QLabel(wordWrap=True)
        self.hint.setStyleSheet("color: gray")
        self.grid = QGridLayout()
        self.grid.addWidget(QLabel("<b>Step</b>"), 0, 0)
        self.grid.addWidget(QLabel("<b>Estimate</b>"), 0, 1)
        add = QPushButton("+ Add step")
        add.clicked.connect(lambda: self._add_row("", 30))
        self.message = QLabel(wordWrap=True)
        save, keep = QPushButton("Save steps"), QPushButton("Keep as one task")
        save.setDefault(True)
        save.clicked.connect(self._save)
        keep.clicked.connect(self.hide)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addStretch()
        buttons.addWidget(keep)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.addWidget(self.heading)
        layout.addWidget(self.hint)
        layout.addLayout(self.grid)
        layout.addWidget(self.message)
        layout.addLayout(buttons)
        self.setFixedWidth(520)

    def open(self, task: Task, reason: str, suggest: Suggest | None, on_save: SaveSteps) -> None:
        self._task, self._on_save = task, on_save
        for title, estimate, remove in self._rows:
            for w in (title, estimate, remove):
                w.deleteLater()
        self._rows = []
        self.heading.setText(f"<b>{task.title}</b><br>" + REASONS[reason].format(estimate=minutes_text(task.estimate)))
        self.message.setText("")
        self._add_row("", 30)
        if suggest:
            self.hint.setText("proki is suggesting possible steps…")
            self.background.run(suggest, self._got_suggestions)
        else:
            self.hint.setText("Write the steps below, one per row.")
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - 260, screen.top() + 100)
        self.show()
        self.raise_()
        self.activateWindow()

    def _got_suggestions(self, steps: list[str] | None) -> None:
        if not steps:
            self.hint.setText("No suggestions available right now. Write the steps below, one per row.")
            return
        self.hint.setText("Suggested steps: edit, remove or add your own. You decide.")
        if len(self._rows) == 1 and not self._rows[0][0].text():
            self._remove_row(self._rows[0])
        per_step = max(5, min(SESSION_MINUTES, round((self._task.estimate / len(steps)) / 5) * 5))
        for step in steps:
            self._add_row(step, per_step)

    def _add_row(self, text: str, minutes: int) -> None:
        title = QLineEdit(text, placeholderText="A concrete step")
        estimate = QSpinBox(minimum=5, maximum=600, singleStep=5, suffix=" min", value=minutes)
        remove = QPushButton("✕")
        remove.setFixedWidth(32)
        row = (title, estimate, remove)
        remove.clicked.connect(lambda: self._remove_row(row))
        r = len(self._rows) + 1
        self.grid.addWidget(title, r, 0)
        self.grid.addWidget(estimate, r, 1)
        self.grid.addWidget(remove, r, 2)
        self._rows.append(row)
        title.setFocus()

    def _remove_row(self, row) -> None:
        self._rows.remove(row)
        for w in row:
            w.deleteLater()

    def _save(self) -> None:
        steps = [(t.text().strip(), e.value()) for t, e, _ in self._rows if t.text().strip()]
        if not steps:
            self.message.setText("Add at least one step, or keep it as one task.")
            return
        too_long = [s for s, m in steps if m > SESSION_MINUTES]
        if too_long:
            self.message.setText(f"“{too_long[0]}” is over 50 minutes: split it further.")
            return
        self.hide()
        if self._on_save:
            self._on_save(self._task, steps)
