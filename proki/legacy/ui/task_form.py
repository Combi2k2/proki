"""New / edit task: title, description, deadline, your estimate, goal group.

On save, openjev checks the task (in the background). If its size estimate is far
from yours, you're asked once to double-check (yours stays the one that counts).
Then the task is saved, and if it isn't atomic (vague, or over one 50-minute
session) the break-down dialog opens.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from proki.legacy.core.backlog import Assessment, Task, breakdown_reason, estimate_mismatch, minutes_text
from proki.legacy.ui.background import Background

PRIORITIES = ["high", "normal", "low"]

# what the form needs from the app; all may be slow and are run in the background
Assess = Callable[[str], "Assessment | None"]
SuggestGroup = Callable[[str, list[str]], "str | None"]
Saved = Callable[[dict, "Assessment | None", "str | None"], None]  # fields, assessment, breakdown reason


class TaskForm(QWidget):
    def __init__(self, assess: Assess | None, suggest_group: SuggestGroup | None):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)  # see ui/popup.py
        self.assess, self.suggest_group = assess, suggest_group
        self.background = Background(self)
        self._on_saved: Saved | None = None
        self._editing: Task | None = None
        self._confirmed_estimate = False
        self._group_touched = False

        self.title = QLineEdit(placeholderText="What needs to be done?")
        self.description = QPlainTextEdit(placeholderText="Details: which part, how much, what counts as done (optional)")
        self.description.setFixedHeight(70)
        self.deadline = QDateEdit(calendarPopup=True, displayFormat="ddd d MMM yyyy")
        self.estimate = QSpinBox(minimum=5, maximum=6000, singleStep=5, suffix=" min")
        self.group = QComboBox(editable=True)
        self.group.lineEdit().setPlaceholderText("Goal, e.g. Statistics final")
        self.priority = QComboBox()
        self.priority.addItems(PRIORITIES)
        self.priority.setCurrentText("normal")
        self.group_hint = QLabel(wordWrap=True)
        self.group_hint.setStyleSheet("color: gray")
        self.message = QLabel(wordWrap=True)

        form = QFormLayout()
        form.addRow("Task", self.title)
        form.addRow("Description", self.description)
        form.addRow("Deadline", self.deadline)
        form.addRow("Your estimate", self.estimate)
        form.addRow("Goal group", self.group)
        form.addRow("", self.group_hint)
        form.addRow("Group priority", self.priority)

        self.save = QPushButton("Save")
        self.save.setDefault(True)
        self.keep = QPushButton("Keep my estimate")
        self.keep.setVisible(False)
        cancel = QPushButton("Cancel")
        self.save.clicked.connect(self._save)
        self.keep.clicked.connect(self._keep_estimate)
        cancel.clicked.connect(self.hide)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.keep)
        buttons.addWidget(self.save)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addLayout(buttons)
        self.setFixedWidth(500)

        self.title.editingFinished.connect(self._suggest_group)
        self.group.currentTextChanged.connect(self._group_changed)

    def open(self, groups: dict[str, str], default_deadline: date, on_saved: Saved, task: Task | None = None,
             group_name: str | None = None, title: str = "") -> None:
        """groups: name → priority. `task` set = edit an existing task; `title` prefills a new one."""
        self._on_saved, self._editing = on_saved, task
        self._groups = groups
        self._confirmed_estimate = task is not None  # don't re-ask about an estimate the user already kept
        self._group_touched = task is not None
        self.setWindowTitle("proki: edit task" if task else "proki: new task")
        self.group.blockSignals(True)
        self.group.clear()
        self.group.addItems(sorted(groups))
        self.group.setCurrentText(group_name or "")
        self.group.blockSignals(False)
        self.title.setText(task.title if task else title)
        self.description.setPlainText(task.description if task else "")
        d = (task.deadline if task and task.deadline else default_deadline)
        self.deadline.setDate(QDate(d.year, d.month, d.day))
        self.estimate.setValue(task.estimate if task else 30)
        self._group_changed(self.group.currentText())
        self._set_message("")
        self.keep.setVisible(False)
        self.save.setEnabled(True)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - 250, screen.top() + 80)
        self.show()
        self.raise_()
        self.activateWindow()
        self.title.setFocus()

    # --- group suggestion -----------------------------------------------------------

    def _suggest_group(self) -> None:
        text = self.title.text().strip()
        if not text or self._group_touched or not self.suggest_group:
            return
        self.group_hint.setText("suggesting a group…")
        self.background.run(lambda: self.suggest_group(text, sorted(self._groups)), self._got_group)

    def _got_group(self, name: str | None) -> None:
        if self._group_touched:
            return
        if name:
            self.group.blockSignals(True)
            self.group.setCurrentText(name)
            self.group.blockSignals(False)
            self._group_changed(name, suggested=True)
        else:
            self.group_hint.setText("Looks like a new goal: type a name for it.")

    def _group_changed(self, name: str, suggested: bool = False) -> None:
        if not suggested and self.isVisible():
            self._group_touched = True
        name = name.strip()
        known = name in self._groups
        self.priority.setEnabled(bool(name))
        if known:
            self.priority.setCurrentText(self._groups[name])
        if suggested:
            self.group_hint.setText("suggested by proki (change it if it's wrong)" + ("" if known else ": a new group"))
        else:
            self.group_hint.setText("" if known or not name else "new group")

    # --- saving ---------------------------------------------------------------------------

    def _fields(self) -> dict:
        d = self.deadline.date()
        return {
            "title": self.title.text().strip(),
            "description": self.description.toPlainText().strip(),
            "deadline": date(d.year(), d.month(), d.day()),
            "estimate": self.estimate.value(),
            "group": self.group.currentText().strip() or None,
            "priority": self.priority.currentText(),
            "task": self._editing,
        }

    def _save(self) -> None:
        fields = self._fields()
        if not fields["title"]:
            self._set_message("Give the task a title.")
            return
        self.save.setEnabled(False)
        self._set_message("checking the task…")
        text = fields["title"] + (f" ({fields['description']})" if fields["description"] else "")
        if self.assess is None:
            self._assessed(None)
        else:
            self.background.run(lambda: self.assess(text), self._assessed)

    def _assessed(self, assessment: Assessment | None) -> None:
        fields = self._fields()
        if not self._confirmed_estimate and estimate_mismatch(fields["estimate"], assessment):
            self._assessment = assessment
            self._set_message(
                f"openjev estimates about {minutes_text(assessment.minutes)} for this; you said "
                f"{minutes_text(fields['estimate'])}. Keep your estimate, or change it and save again."
            )
            self.keep.setVisible(True)
            self.save.setEnabled(True)
            self._confirmed_estimate = True  # asked once
            return
        self._finish(fields, assessment)

    def _keep_estimate(self) -> None:
        self._finish(self._fields(), getattr(self, "_assessment", None))

    def _finish(self, fields: dict, assessment: Assessment | None) -> None:
        self.hide()
        if self._on_saved:
            self._on_saved(fields, assessment, breakdown_reason(fields["estimate"], assessment))

    def _set_message(self, text: str) -> None:
        self.message.setText(text)
