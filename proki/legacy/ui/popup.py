from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QGridLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget


BUTTONS_PER_ROW = 4
NUDGE_OPTIONS = [("Got it", "ok"), ("Snooze 30 min", "snooze"), ("Dismiss", "dismissed")]


class Popup(QWidget):
    """Small floating panel in the top-right corner that asks for a response."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        # proki is a background app that is never "active"; without these, macOS
        # hides tool windows of inactive apps, and showing one would steal focus.
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._on_response: Callable[[str], None] | None = None
        self._label = QLabel(wordWrap=True)
        self._buttons = QGridLayout()  # wraps onto more rows when there are many choices
        self._text = QLineEdit()  # only for questions answered by typing
        self._text.returnPressed.connect(lambda: self._respond("submit") if self._text.text().strip() else None)
        self._text.setVisible(False)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._text)
        layout.addLayout(self._buttons)
        self.setFixedWidth(420)

    def ask(
        self,
        message: str,
        on_response: Callable[[str], None],
        options: list[tuple[str, str]] = NUDGE_OPTIONS,
    ) -> None:
        """Show `message` with one button per (label, response) option."""
        self._text.setVisible(False)
        self._show(message, on_response, options)

    def ask_text(
        self,
        message: str,
        on_text: Callable[[str | None], None],
        placeholder: str = "",
        skip_label: str = "Skip",
        text: str = "",
    ) -> None:
        """Show `message` with a text field (Enter or "Save" submits); on_text gets the text, or None on skip."""
        self._text.setText(text)
        self._text.setPlaceholderText(placeholder)
        self._text.setVisible(True)

        def respond(response: str) -> None:
            text = self._text.text().strip()
            on_text(text if response == "submit" and text else None)

        self._show(message, respond, [("Save", "submit"), (skip_label, "skip")])

    def _show(self, message: str, on_response: Callable[[str], None], options: list[tuple[str, str]]) -> None:
        self._label.setText(message)
        self._on_response = on_response
        while self._buttons.count():
            self._buttons.takeAt(0).widget().deleteLater()
        per_row = BUTTONS_PER_ROW if len(options) > BUTTONS_PER_ROW else max(len(options), 1)
        for i, (text, response) in enumerate(options):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, r=response: self._respond(r))
            self._buttons.addWidget(button, i // per_row, i % per_row)
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 16, screen.top() + 16)
        self.show()
        self.raise_()

    def _respond(self, response: str) -> None:
        self.hide()
        if self._on_response:
            self._on_response(response)
