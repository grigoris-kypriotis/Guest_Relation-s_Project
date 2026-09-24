# -*- coding: utf-8 -*-
"""
Cake Memo Option Widget: orchestration layer for Create/Update/Edit/Save/Close flows.
=======================================================================================
Provides CakeMemoOptionWidget with mode tracking, form/document lifecycle,
file picker for Update/Edit modes, and structured Save with collision handling.
"""

import os
import re
from datetime import datetime
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QFileDialog, QMessageBox, QPushButton, QHBoxLayout
)

from MODULES.cake_memo.document import generate_cake_memo_document
from MODULES.cake_memo.parser import parse_cake_memo_document
from OPTIONS._shared_widgets import OfficeViewer
from OPTIONS.configuration_option import load_app_settings
from OPTIONS.cake_memo.form import CakeMemoForm
from MODULES.cake_memo.paths import DEFAULT_CAKE_MEMOS_DIR


class CakeMemoOptionWidget(QWidget):
    """
    Cake Memo view: structured form (Create/Update) + raw document editing (Edit),
    with mode-tracked Save/Close lifecycle and file collision handling.
    """

    def __init__(self, log_callback: Optional[Callable] = None, todo_widget=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.log_callback = log_callback
        self.todo_widget = todo_widget
        self.mode: Optional[str] = None  # None | "create" | "update" | "edit"
        self.loaded_file_path: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        """Build the UI: status label, form, and office viewer (only one visible at a time)."""
        cake_layout = QVBoxLayout(self)
        cake_layout.setContentsMargins(6, 6, 6, 6)
        cake_layout.setSpacing(0)

        cake_container = QFrame()
        cake_container.setObjectName("OuterContainer")
        cake_container.setStyleSheet("""
            #OuterContainer {
                background-color: #ffffff;
                border: 2px solid #f43f5e;
                border-radius: 8px;
            }
        """)
        cc_layout = QVBoxLayout(cake_container)
        cc_layout.setContentsMargins(8, 8, 8, 8)
        cc_layout.setSpacing(4)

        self.status_label = QLabel("🎂 CAKE MEMOS\nSelect an action from the menu.")
        self.status_label.setStyleSheet("font-weight: bold; color: #800020; padding: 8px;")
        cc_layout.addWidget(self.status_label)

        # Create the form and office viewer BEFORE wiring any signals
        self.form = CakeMemoForm()
        self.office_viewer = OfficeViewer()

        cc_layout.addWidget(self.form, stretch=1)
        cc_layout.addWidget(self.office_viewer, stretch=1)

        # Both hidden initially (mode is None)
        self.form.hide()
        self.office_viewer.hide()

        cake_layout.addWidget(cake_container)

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log a message via the callback if available."""
        if self.log_callback:
            self.log_callback("CAKE MEMOS", message, level)

    def _get_cake_memos_dir(self) -> str:
        """Resolve the cake memos output directory from settings or use default."""
        return load_app_settings().get("storage", {}).get("cake_memos_dir") or DEFAULT_CAKE_MEMOS_DIR

    # ----- Mode Actions -----

    def handle_create_cake_memo(self) -> None:
        """Transition to Create mode: show form, reset fields."""
        self.mode = "create"
        self.loaded_file_path = None
        self.form.reset()
        self.form.show()
        self.office_viewer.hide()
        self._log("Create Cake Memo mode activated.", "INFO")

    def handle_update_cake_memo(self) -> None:
        """Transition to Update mode: pick a file, parse it, pre-fill form."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a Cake Memo to update",
            self._get_cake_memos_dir(),
            "Word Documents (*.docx)"
        )
        if not path:
            return

        try:
            data = parse_cake_memo_document(path)
            # Add pax default since parser omits it
            if "pax" not in data:
                data["pax"] = 1
        except Exception as e:
            self._log(f"Failed to parse cake memo: {e}", "ERROR")
            return

        self.form.set_form_data(data)
        self.mode = "update"
        self.loaded_file_path = path
        self.form.show()
        self.office_viewer.hide()
        self._log(f"Loaded for update: {os.path.basename(path)}", "SUCCESS")

    def handle_edit(self) -> None:
        """Transition to Edit mode: pick a file, open in OfficeViewer."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a Cake Memo to edit",
            self._get_cake_memos_dir(),
            "Word Documents (*.docx)"
        )
        if not path:
            return

        self.mode = "edit"
        self.loaded_file_path = path
        self.form.hide()
        self.office_viewer.open_file(path)
        self._log(f"Edit mode: {os.path.basename(path)}", "INFO")

    def handle_save(self) -> None:
        """Mode-dependent save: Create (new file + collision), Update (overwrite), Edit (raw save)."""
        if self.mode is None:
            self._log("No mode active; nothing to save.", "WARNING")
            return

        if self.mode in ("create", "update"):
            data = self.form.get_form_data()

            # Validate room number
            if not data["room_number"].strip():
                self._log("Room number is required. Cannot save without a room number.", "ERROR")
                return

            try:
                if self.mode == "create":
                    # Generate new filename with collision handling
                    room_num = data["room_number"].strip()
                    filename = f"CAKE MEMO ({datetime.now():%d-%m-%y}) ROOM {room_num}.docx"
                    target_dir = self._get_cake_memos_dir()
                    os.makedirs(target_dir, exist_ok=True)
                    final_path = os.path.join(target_dir, filename)

                    # Collision handling: " UPDATED" / " UPDATED (N)" pattern
                    if os.path.exists(final_path):
                        base_name = filename.replace(".docx", "")
                        final_path = os.path.join(target_dir, f"{base_name} UPDATED.docx")
                        counter = 2
                        while os.path.exists(final_path):
                            final_path = os.path.join(target_dir, f"{base_name} UPDATED ({counter}).docx")
                            counter += 1

                    generate_cake_memo_document(data, final_path)
                    self._log(f"Cake memo saved: {os.path.basename(final_path)}", "SUCCESS")
                    self.mode = None
                    self.form.hide()
                    self.loaded_file_path = None

                else:  # mode == "update"
                    # Overwrite the loaded file directly (no collision suffix for updates)
                    generate_cake_memo_document(data, self.loaded_file_path)
                    self._log(f"Cake memo updated: {os.path.basename(self.loaded_file_path)}", "SUCCESS")
                    self.mode = None
                    self.form.hide()
                    self.loaded_file_path = None

            except Exception as e:
                self._log(f"Save error: {e}", "ERROR")

        elif self.mode == "edit":
            try:
                self.office_viewer.save_file()
                if self.office_viewer.current_filepath:
                    self._log(f"Document saved: {os.path.basename(self.office_viewer.current_filepath)}", "SUCCESS")
            except Exception as e:
                self._log(f"Save error: {e}", "ERROR")

    def handle_close(self) -> None:
        """Mode-dependent close: discard (create/update) or close editor (edit)."""
        if self.mode is None:
            return

        if self.mode in ("create", "update"):
            self._log(f"Discarding {self.mode} mode changes.", "INFO")
            self.form.hide()
            self.mode = None
            self.loaded_file_path = None

        elif self.mode == "edit":
            self.office_viewer.close_file()
            self._log("Document editor closed.", "INFO")
            self.mode = None
            self.loaded_file_path = None

    def handle_send_email(self) -> None:
        """Placeholder for Step 5 implementation."""
        self._log("Send Email not yet implemented.", "WARNING")
        return

    def activate(self) -> None:
        """Called when this option is selected from the menu. No-op for Cake Memo."""
        pass

    def build_submenu(self) -> QWidget:
        """Constructs the CAKE MEMOS sidebar submenu with 6 buttons."""
        submenu = QWidget()
        submenu.setObjectName("CakeMemoSubmenuContainer")
        submenu_layout = QVBoxLayout(submenu)
        submenu_layout.setContentsMargins(12, 8, 4, 8)
        submenu_layout.setSpacing(3)
        submenu.setStyleSheet("""
            #CakeMemoSubmenuContainer {
                background-color: #F7F7F7;
                border-left: 4px solid #FF6B9D;
                border-radius: 0px 4px 4px 0px;
            }
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                border-radius: 3px;
                padding: 6px 8px 6px 10px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: black;
                margin: 1px 0px;
            }
            QPushButton:hover { background-color: #FF69B4; color: white; }
            QPushButton:disabled {
                background-color: #D3D3D3;
                border: 1px solid #A9A9A9;
                color: #777777;
            }
        """)

        # Create button instances
        self.btn_create = QPushButton("Create Cake Memo")
        self.btn_update = QPushButton("Update Cake Memo")
        self.btn_edit = QPushButton("Edit")
        self.btn_save = QPushButton("Save")
        self.btn_close = QPushButton("Close")
        self.btn_send_email = QPushButton("Send Email")

        # Blue styling for Save, Close, Send Email
        blue_sub_style = """
            QPushButton {
                background-color: #B0E0E6;
                border: 1px solid #4682B4;
                border-radius: 3px;
                padding: 6px 8px 6px 10px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: #0F3460;
                margin: 1px 0px;
            }
            QPushButton:hover { background-color: #4682B4; color: white; }
            QPushButton:disabled {
                background-color: #B8D4E8;
                border: 1px solid #8BA9C8;
                color: #5A7FA0;
            }
        """
        self.btn_save.setStyleSheet(blue_sub_style)
        self.btn_close.setStyleSheet(blue_sub_style)
        self.btn_send_email.setStyleSheet(blue_sub_style)

        # Wire buttons to handlers
        self.btn_create.clicked.connect(self.handle_create_cake_memo)
        self.btn_update.clicked.connect(self.handle_update_cake_memo)
        self.btn_edit.clicked.connect(self.handle_edit)
        self.btn_save.clicked.connect(self.handle_save)
        self.btn_close.clicked.connect(self.handle_close)
        self.btn_send_email.clicked.connect(self.handle_send_email)

        # Add buttons to layout
        submenu_layout.addWidget(self.btn_create)
        submenu_layout.addWidget(self.btn_update)
        submenu_layout.addWidget(self.btn_edit)
        submenu_layout.addSpacing(14)
        submenu_layout.addWidget(self.btn_save)
        submenu_layout.addWidget(self.btn_close)
        submenu_layout.addWidget(self.btn_send_email)

        submenu.hide()
        return submenu
