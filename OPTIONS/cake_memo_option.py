"""
Cake Memo Option: Word table parsing, Save As pipeline, and Outlook draft generation.
======================================================================================
Provides CakeMemoOptionWidget with OfficeViewer integration, docx table parsing helper,
and automated Outlook email draft creation for cake service notifications.
"""

import os
import re
import shutil
from datetime import datetime
from typing import Dict, Optional, Callable

import docx
import win32com.client

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QMessageBox
)
from PyQt6.QtCore import pyqtSignal

from MODULES.data_manager import OUTPUT_DIR, resolve_template_path
from MODULES.common.fb_email_recipients import TO_RECIPIENTS, CC_RECIPIENTS
from OPTIONS._shared_widgets import OfficeViewer


# =============================================================================
# Helper: Parse Cake Memo Word Document Table
# =============================================================================

def parse_cake_memo_docx(docx_path: str) -> Dict[str, str]:
    """
    Parses a Cake Memo .docx table and extracts:
      - room_number (from column 'ROOM NUMBER' or data row)
      - cake_location (ERMIS, IL GUSTO, ELIA, AMMOS, or ROOM)
      - cake_time (e.g. 14:00, 20:30, 7:00 PM, 19.30PM)
      - cake_date_display (dd/MM)
      - cake_date_file (dd.MM.yyyy)
      - memo_month_year (MM.yyyy)
    """
    doc = docx.Document(docx_path)
    room_number = ""
    provided_at_text = ""
    date_text = ""

    for table in doc.tables:
        if not table.rows:
            continue
        header_cells = [c.text.strip().upper().replace("\n", " ") for c in table.rows[0].cells]

        col_room = -1
        col_provided = -1
        col_date = -1

        for idx, h in enumerate(header_cells):
            if "ROOM" in h:
                col_room = idx
            elif "PROVIDED" in h or "AT" in h:
                col_provided = idx
            elif "DATE" in h:
                col_date = idx

        if col_room == -1 and len(header_cells) >= 7:
            col_room = 6
        if col_provided == -1 and len(header_cells) >= 4:
            col_provided = 3
        if col_date == -1 and len(header_cells) >= 5:
            col_date = 4

        for row in table.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if not any(cells):
                continue

            r_val = cells[col_room] if 0 <= col_room < len(cells) else ""
            p_val = cells[col_provided] if 0 <= col_provided < len(cells) else ""
            d_val = cells[col_date] if 0 <= col_date < len(cells) else ""

            if not r_val:
                for c_text in cells:
                    m_room = re.search(r"\b(\d{3,4})\b", c_text)
                    if m_room:
                        r_val = m_room.group(1)
                        break

            if r_val or p_val or d_val:
                room_number = r_val
                provided_at_text = p_val
                date_text = d_val
                break

    # Parse Location: Look for ERMIS, IL GUSTO, ELIA, AMMOS, or ROOM
    location = "ROOM"
    loc_match = re.search(r"(?i)\b(ERMIS|IL GUSTO|ELIA|AMMOS|ROOM)\b", provided_at_text)
    if loc_match:
        location = loc_match.group(1).upper()

    # Parse Time: e.g., 14:00, 20:30, 7:00 PM, 19.30PM
    time_match = re.search(r"(\b\d{1,2}[:\.]\d{2}\s*(?:AM|PM|am|pm)?|\b\d{1,2}\s*(?:AM|PM|am|pm)\b)", provided_at_text)
    time_val = time_match.group(1) if time_match else "N/A"

    # Normalize Date
    now = datetime.now()
    date_match = re.search(r"(\d{1,2})[\/\.\-](\d{1,2})", date_text)
    if date_match:
        d_day = int(date_match.group(1))
        d_month = int(date_match.group(2))
        cake_date_display = f"{d_day:02d}/{d_month:02d}"
        cake_date_file = f"{d_day:02d}.{d_month:02d}.{now.year}"
        memo_month_year = f"{d_month:02d}.{now.year}"
    else:
        cake_date_display = now.strftime("%d/%m")
        cake_date_file = now.strftime("%d.%m.%Y")
        memo_month_year = now.strftime("%m.%Y")

    if not room_number:
        room_number = "UNKNOWN"

    return {
        "room_number": room_number,
        "cake_location": location,
        "cake_time": time_val,
        "cake_date_display": cake_date_display,
        "cake_date_file": cake_date_file,
        "memo_month_year": memo_month_year
    }


# =============================================================================
# Helper: Generate Outlook Draft for Cake Memo
# =============================================================================

def generate_cake_memo_outlook_payload(docx_path: str, memo_data: Dict[str, str]) -> dict:
    """Generates an Outlook draft payload with the specified recipients, subject, and formatted HTML body."""

    room_number = memo_data["room_number"]
    cake_date = memo_data["cake_date_display"]
    cake_location = memo_data["cake_location"]
    cake_time = memo_data["cake_time"]

    subject = f"CAKE MEMO {cake_date} R{room_number}"

    html_body = f"""<div style='font-family: Calibri, sans-serif; font-size: 11pt;'>
  Dear all,<br>Kindly find attached the Cake Memo for Room {room_number}.<br><br>
  <b>Service Details:</b><br>
  &bull; <b>Date:</b> {cake_date}<br>
  &bull; <b>Location:</b> {cake_location}<br>
  &bull; <b>Time:</b> {cake_time}<br><br>
  For any further information don't hesitate to contact the Guest Relations Team.
</div>"""

    return {
        "type": "outlook_draft",
        "category": "Offer",
        "subcategory": "Cake Memo",
        "room_number": room_number,
        "is_service_trace": True,
        "data": {
            "To": TO_RECIPIENTS,
            "CC": CC_RECIPIENTS,
            "Subject": subject,
            "HTMLBody": html_body,
            "Attachment": docx_path
        }
    }


# =============================================================================
# CakeMemoOptionWidget: Main widget for the CAKE MEMOS sidebar option
# =============================================================================

class CakeMemoOptionWidget(QWidget):
    """
    Cake Memos view: OfficeViewer integration with template loading,
    Word table parsing, Save As pipeline, and Outlook draft generation.
    """
    task_generated = pyqtSignal(str, dict)

    def __init__(self, log_callback: Optional[Callable] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.log_callback = log_callback
        self._init_ui()

    def _init_ui(self) -> None:
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

        self.cake_status = QLabel("🎂 CAKE MEMOS PROCESSOR\nLoads from: TEMPLATES/CAKE MEMO TEMPLATE/CAKE MEMO.docx")
        self.cake_status.setStyleSheet("font-weight: bold; color: #800020; padding: 8px;")
        cc_layout.addWidget(self.cake_status)

        self.cake_office_viewer = OfficeViewer()
        self.cake_office_viewer.file_saved_and_closed.connect(self._handle_cake_save_and_close)
        cc_layout.addWidget(self.cake_office_viewer, stretch=1)

        cake_layout.addWidget(cake_container)

    def _log(self, message: str, level: str = "INFO") -> None:
        if self.log_callback:
            self.log_callback("CAKE MEMOS", message, level)

    # ----- Template & Document Lifecycle -----

    def open_cake_memo_template(self) -> None:
        """Opens base Cake Memo template from TEMPLATES/ inside OfficeViewer."""
        try:
            template_path = resolve_template_path("cake_memo")
            if not template_path or not os.path.exists(template_path):
                self._log("Cake Memo template not found in TEMPLATES/", "ERROR")
                QMessageBox.warning(self, "Template Error", "Cake Memo template not found in TEMPLATES/CAKE MEMO TEMPLATE/.")
                return

            cake_temp_dir = os.path.join(OUTPUT_DIR, "CAKE_MEMOS")
            os.makedirs(cake_temp_dir, exist_ok=True)
            working_file = os.path.join(cake_temp_dir, "WORKING_CAKE_MEMO.docx")
            try:
                shutil.copy2(template_path, working_file)
            except Exception as e:
                print(f"[CakeMemo] Error copying template: {e}")
                working_file = template_path

            self._log(f"Opening Cake Memo template in OfficeViewer: {os.path.basename(working_file)}")
            self.cake_office_viewer.open_file(working_file)
        except Exception as e:
            self._log(f"Template open error: {e}", "ERROR")

    def handle_cake_save(self) -> None:
        """Save the current cake memo working document."""
        try:
            self.cake_office_viewer.save_file()
            if self.cake_office_viewer.current_filepath:
                self._log(f"Cake memo working document saved: {os.path.basename(self.cake_office_viewer.current_filepath)}")
        except Exception as e:
            self._log(f"Save error: {e}", "ERROR")

    def handle_cake_close(self) -> None:
        """Close the cake memo document without saving."""
        try:
            if self.cake_office_viewer.current_filepath:
                self._log(f"Cake memo document closed: {os.path.basename(self.cake_office_viewer.current_filepath)}")
            self.cake_office_viewer.close_file()
        except Exception as e:
            self._log(f"Close error: {e}", "ERROR")

    def handle_cake_save_and_close(self) -> None:
        """Trigger save and close on the cake OfficeViewer."""
        self.cake_office_viewer.save_and_close()

    def _handle_cake_save_and_close(self, filepath: str) -> None:
        """
        Executes Save As pipeline:
        1. Read and parse Word table content using python-docx.
        2. Extract ROOM NUMBER, Location, Time, Date.
        3. Determine destination: OUTPUT/CAKE_MEMOS/GR CAKE MEMO MM.yyyy/
        4. Filename: ROOM {roomNumber} CAKE MEMO ({dd.MM.yyyy}).docx (with collision handling).
        5. Move / Save final document.
        6. Generate Automated Outlook Draft.
        """
        try:
            self._log("Parsing Cake Memo table content...")
            memo_data = parse_cake_memo_docx(filepath)

            room_num = memo_data["room_number"]
            dest_folder = os.path.join(OUTPUT_DIR, "CAKE_MEMOS", f"GR CAKE MEMO {memo_data['memo_month_year']}")
            os.makedirs(dest_folder, exist_ok=True)

            base_dest_name = f"ROOM {room_num} CAKE MEMO ({memo_data['cake_date_file']})"
            dest_path = os.path.join(dest_folder, f"{base_dest_name}.docx")

            # Collision Handling
            counter = 2
            if os.path.exists(dest_path):
                dest_path = os.path.join(dest_folder, f"{base_dest_name} UPDATED.docx")
                while os.path.exists(dest_path):
                    dest_path = os.path.join(dest_folder, f"{base_dest_name} UPDATED ({counter}).docx")
                    counter += 1

            shutil.copy2(filepath, dest_path)
            self._log(f"Cake memo saved to: {os.path.basename(dest_path)}", "SUCCESS")

            # Route as To-Do Task
            self._log("Routing Cake Memo Outlook draft to To-Do List...")
            try:
                payload = generate_cake_memo_outlook_payload(dest_path, memo_data)
                self.task_generated.emit(f"Send Cake Memo Email for R{room_num}", payload)
                self._log(f"Cake Memo task generated for Room {room_num}.", "SUCCESS")
                QMessageBox.information(
                    self,
                    "Cake Memo Processed",
                    f"Cake Memo saved successfully!\n\n"
                    f"• Room: {room_num}\n"
                    f"• Date: {memo_data['cake_date_display']}\n"
                    f"• Location: {memo_data['cake_location']}\n"
                    f"• Time: {memo_data['cake_time']}\n"
                    f"• Saved To: {os.path.basename(dest_path)}\n\n"
                    f"A task to send the Outlook email has been added to the To-Do List."
                )
            except Exception as task_err:
                self._log(f"Task generation failed: {task_err}", "WARNING")
                QMessageBox.warning(
                    self,
                    "Cake Memo Saved (Task Warning)",
                    f"Cake Memo was saved to:\n{dest_path}\n\n"
                    f"However, the To-Do task could not be generated:\n{task_err}"
                )

        except Exception as e:
            self._log(f"Error in Cake Memo pipeline: {e}", "ERROR")
            QMessageBox.critical(self, "Pipeline Error", f"Failed to process Cake Memo:\n{str(e)}")

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            self.open_cake_memo_template()
        except Exception as e:
            print(f"[CakeMemo] Activation error: {e}")
