"""
Offers Option: Offerlist creation, update, and document management.
====================================================================
Provides OffersOptionWidget containing the OfficeViewer integration,
create/update pipeline handlers, and save/close lifecycle management.
"""

import os
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QFileDialog, QMessageBox, QPushButton
)

from MODULES.offers_module import (
    execute_offers_pipeline,
    duplicate_for_update, resolve_todays_offer_file, ARRIVALS_FOLDER
)
from MODULES.offers.pipeline import get_last_record_failures
from MODULES.common.fb_email_recipients import TO_RECIPIENTS, CC_RECIPIENTS
from OPTIONS._shared_widgets import OfficeViewer
from OPTIONS.configuration_option import load_app_settings


class OffersOptionWidget(QWidget):
    """
    Offers view: document viewer container with create/update pipeline,
    save/close lifecycle, and status label.
    """

    def __init__(self, log_callback: Optional[Callable] = None, todo_widget=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.log_callback = log_callback
        self.todo_widget = todo_widget
        self.is_update_mode = False
        self._init_ui()

    def _init_ui(self) -> None:
        offers_layout = QVBoxLayout(self)
        offers_layout.setContentsMargins(6, 6, 6, 6)
        offers_layout.setSpacing(0)

        offers_container = QFrame()
        offers_container.setObjectName("OuterContainer")
        offers_container.setStyleSheet("""
            #OuterContainer {
                background-color: #ffffff;
                border: 2px solid #f43f5e;
                border-radius: 8px;
            }
        """)
        oc_layout = QVBoxLayout(offers_container)
        oc_layout.setContentsMargins(8, 8, 8, 8)
        oc_layout.setSpacing(4)

        self.offers_status = QLabel("OFFERS PROCESSOR\nTarget: TEMPLATES/OFFER LIST TEMPLATE/")
        self.offers_status.setWordWrap(True)
        self.offers_status.setStyleSheet("font-weight: bold; color: #B03060; padding: 5px;")
        oc_layout.addWidget(self.offers_status)

        self.office_viewer = OfficeViewer()
        oc_layout.addWidget(self.office_viewer, stretch=1)

        offers_layout.addWidget(offers_container)

    def _log(self, message: str, level: str = "INFO") -> None:
        if self.log_callback:
            self.log_callback("OFFERS", message, level)

    def _refresh_button_states(self) -> None:
        """
        Refresh the enabled/disabled state of the Create and Send Email buttons
        based on whether today's offer file already exists.
        """
        offer_lists_dir = load_app_settings().get("storage", {}).get("offer_lists_dir")
        exists = resolve_todays_offer_file(offer_lists_dir=offer_lists_dir) is not None
        self.btn_create.setEnabled(not exists)
        self.btn_send_email.setEnabled(exists)

    # ----- Document lifecycle -----

    def handle_doc_save(self) -> None:
        """Save the currently open document. In update mode, also creates a new UPDATED variant."""
        try:
            self.offers_status.hide()
            self.office_viewer.save_file()
            if not self.office_viewer.current_filepath:
                return
            self._log(f"Document saved: {os.path.basename(self.office_viewer.current_filepath)}")
            if self.is_update_mode:
                try:
                    new_path = duplicate_for_update(self.office_viewer.current_filepath)
                    self._log(f"Update saved as: {os.path.basename(new_path)}", "SUCCESS")
                except Exception as e:
                    self._log(f"Update save error: {e}", "ERROR")
                    return
                self._refresh_button_states()
        except Exception as e:
            self._log(f"Save error: {e}", "ERROR")

    def handle_doc_close(self) -> None:
        """Close the currently open document without saving."""
        try:
            self.offers_status.hide()
            if self.office_viewer.current_filepath:
                self._log(f"Document closed: {os.path.basename(self.office_viewer.current_filepath)}")
            self.office_viewer.close_file()
        except Exception as e:
            self._log(f"Close error: {e}", "ERROR")

    def _handle_outlook_error(self, error: Exception) -> None:
        """Callback for Outlook draft errors from manual_draft_outlook()."""
        self._log(f"Outlook draft error: {error}", "ERROR")

    def handle_send_email(self) -> None:
        """Resolves today's offer file, opens an Outlook draft (display-only, never auto-sent),
        and reuses/creates the 'Send Offerlist Email' To-Do task."""
        try:
            offer_lists_dir = load_app_settings().get("storage", {}).get("offer_lists_dir")
            file_path = resolve_todays_offer_file(offer_lists_dir=offer_lists_dir)
            if not file_path:
                self._log("No offer list found for today. Send Email unavailable.", "ERROR")
                return
            if self.todo_widget is None:
                self._log("To-Do list unavailable; cannot create/send task.", "ERROR")
                return
            payload = self._generate_offers_payload(file_path)
            task_id = self.todo_widget.get_or_create_task("Send Offerlist Email", payload)
            task_widget = self.todo_widget.active_tasks.get(task_id)
            if task_widget:
                draft_failure = {}

                def _on_draft_error(error: Exception) -> None:
                    draft_failure["error"] = error
                    self._handle_outlook_error(error)

                task_widget.manual_draft_outlook(error_callback=_on_draft_error)
                if "error" not in draft_failure:
                    self._log(f"Outlook draft opened for: {os.path.basename(file_path)}", "SUCCESS")
            else:
                self._log("Task created but widget reference not found — draft not opened.", "ERROR")
        except Exception as e:
            self._log(f"Send Email error: {e}", "ERROR")

    # ----- Pipeline actions -----

    def run_offers_creation(self) -> None:
        """Execute the Create Offerlist pipeline."""
        try:
            self.offers_status.hide()
            self.is_update_mode = False
            self._log("Action: Create Offerlist triggered")

            # Defensive guard: today's file should not already exist (button should be disabled, but check anyway)
            offer_lists_dir = load_app_settings().get("storage", {}).get("offer_lists_dir")
            if resolve_todays_offer_file(offer_lists_dir=offer_lists_dir) is not None:
                self._log("Today's offer list already exists. Operation denied. Use UPDATE Offerlist.", "ERROR")
                return

            self._log("Processing Data... Please wait.")
            self.office_viewer.close_file()
            self.repaint()

            pipeline_status, msg, final_path = execute_offers_pipeline()

            if not pipeline_status and msg == "MISSING_CSVS":
                self._log("Missing CSV in ARRIVALS. Prompting file selector...", "WARNING")
                selected_file, _ = QFileDialog.getOpenFileName(self, "Select today's arrivals CSV", ARRIVALS_FOLDER, "CSV (*.csv)")
                if selected_file:
                    self._log(f"User selected CSV file: {os.path.basename(selected_file)}")
                    pipeline_status, msg, final_path = execute_offers_pipeline(selected_csvs=[selected_file])
                else:
                    self._log("Requirement: exactly 1 CSV file. Operation aborted.", "ERROR")
                    return

            level = "SUCCESS" if pipeline_status else "ERROR"
            self._log(msg, level)

            # Log individual record write failures if any
            record_failures = get_last_record_failures()
            for booking_id, error in record_failures:
                self._log(f"Record write failed for booking {booking_id}: {error}", "ERROR")

            if pipeline_status and final_path:
                self._log(f"Opening generated document in OfficeViewer: {os.path.basename(final_path)}")
                self.office_viewer.open_file(final_path)
                # Refresh button states to reflect that today's file now exists
                self._refresh_button_states()
        except Exception as e:
            self._log(f"Creation pipeline error: {e}", "ERROR")

    def run_offers_update(self) -> None:
        """Execute the UPDATE Offerlist pipeline."""
        try:
            self.offers_status.hide()
            self.is_update_mode = True
            self._log("Action: UPDATE Offerlist triggered")
            self._log("Searching for today's file...")
            self.repaint()

            # Read offer_lists_dir from settings
            offer_lists_dir = load_app_settings().get("storage", {}).get("offer_lists_dir")
            file_path = resolve_todays_offer_file(offer_lists_dir=offer_lists_dir)
            if file_path:
                self._log(f"File located. Mode: UPDATE. Target: {os.path.basename(file_path)}", "SUCCESS")
                self.office_viewer.open_file(file_path)
            else:
                self._log("No offer list found for today. Please create one first.", "WARNING")
        except Exception as e:
            self._log(f"Update pipeline error: {e}", "ERROR")

    def _generate_offers_payload(self, filepath: str) -> dict:
        """Generates an Outlook draft payload for the Offerlist."""
        subject = f"OFFERLIST {os.path.basename(filepath).replace('.docx', '')}"
        html_body = f"""<div style='font-family: Calibri, sans-serif; font-size: 11pt;'>
          Dear all,<br>Kindly find attached the Offerlist.<br><br>
          For any further information don't hesitate to contact the Guest Relations Team.
        </div>"""

        return {
            "type": "outlook_draft",
            "category": "Offer",
            "subcategory": "Offer List",
            "is_service_trace": True,
            "data": {
                "To": TO_RECIPIENTS,
                "CC": CC_RECIPIENTS,
                "Subject": subject,
                "HTMLBody": html_body,
                "Attachment": filepath
            }
        }

    def activate(self) -> None:
        """Called when this option is selected from the menu. Refresh button states."""
        self._refresh_button_states()

    def build_submenu(self) -> QWidget:
        """Constructs the OFFERS sidebar submenu, wires its buttons to this widget's own handlers, and returns it."""
        submenu = QWidget()
        submenu.setObjectName("OffersSubmenuContainer")
        submenu_layout = QVBoxLayout(submenu)
        submenu_layout.setContentsMargins(12, 8, 4, 8)
        submenu_layout.setSpacing(3)
        submenu.setStyleSheet("""
            #OffersSubmenuContainer {
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

        self.btn_create = QPushButton("Create Offerlist")
        self.btn_update = QPushButton("UPDATE Offerlist")
        self.btn_save = QPushButton("SAVE")
        self.btn_close = QPushButton("CLOSE")
        self.btn_send_email = QPushButton("Send Email")

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

        self.btn_create.clicked.connect(self.run_offers_creation)
        self.btn_update.clicked.connect(self.run_offers_update)
        self.btn_save.clicked.connect(self.handle_doc_save)
        self.btn_close.clicked.connect(self.handle_doc_close)
        self.btn_send_email.clicked.connect(self.handle_send_email)

        submenu_layout.addWidget(self.btn_create)
        submenu_layout.addWidget(self.btn_update)
        submenu_layout.addSpacing(14)
        submenu_layout.addWidget(self.btn_save)
        submenu_layout.addWidget(self.btn_close)
        submenu_layout.addWidget(self.btn_send_email)
        submenu.hide()

        # Refresh button states so the Create/Send Email buttons start in the correct state
        self._refresh_button_states()

        return submenu
