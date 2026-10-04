"""The task window: all open tasks by goal group, steps under their task.

It shows what's been done today (never what's "left"), and has buttons for new,
edit, break down, done and remove. Right-click a group to set its priority.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QMenu, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from proki.legacy.core.backlog import Group, Task, due_text, minutes_text, urgency, workable

ROLE = Qt.ItemDataRole.UserRole


class TaskBoard(QWidget):
    def __init__(
        self,
        on_new: Callable[[], None],
        on_edit: Callable[[Task], None],
        on_breakdown: Callable[[Task], None],
        on_done: Callable[[Task], None],
        on_remove: Callable[[Task], None],
        on_priority: Callable[[Group, str], None],
    ):
        super().__init__(None, Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)  # see ui/popup.py
        self.setWindowTitle("proki: tasks")
        self._on_priority = on_priority
        self.done_today = QLabel()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Task", "Estimate", "Deadline"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.itemDoubleClicked.connect(lambda item, _: self._with_task(on_edit))

        buttons = QHBoxLayout()
        for label, handler in [
            ("+ New task", lambda: on_new()),
            ("Edit…", lambda: self._with_task(on_edit)),
            ("Break down…", lambda: self._with_task(on_breakdown)),
            ("Done ✓", lambda: self._with_task(on_done)),
            ("Remove", lambda: self._with_task(on_remove)),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.done_today)
        layout.addWidget(self.tree)
        layout.addLayout(buttons)
        self.resize(640, 460)

    def open(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.top() + 60)
        self.show()
        self.raise_()
        self.activateWindow()

    def refresh(self, groups: list[Group], tasks: list[Task], today: date, now, done_today: int, deep_minutes: int) -> None:
        self.done_today.setText(
            f"<b>Done today:</b> {done_today} task{'s' if done_today != 1 else ''} · {minutes_text(deep_minutes)} of deep work"
        )
        self.tree.clear()
        bold = QFont()
        bold.setBold(True)
        sections = [(g, [t for t in tasks if t.group_id == g.id]) for g in groups]
        ungrouped = [t for t in tasks if t.group_id is None or t.group_id not in {g.id for g in groups}]
        if ungrouped:
            sections.append((None, ungrouped))
        # most urgent group first
        sections.sort(key=lambda s: -urgency(s[1], now))
        for group, members in sections:
            if not members:
                continue
            remaining = sum(t.estimate for t in workable(members))
            deadlines = [t.deadline for t in workable(members) if t.deadline]
            header = QTreeWidgetItem([
                (group.name if group else "No group") + (f"  ({group.priority})" if group and group.priority != "normal" else ""),
                minutes_text(remaining),
                due_text(min(deadlines), today) if deadlines else "",
            ])
            header.setData(0, ROLE, ("group", group))
            for col in range(3):
                header.setFont(col, bold)
            self.tree.addTopLevelItem(header)
            by_parent: dict[int | None, list[Task]] = {}
            for t in members:
                by_parent.setdefault(t.parent_id if t.parent_id in {m.id for m in members} else None, []).append(t)
            self._add_children(header, None, by_parent, today)
            header.setExpanded(True)

    def _add_children(self, parent_item, parent_id, by_parent, today) -> None:
        for task in sorted(by_parent.get(parent_id, []), key=lambda t: (t.deadline or date.max, t.position)):
            item = QTreeWidgetItem([task.title + (f"  · {task.kind}" if task.kind else ""),
                                    minutes_text(task.estimate), due_text(task.deadline, today)])
            item.setData(0, ROLE, ("task", task))
            if task.description:
                item.setToolTip(0, task.description)
            parent_item.addChild(item)
            self._add_children(item, task.id, by_parent, today)
            item.setExpanded(True)

    def _selected(self):
        item = self.tree.currentItem()
        return item.data(0, ROLE) if item else None

    def _with_task(self, action: Callable[[Task], None]) -> None:
        selected = self._selected()
        if selected and selected[0] == "task":
            action(selected[1])

    def _context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        data = item.data(0, ROLE) if item else None
        if not data or data[0] != "group" or data[1] is None:
            return
        group = data[1]
        menu = QMenu(self)
        for priority in ("high", "normal", "low"):
            action = menu.addAction(f"Priority: {priority}" + ("  ✓" if group.priority == priority else ""))
            action.triggered.connect(lambda _=False, p=priority: self._on_priority(group, p))
        menu.exec(self.tree.viewport().mapToGlobal(pos))
