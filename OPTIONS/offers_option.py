"""
Offers Option: Offerlist creation, update, and document management.
====================================================================
Provides OffersOptionWidget containing the OfficeViewer integration,
create/update pipeline handlers, and save/close lifecycle management.
"""

import os
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QFileDialog, QMessageBox
)

from MODULES.offers_module import (
    execute_offers_pipeline, get_todays_offer_list,
    duplicate_for_update, ARRIVALS_FOLDER
)
from OPTIONS._shared_widgets import OfficeViewer


class OffersOptionWidget(QWidget):
    """
    Offers view: document viewer container with create/update pipeline,
    save/close lifecycle, and status label.
    """

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

            if get_todays_offer_list() is not None:
                self._log("Today's offer list already exists. Operation denied. Use UPDATE Offerlist.", "WARNING")
                return

            self._log("Processing Data... Please wait.")
            self.office_viewer.close_file()
            self.repaint()

            pipeline_status, msg, final_path = execute_offers_pipeline()

            if not pipeline_status and msg == "MISSING_CSVS":
                self._log("Missing CSVs in ARRIVALS. Prompting file selector...", "WARNING")
                files, _ = QFileDialog.getOpenFileNames(self, "Select 2 CSV Files (Hold Ctrl for multiple)", ARRIVALS_FOLDER, "CSV (*.csv)")
                if len(files) == 1:
                    second_file, _ = QFileDialog.getOpenFileName(self, "Select the SECOND CSV File", ARRIVALS_FOLDER, "CSV (*.csv)")
                    if second_file:
                        files.append(second_file)
                if len(files) == 2:
                    self._log(f"User selected CSV files: {os.path.basename(files[0])}, {os.path.basename(files[1])}")
                    pipeline_status, msg, final_path = execute_offers_pipeline(selected_csvs=files)
                else:
                    self._log("Requirement: Exactly 2 CSV files. Operation aborted.", "ERROR")
                    return

            level = "SUCCESS" if pipeline_status else "ERROR"
            self._log(msg, level)
            if pipeline_status and final_path:
                self._log(f"Opening generated document in OfficeViewer: {os.path.basename(final_path)}")
                self.office_viewer.open_file(final_path)
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

            file_path = get_todays_offer_list()
            if file_path:
                self._log(f"File located. Mode: UPDATE. Target: {os.path.basename(file_path)}", "SUCCESS")
                self.office_viewer.open_file(file_path)
            else:
                self._log("No offer list found for today. Please create one first.", "WARNING")
        except Exception as e:
            self._log(f"Update pipeline error: {e}", "ERROR")

    def _handle_save_and_close(self, filepath: str) -> None:
        """
        Offerlist Save & Close Handler:
        Strictly saves/updates the Word document in OUTPUT/OFFERS/.
        Completely removed Outlook email draft generation per user specification.
        """
        try:
            self.offers_status.hide()
            if self.is_update_mode:
                self._log(f"Saving updated offerlist: {os.path.basename(filepath)}")
                try:
                    new_path = duplicate_for_update(filepath)
                    self._log(f"Offerlist updated & saved successfully: {os.path.basename(new_path)}", "SUCCESS")
                    QMessageBox.information(self, "Saved", f"Offerlist updated & saved successfully:\n{os.path.basename(new_path)}")
                except Exception as e:
                    self._log(f"Update save error: {e}", "ERROR")
            else:
                self._log(f"Offerlist saved successfully: {os.path.basename(filepath)}", "SUCCESS")
                QMessageBox.information(self, "Saved", f"Offerlist saved successfully:\n{os.path.basename(filepath)}")
        except Exception as e:
            self._log(f"Save and close error: {e}", "ERROR")

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        pass  # Offers view is stateful — no auto-refresh needed
