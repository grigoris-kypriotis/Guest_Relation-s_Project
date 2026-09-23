"""
To-Do Option: Task management list with status cycling.
========================================================
Provides a TodoWidget wrapping QListWidget with TaskWidget items.
Tasks can be added programmatically and cycled through ⏳ ❌ ✅ ➖ states.
"""

import uuid
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import QSize

from MODULES.offers_module import log_task
from OPTIONS._shared_widgets import TaskWidget


class TodoWidget(QWidget):
    """
    To-Do List container: wraps a QListWidget populated with TaskWidget rows.
    Exposes add_task() and a callback hook for state changes.
    """

    def __init__(self, log_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.log_callback = log_callback
        self.active_tasks = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.todo_list = QListWidget()
        self.todo_list.setStyleSheet("background-color: #FFFFFF; color: black; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.todo_list)

    def add_task(self, task_id: str, description: str, payload: dict = None) -> None:
        """Add a new task to the list."""
        try:
            item = QListWidgetItem(self.todo_list)
            item.setSizeHint(QSize(0, 40))
            task_widget = TaskWidget(description, task_id, state_change_callback=self._handle_task_state_change, payload=payload)
            self.todo_list.setItemWidget(item, task_widget)
            self.active_tasks[task_id] = task_widget
            log_task(f"⏳ {description}", "ADDED")
            if self.log_callback:
                self.log_callback("To Do List", f"Task created: ⏳ {description}", "INFO")
        except Exception as e:
            print(f"[Todo] Error adding task: {e}")

    def add_task_auto(self, description: str, payload: dict = None) -> str:
        """Add a task with an auto-generated ID. Returns the task ID."""
        task_id = str(uuid.uuid4())
        self.add_task(task_id, description, payload)
        return task_id

    def get_or_create_task(self, description: str, payload: dict = None) -> str:
        """
        Finds an existing task whose description matches exactly and reuses it
        (updating its payload to the latest), instead of creating a duplicate.
        Falls back to add_task_auto if no match exists.
        """
        for task_id, task_widget in self.active_tasks.items():
            if task_widget.lbl_desc.text() == description:
                task_widget.payload = payload or {}
                if self.log_callback:
                    self.log_callback("To Do List", f"Task reused (updated payload): {description}", "INFO")
                return task_id
        return self.add_task_auto(description, payload)

    def _handle_task_state_change(self, state: str, task_id: str, desc: str) -> None:
        """Handle task state transitions."""
        try:
            if state == "✅":
                log_task(f"✅ {desc}", "COMPLETED")
                if self.log_callback:
                    self.log_callback("To Do List", f"Task COMPLETED: {desc}", "SUCCESS")
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                for row in range(self.todo_list.count()):
                    item = self.todo_list.item(row)
                    w = self.todo_list.itemWidget(item)
                    if w and getattr(w, 'task_id', None) == task_id:
                        self.todo_list.takeItem(row)
                        break
            else:
                if self.log_callback:
                    self.log_callback("To Do List", f"Task status updated to {state}: {desc}", "INFO")
        except Exception as e:
            print(f"[Todo] State change error: {e}")

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        pass  # No refresh needed — list is stateful
