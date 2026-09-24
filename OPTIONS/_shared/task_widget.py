"""
TaskWidget: Individual to-do item with status cycling.
"""

import os
import win32com.client

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QMenu


class TaskWidget(QWidget):
    def __init__(self, description: str, task_id: str, state_change_callback=None, payload: dict = None):
        super().__init__()
        self.task_id = task_id
        self.state_change_callback = state_change_callback
        self.payload = payload or {}
        self.states = ["⏳", "❌", "✅", "➖", "📨"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.lbl_desc = QLabel(description)
        self.btn_state = QPushButton(self.states[0])
        self.btn_state.setFixedWidth(40)
        self.btn_state.clicked.connect(self.show_status_menu)

        layout.addWidget(self.lbl_desc)

        if self.payload.get("type") == "outlook_draft":
            self.btn_outlook = QPushButton("✉️ Manual Draft")
            self.btn_outlook.setStyleSheet("background-color: #2563EB; color: white; border-radius: 4px; padding: 2px 8px; font-weight: bold;")
            self.btn_outlook.clicked.connect(self.manual_draft_outlook)
            layout.addWidget(self.btn_outlook)

        layout.addStretch()
        layout.addWidget(self.btn_state)

    def manual_draft_outlook(self, error_callback=None):
        try:
            import win32com.client
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)
            data = self.payload.get("data", {})
            mail.To = data.get("To", "")
            mail.CC = data.get("CC", "")
            mail.Subject = data.get("Subject", "")
            mail.HTMLBody = data.get("HTMLBody", "")

            attachment = data.get("Attachment")
            if attachment:
                import os
                mail.Attachments.Add(os.path.abspath(attachment))

            mail.Display()
            if self.payload.get("subcategory") in ("Offer List", "Cake Memo"):
                self.set_state("📨")
        except Exception as e:
            print(f"Failed to draft outlook email: {e}")
            if error_callback:
                error_callback(e)

    def show_status_menu(self):
        menu = QMenu(self)
        for state in self.states:
            action = menu.addAction(state)
            action.triggered.connect(lambda checked=False, s=state: self.set_state(s))
        menu.exec(self.btn_state.mapToGlobal(self.btn_state.rect().bottomLeft()))

    def set_state(self, state: str):
        from MODULES.offers_module import log_task
        self.btn_state.setText(state)
        log_task(f"{state} {self.lbl_desc.text()}", "STATE_CHANGED")
        if self.state_change_callback:
            self.state_change_callback(state, self.task_id, self.lbl_desc.text())
