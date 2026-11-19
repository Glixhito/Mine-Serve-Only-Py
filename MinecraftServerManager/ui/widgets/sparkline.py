"""Gráfica de línea con relleno degradado suave (QPainter). No requiere librerías externas."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget


class Sparkline(QWidget):
    def __init__(self, title: str, fixed_max: float | None = None,
                 accent: str = "#3fb950", unit: str = "") -> None:
        super().__init__()
        self._title = title
        self._fixed_max = fixed_max
        self._accent = QColor(accent)
        self._unit = unit
        self._values: list[float] = []
        self.setMinimumHeight(155)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_values(self, values: list[float]) -> None:
        self._values = list(values)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        painter.fillRect(rect, QColor("#14161a"))

        # Cabecera interna
        painter.setPen(QColor("#a0a8b4"))
        painter.drawText(14, 22, self._title)
        if self._values:
            val_text = f"Actual: {self._values[-1]:.1f}{self._unit}"
            painter.setPen(self._accent)
            painter.drawText(QRectF(14, 8, rect.width() - 28, 20),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val_text)

        area = QRectF(14, 34, max(rect.width() - 28, 10), max(rect.height() - 48, 10))

        # Líneas guía horizontales
        grid_pen = QPen(QColor("#2a2f3a"), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for step_y in (0.0, 0.33, 0.66, 1.0):
            y = area.top() + area.height() * step_y
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))

        if len(self._values) >= 2:
            top = self._fixed_max or max(max(self._values) * 1.15, 1.0)
            step = area.width() / (len(self._values) - 1)
            points = [
                QPointF(area.left() + i * step,
                        area.bottom() - min(v / top, 1.0) * area.height())
                for i, v in enumerate(self._values)
            ]

            # Área degradada bajo la curva
            fill_path = QPainterPath()
            fill_path.moveTo(points[0].x(), area.bottom())
            for pt in points:
                fill_path.lineTo(pt)
            fill_path.lineTo(points[-1].x(), area.bottom())
            fill_path.closeSubpath()

            grad = QLinearGradient(0, area.top(), 0, area.bottom())
            top_color = QColor(self._accent)
            top_color.setAlpha(65)
            bot_color = QColor(self._accent)
            bot_color.setAlpha(0)
            grad.setColorAt(0.0, top_color)
            grad.setColorAt(1.0, bot_color)
            painter.fillPath(fill_path, grad)

            # Línea principal
            painter.setPen(QPen(self._accent, 2))
            painter.drawPolyline(QPolygonF(points))

            # Punto final brillante
            painter.setBrush(self._accent)
            painter.setPen(QPen(QColor("#0f1115"), 1.5))
            painter.drawEllipse(points[-1], 3.5, 3.5)
        else:
            painter.setPen(QColor("#677484"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "Esperando muestras en tiempo real…")

        painter.end()