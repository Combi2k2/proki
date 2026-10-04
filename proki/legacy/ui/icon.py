"""proki's menu-bar icon: a sniper scope whose outer ring shows progress toward
today's deep-work goal.

Drawn in code (so it stays sharp and can change live) in black on transparent,
and marked as a mask so macOS treats it as a template image that adapts to
light and dark menu bars. All coordinates are in points on a 22 × 22 canvas.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

SIZE = 22  # points; the menu bar height on macOS
CENTER = QPointF(11.0, 11.0)
RADIUS = 8.0

FAINT = QColor(0, 0, 0, 80)
SOLID = QColor(0, 0, 0, 255)


def scope_icon(progress: float, scale: int = 2) -> QIcon:
    icon = QIcon(scope_pixmap(progress, scale))
    icon.setIsMask(True)
    return icon


def scope_pixmap(progress: float, scale: int = 2) -> QPixmap:
    pixmap = QPixmap(SIZE * scale, SIZE * scale)
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _ring(painter, progress)
    _crosshair(painter, done=progress >= 1)
    painter.end()
    return pixmap


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def _ring(painter: QPainter, progress: float) -> None:
    box = QRectF(CENTER.x() - RADIUS, CENTER.y() - RADIUS, 2 * RADIUS, 2 * RADIUS)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(_pen(FAINT, 1.6))
    painter.drawEllipse(box)
    if progress > 0:
        painter.setPen(_pen(SOLID, 2.0))
        painter.drawArc(box, 90 * 16, -round(min(progress, 1.0) * 360 * 16))  # clockwise from the top


def _crosshair(painter: QPainter, done: bool) -> None:
    painter.setPen(_pen(SOLID, 1.3))
    cx, cy = CENTER.x(), CENTER.y()
    outer, inner = RADIUS - 0.8, 3.0  # ticks run from the ring inward, leaving the middle open
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        painter.drawLine(QPointF(cx + dx * outer, cy + dy * outer), QPointF(cx + dx * inner, cy + dy * inner))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(SOLID)
    dot = 1.9 if done else 0.9  # goal reached: the dot grows into a hit marker
    painter.drawEllipse(CENTER, dot, dot)
