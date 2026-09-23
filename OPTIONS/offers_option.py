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
from PyQt6.QtCore import pyqtSignal

from MODULES.offers_module import (
    execute_offers_pipeline,
    duplicate_for_update, resolve_todays_offer_file, ARRIVALS_FOLDER
)
from MODULES.offers.pipeline import get_last_record_failures
from OPTIONS._shared_widgets import OfficeViewer
from OPTIONS.configuration_option import load_app_settings


class OffersOptionWidget(QWidget):
    """
    Offers view: document viewer container with create/update pipeline,
    save/close lifecycle, and status label.
    """
    task_generated = pyqtSignal(str, dict)

    def __init__(self, log_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.log_callback = log_callback
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
        self.office_viewer.file_saved_and_closed.connect(self._handle_save_and_close)
        oc_layout.addWidget(self.office_viewer, stretch=1)

        offers_layout.addWidget(offers_container)

    def _log(self, message: str, level: str = "INFO") -> None:
        if self.log_callback:
            self.log_callback("OFFERS", message, level)

    def _refresh_button_states(self) -> None:
        """
        Refresh the enabled/disabled state of the Create Offerlist button
        based on whether today's offer file already exists.
        """
        offer_lists_dir = load_app_settings().get("storage", {}).get("offer_lists_dir")
        exists = resolve_todays_offer_file(offer_lists_dir=offer_lists_dir) is not None
        self.btn_create.setEnabled(not exists)

    # ----- Document lifecycle -----

    def handle_doc_save(self) -> None:
        """Save the currently open document."""
        try:
            self.offers_status.hide()
            self.office_viewer.save_file()
            if self.office_viewer.current_filepath:
                self._log(f"Document saved: {os.path.basename(self.office_viewer.current_filepath)}")
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

    def handle_doc_save_and_close(self) -> None:
        """Trigger save and close on the OfficeViewer."""
        self.office_viewer.save_and_close()

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
                "To": "Operation Manager <Mariela.Tsvetkova@rizosresorts.gr>; Rooms Division Manager - Sandy Beach <harrys.palikiras@rizosresorts.gr>; Front Office Manager Sandy Beach <fom.sandy@rizosresorts.gr>;",
                "CC": "Guest Relations Sandy Beach <guest.sandybeach@rizosresorts.gr>;",
                "Subject": subject,
                "HTMLBody": html_body,
                "Attachment": filepath
            }
        }

    def _handle_save_and_close(self, filepath: str) -> None:
        """
        Offerlist Save & Close Handler:
        Strictly saves/updates the Word document in OUTPUT/OFFERS/.
        Routes the task to generate an Outlook email to the To-Do list.
        """
        try:
            self.offers_status.hide()
            final_path = filepath
            if self.is_update_mode:
                self._log(f"Saving updated offerlist: {os.path.basename(filepath)}")
                try:
                    new_path = duplicate_for_update(filepath)
                    self._log(f"Offerlist updated & saved successfully: {os.path.basename(new_path)}", "SUCCESS")
                    final_path = new_path
                except Exception as e:
                    self._log(f"Update save error: {e}", "ERROR")
                    return
            else:
                self._log(f"Offerlist saved successfully: {os.path.basename(filepath)}", "SUCCESS")
                
            payload = self._generate_offers_payload(final_path)
            self.task_generated.emit(f"Send Offerlist Email", payload)
            
            QMessageBox.information(
                self, 
                "Saved", 
                f"Offerlist saved successfully:\n{os.path.basename(final_path)}\n\n"
                f"A task to send the Outlook email has been added to the To-Do List."
            )
        except Exception as e:
            self._log(f"Save and close error: {e}", "ERROR")

    def activate(self) -> None:
        """Called when this option is selected from the menu. Refresh button states."""
        self._refresh_button_states()

    def build_submenu(self) -> QWidget:
        """Constructs the OFFERS sidebar submenu, wires its buttons to this widget's own handlers, and returns it."""
        submenu = QWidget()
        submenu_layout = QVBoxLayout(submenu)
        submenu_layout.setContentsMargins(0, 4, 0, 6)
        submenu_layout.setSpacing(5)
        submenu.setStyleSheet("""
            QWidget { background-color: transparent; }
            QPushButton {
                background-color: #FFE4E1;
                border: 1px solid #FFB6C1;
                border-radius: 4px;
                padding: 7px 10px 7px 20px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: black;
                margin-bottom: 2px;
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
        self.btn_save_close = QPushButton("SAVE & CLOSE")

        blue_sub_style = """
            QPushButton {
                background-color: #B0E0E6;
                border: 1px solid #4682B4;
                border-radius: 4px;
                padding: 7px 10px 7px 20px;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                color: #0F3460;
                margin-bottom: 2px;
            }
            QPushButton:hover { background-color: #4682B4; color: white; }
        """
        self.btn_save.setStyleSheet(blue_sub_style)
        self.btn_close.setStyleSheet(blue_sub_style)
        self.btn_save_close.setStyleSheet(blue_sub_style)

        self.btn_create.clicked.connect(self.run_offers_creation)
        self.btn_update.clicked.connect(self.run_offers_update)
        self.btn_save.clicked.connect(self.handle_doc_save)
        self.btn_close.clicked.connect(self.handle_doc_close)
        self.btn_save_close.clicked.connect(self.handle_doc_save_and_close)

        submenu_layout.addWidget(self.btn_create)
        submenu_layout.addWidget(self.btn_update)
        submenu_layout.addSpacing(14)
        submenu_layout.addWidget(self.btn_save)
        submenu_layout.addWidget(self.btn_close)
        submenu_layout.addWidget(self.btn_save_close)
        submenu.hide()

        # Refresh button states so the Create button starts in the correct state
        self._refresh_button_states()

        return submenu
