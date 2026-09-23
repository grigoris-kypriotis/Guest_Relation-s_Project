"""
WorkspaceViewerDialog: Full-size document viewer dialog.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QTextBrowser, QPushButton
)


class WorkspaceViewerDialog(QDialog):
    """
    Dedicated document viewer dialog covering 99% of the parent window's bounds.
    An explicit outer padding of 6 pixels leaves the discrete pink boundary visible framing the active viewer.
    """
    def __init__(self, title: str, content_html: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet("""
            QDialog {
                background-color: transparent;
            }
            #OuterContainer {
                background-color: #ffffff;
                border: 2px solid #f43f5e; /* Discrete Pink Border */
                border-radius: 8px;
            }
        """)

        # Main Layout taking 99% scale of the workspace
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)  # Leaves discrete 1% pink backdrop visible

        container = QFrame()
        container.setObjectName("OuterContainer")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(12, 12, 12, 12)

        # Content display
        self.browser = QTextBrowser()
        if content_html:
            self.browser.setHtml(content_html)
        self.browser.setStyleSheet("border: none; background: #ffffff;")
        c_layout.addWidget(self.browser)

        # Bottom Controls
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #e11d48;
                color: white;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #be123c;
            }
        """)
        close_btn.clicked.connect(self.close)
        btn_bar.addWidget(close_btn)
        c_layout.addLayout(btn_bar)

        root_layout.addWidget(container)

    def showEvent(self, event):
        super().showEvent(event)
        if self.parent():
            # Calculate 99% geometry of parent workspace
            p_geom = self.parent().geometry()
            w = int(p_geom.width() * 0.99)
            h = int(p_geom.height() * 0.99)
            x = p_geom.x() + (p_geom.width() - w) // 2
            y = p_geom.y() + (p_geom.height() - h) // 2
            self.setGeometry(x, y, w, h)
