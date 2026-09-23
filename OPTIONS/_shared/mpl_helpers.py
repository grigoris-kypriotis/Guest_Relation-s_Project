"""
Matplotlib helpers: Wheel event filtering and non-scrollable figure canvas.
"""

from PyQt6.QtWidgets import QScrollArea, QWidget
from PyQt6.QtCore import QObject, QEvent, QSize, Qt


class WheelPassThroughFilter(QObject):
    """
    Event filter for FigureCanvas widgets inside scrollable cards.
    Intercepts wheel events that Matplotlib's Qt backend would normally capture/consume,
    and forwards them up to the ancestor QScrollArea viewport so the dashboard scrolls smoothly.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            p = obj.parent()
            while p is not None:
                if isinstance(p, QScrollArea):
                    viewport = p.viewport()
                    if viewport is not None:
                        viewport.event(event)
                    else:
                        p.wheelEvent(event)
                    return True
                p = p.parent()
            event.ignore()
            return False
        return False


try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
except ImportError:
    FigureCanvasQTAgg = QWidget


class NonScrollableFigureCanvas(FigureCanvasQTAgg):
    """FigureCanvas that ignores mouse wheel events, provides zero minimum width, and passes wheel to ancestor QScrollArea."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def sizeHint(self) -> QSize:
        return QSize(400, 260)

    def wheelEvent(self, event):
        p = self.parent()
        while p is not None:
            if isinstance(p, QScrollArea):
                viewport = p.viewport()
                if viewport is not None:
                    viewport.event(event)
                else:
                    p.wheelEvent(event)
                event.accept()
                return
            p = p.parent()
        event.ignore()
