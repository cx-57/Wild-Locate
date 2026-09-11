from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap, QIcon
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


def label(text, role="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget


def divider():
    widget = QFrame()
    widget.setObjectName("divider")
    return widget


def draw_mark(painter, size):
    painter.save()
    painter.scale(size / 40, size / 40)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#254f38"))
    painter.drawRoundedRect(QRectF(0, 0, 40, 40), 11, 11)
    path = QPainterPath(QPointF(12, 28))
    path.cubicTo(5, 12, 22, 10, 30, 9)
    path.cubicTo(31, 24, 25, 32, 12, 28)
    painter.setBrush(QColor("#d4e2b5"))
    painter.drawPath(path)
    painter.setPen(QPen(QColor("#254f38"), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(12, 29), QPointF(24, 17))
    painter.restore()


def app_icon():
    pixmap = QPixmap(80, 80)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    draw_mark(painter, 80)
    painter.end()
    return QIcon(pixmap)


class BrandMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(36, 36)

    def paintEvent(self, event):
        painter = QPainter(self)
        draw_mark(painter, 36)


class SuitabilityGauge(QWidget):
    COLORS = ("#e1e6d9", "#c9d6af", "#a5bb7c", "#708f4c", "#345e3c")

    def __init__(self):
        super().__init__()
        self.percentile = None
        self.setMinimumHeight(72)
        self.setToolTip("Percentile categories: 0–19 Very Low; 20–39 Low; 40–59 Moderate; 60–79 High; 80–100 Very High.")

    def set_percentile(self, percentile):
        self.percentile = percentile
        self.setAccessibleName(f"Habitat suitability: {percentile}th percentile on a scale of 0 to 100")
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width() - 12
        for index, color in enumerate(self.COLORS):
            x = 6 + width * index / 5
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(x, 19, width / 5 - 3, 9), 3, 3)
            p.setPen(QColor("#758170"))
            font = QFont("Segoe UI")
            font.setPixelSize(10)
            p.setFont(font)
            p.drawText(QRectF(x - 2, 37, width / 5, 15), Qt.AlignmentFlag.AlignCenter, ("Very low", "Low", "Moderate", "High", "Very high")[index])
        if self.percentile is not None:
            x = 6 + (width - 3) * self.percentile / 100
            p.setPen(QPen(QColor("#ffffff"), 3))
            p.setBrush(QColor("#254f38"))
            p.drawEllipse(QPointF(x, 23.5), 7.5, 7.5)
            p.setPen(QPen(QColor("#254f38"), 1))
            p.drawLine(QPointF(x, 3), QPointF(x, 11))


class Disclosure(QFrame):
    def __init__(self, title, role="environment"):
        super().__init__()
        self.setObjectName(role)
        self.title = title
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.toggle = QPushButton(f"+   {title}")
        self.toggle.setObjectName("accordion")
        self.toggle.setCheckable(True)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.toggled.connect(self.set_expanded)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(22, 0, 22, 22)
        self.body_layout.setSpacing(10)
        self.layout.addWidget(self.toggle)
        self.layout.addWidget(self.body)
        self.body.hide()

    def set_expanded(self, expanded):
        self.toggle.setChecked(expanded)
        self.toggle.setText(f"{'−' if expanded else '+'}   {self.title}")
        self.body.setVisible(expanded)
