"""
Logs Option: Tabbed activity log viewer.
=========================================
Provides LogsWidget with categorized QListWidget tabs for each log stream.
Exposes add_log() for cross-module logging.
"""

import re
from datetime import datetime
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem
)
from PyQt6.QtGui import QColor

from MODULES.offers_module import log_task


# Default log category list
DEFAULT_LOG_CATEGORIES: List[str] = [
    "All Activity",
    "To Do List",
    "OFFERS",
    "ALLERGIES",
    "CAKE MEMOS",
    "Booking Calls",
    "ALL DATA"
]


class LogsWidget(QWidget):
    """
    Logs view: tabbed QListWidget panels for categorized activity logging.
    Provides add_log(category, message, level) as the unified logging interface.
    """

    def __init__(self, categories: Optional[List[str]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.categories = categories or DEFAULT_LOG_CATEGORIES
        self.log_lists = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFB6C1; background-color: #FFFFFF; border-radius: 6px; }
            QTabBar::tab { background-color: #FFE4E1; border: 1px solid #FFB6C1; padding: 8px 14px; margin-right: 3px; font-weight: bold; }
            QTabBar::tab:selected { background-color: #FF69B4; color: #FFFFFF; }
        """)

        for cat in self.categories:
            lw = QListWidget()
            lw.setWordWrap(True)
            self.log_lists[cat] = lw
            self.tab_widget.addTab(lw, cat)

        layout.addWidget(self.tab_widget)

    def add_log(self, category: str, message: str, level: str = "INFO") -> None:
        """
        Add a log entry to the specified category tab and always to 'All Activity'.
        Level determines text color: SUCCESS/OK=green, ERROR=red, WARNING=orange, INFO=blue.
        """
        try:
            clean_cat = re.sub(r"^\d+\.\s*", "", category)
            target_cat = clean_cat if clean_cat in self.log_lists else (category if category in self.log_lists else None)

            now_str = datetime.now().strftime("%H:%M:%S")
            formatted_entry = f"[{now_str}] [{level}] {message}"
            color_map = {
                "SUCCESS": "#2E7D32", "OK": "#2E7D32", "ERROR": "#C62828",
                "WARNING": "#E65100", "INFO": "#1976D2"
            }
            text_color = color_map.get(level.upper(), "#333333")

            if target_cat and target_cat in self.log_lists:
                item = QListWidgetItem(formatted_entry)
                item.setForeground(QColor(text_color))
                self.log_lists[target_cat].addItem(item)
                self.log_lists[target_cat].scrollToBottom()

            if target_cat != "All Activity" and "All Activity" in self.log_lists:
                all_entry = f"[{now_str}] [{target_cat or category}] [{level}] {message}"
                all_item = QListWidgetItem(all_entry)
                all_item.setForeground(QColor(text_color))
                self.log_lists["All Activity"].addItem(all_item)
                self.log_lists["All Activity"].scrollToBottom()

            try:
                log_task(f"[{target_cat or category}] {message}", level)
            except Exception:
                pass
        except Exception as e:
            print(f"[Logs] Logging error: {e}")

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        pass  # Logs are always accumulating — no refresh needed
