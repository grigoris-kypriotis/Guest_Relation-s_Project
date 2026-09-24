"""
Card Ingestion: In-house list loading and database maintenance.
================================================================
Provides build_ingestion_card() builder and IngestionMixin with data ingestion
and database maintenance methods.
"""

import os
import shutil
from datetime import date, datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QLineEdit, QDateEdit,
    QFileDialog, QMessageBox, QDialog, QVBoxLayout, QDialogButtonBox
)
from PyQt6.QtCore import QDate, Qt, QTimer

from MODULES.data_manager import (
    extract_inhouse_report_date, validate_inhouse_file_date,
    BASE_DIR, BOOKING_CALLS_DIR
)
from MODULES.common.paths_config import DATA_BACKUP_DIR
from OPTIONS.configuration.card_shared import create_card, btn_browse_style


def build_ingestion_card(widget) -> QFrame:
    """
    Builds the In-House List Ingestion card (Card 1) with inline date override row.

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.txt_timestamp (QLineEdit, read-only)
            - widget.btn_load_inhouse (QPushButton)
            - widget.date_override (QDateEdit)

    Returns:
        QFrame containing the ingestion card layout
    """
    card_inhouse = create_card("\U0001f4c2 IN-HOUSE LIST INGESTION", accent_color="#1E3A8A")
    ih_layout = card_inhouse.layout()

    ih_desc = QLabel("Load today's In-House List from your PMS export. This is the primary data source for all Stats, Occupancy, and Guest Manifest views.")
    ih_desc.setStyleSheet("color: #64748B; font-size: 11px; border: none;")
    ih_desc.setWordWrap(True)
    ih_layout.addWidget(ih_desc)

    # Status display
    widget.txt_timestamp = QLineEdit("No In-House List Loaded")
    widget.txt_timestamp.setReadOnly(True)
    widget.txt_timestamp.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 8px 12px; border: 1px solid #FECACA; border-radius: 6px;")
    ih_layout.addWidget(widget.txt_timestamp)

    # Load button row
    row_load = QHBoxLayout()
    widget.btn_load_inhouse = QPushButton("\U0001f4c2 Load In-House List (.xlsx / .xls / .csv)")
    widget.btn_load_inhouse.setStyleSheet("""
        QPushButton {
            background-color: #1E3A8A;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 10px 22px;
            border-radius: 6px;
            border: none;
        }
        QPushButton:hover { background-color: #2563EB; }
    """)
    widget.btn_load_inhouse.clicked.connect(widget.load_inhouse_list)
    row_load.addWidget(widget.btn_load_inhouse)
    row_load.addStretch()
    ih_layout.addLayout(row_load)

    # Gatekeeper Override (compact, inline)
    row_override = QHBoxLayout()
    lbl_override = QLabel("Manual Date Override:")
    lbl_override.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; border: none;")
    widget.date_override = QDateEdit()
    widget.date_override.setCalendarPopup(True)
    widget.date_override.setDate(QDate.currentDate())
    widget.date_override.setDisplayFormat("dd/MM/yyyy")
    widget.date_override.setFixedWidth(130)
    widget.date_override.setStyleSheet("padding: 4px; border: 1px solid #CBD5E1; border-radius: 4px; background: white;")

    btn_apply_override = QPushButton("Apply")
    btn_apply_override.setStyleSheet("""
        QPushButton {
            background-color: #475569;
            color: white;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover { background-color: #334155; }
    """)
    btn_apply_override.clicked.connect(widget._apply_date_override)

    row_override.addWidget(lbl_override)
    row_override.addWidget(widget.date_override)
    row_override.addWidget(btn_apply_override)
    row_override.addStretch()
    ih_layout.addLayout(row_override)

    return card_inhouse


class IngestionMixin:
    """
    Mixin providing in-house list ingestion and database maintenance methods.

    Expected to be mixed into ConfigurationWidget. Requires:
        - self.data_manager (InHouseDataManager)
        - self.data_updated signal
        - self.txt_timestamp, self.date_override (from build_ingestion_card)
    """

    def refresh_timestamp_display(self) -> None:
        """Updates the timestamp display based on current master state."""
        master = self.data_manager.load_master_state()
        meta = self.data_manager.load_metadata()
        sync_date = meta.get("last_sync_date") or meta.get("last_processed_date")
        last_updated = meta.get("last_updated_at")

        if master and sync_date:
            ts_str = str(last_updated).split(".")[0].replace("T", " ") if last_updated else "N/A"
            self.txt_timestamp.setText(f"✅ Operational Date: {sync_date}  |  Last Synced: {ts_str}  ({len(master)} Active Bookings)")
            self.txt_timestamp.setStyleSheet("background-color: #ECFDF5; color: #2563EB; font-weight: bold; padding: 8px 12px; border: 1px solid #A7F3D0; border-radius: 6px;")
        else:
            self.txt_timestamp.setText("⚠️ No In-House List Loaded — Load one to populate Stats and Guest Manifest")
            self.txt_timestamp.setStyleSheet("background-color: #FEF2F2; color: #991B1B; font-weight: bold; padding: 8px 12px; border: 1px solid #FECACA; border-radius: 6px;")

    def _prompt_for_operational_date(self, title: str, message: str, default_date: Optional[date] = None) -> Optional[date]:
        """Prompts user for operational date confirmation via dialog."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return default_date or date.today()

        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(400, 190)
        dlg.setStyleSheet("background-color: #FFFFFF; font-family: 'Segoe UI', Arial, sans-serif;")
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 13px; color: #1F2937;")
        layout.addWidget(lbl)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        init_d = default_date or date.today()
        date_edit.setDate(QDate(init_d.year, init_d.month, init_d.day))
        date_edit.setStyleSheet("padding: 6px; font-size: 13px; border: 1px solid #D1D5DB; border-radius: 4px;")
        layout.addWidget(date_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            qd = date_edit.date()
            return date(qd.year(), qd.month(), qd.day())
        return None

    def load_inhouse_list(self) -> None:
        """Loads an in-house list from disk, validates date, and ingests into database."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select In-House List",
            BASE_DIR,
            "In-House Files (*.xlsx *.xls *.csv);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*.*)"
        )
        if not file_path:
            return

        extracted_dt, ts_str = extract_inhouse_report_date(file_path)
        target_today = date.today()

        rep_date = extracted_dt
        if rep_date is None:
            rep_date = self._prompt_for_operational_date(
                "Operational Date Required",
                f"No date was detected in '{os.path.basename(file_path)}'.\n"
                "Please confirm the operational date for this In-House list:",
                default_date=target_today
            )
            if not rep_date:
                return
        elif rep_date != target_today:
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                reply = QMessageBox.question(
                    self,
                    "Operational Date Confirmation",
                    f"Selected In-House List operational date:\n"
                    f"  📅 {rep_date.strftime('%Y-%m-%d')} ({rep_date.strftime('%A')})\n\n"
                    f"Today's system calendar date is {target_today.strftime('%Y-%m-%d')}.\n\n"
                    f"Do you want to ingest this In-House List for operational date {rep_date.strftime('%Y-%m-%d')}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        try:
            parsed = self.data_manager.parse_in_house_file(file_path)
            if not parsed:
                if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                    QMessageBox.warning(self, "Empty Dataset", "No valid bookings were found in the selected file.")
                return

            summary = self.data_manager.compare_and_update(parsed, processing_date=rep_date)

            try:
                os.makedirs(DATA_BACKUP_DIR, exist_ok=True)
                name_part, ext = os.path.splitext(os.path.basename(file_path))
                date_tag = rep_date.strftime('%Y-%m-%d') if rep_date else datetime.now().strftime('%Y-%m-%d')
                backup_filename = f"{name_part}_{date_tag}{ext}"
                shutil.copy2(file_path, os.path.join(DATA_BACKUP_DIR, backup_filename))
            except Exception:
                pass

            self.active_in_house_list = rep_date.strftime('%Y-%m-%d') if rep_date else file_path
            self.refresh_timestamp_display()
            self.data_updated.emit()

            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.information(
                    self,
                    "Ingestion Successful",
                    f"In-House List ingested successfully!\n\n"
                    f"• Operational Date: {rep_date.strftime('%Y-%m-%d')}\n"
                    f"• Active In-House Bookings: {summary['total_in_house']}\n"
                    f"• Room Moves Detected: {len(summary['room_moves'])}\n"
                    f"• Check-Outs Archived: {len(summary['check_outs'])}\n\n"
                    f"All Room Block JSON metrics have been synchronized in PLOT/."
                )
        except Exception as e:
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.critical(self, "Ingestion Error", f"Failed to ingest In-House List:\n{str(e)}")

    def clear_hotel_database(self) -> None:
        """Purges the hotel database after confirmation."""
        confirm = QMessageBox.warning(
            self,
            "Confirm Database Reset",
            "This operation will purge guest manifests, reservation records, offer lists, and cake memos from all system JSON storage.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        second_confirm = QMessageBox.critical(
            self,
            "Final Warning: Atomic Purge",
            "This action is irreversible and will permanently delete all operational data.\n\nAre you absolutely sure you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if second_confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            res = self.data_manager.purge_hotel_database()
            purged_count = res.get("purged_count", 0) if isinstance(res, dict) else 0
            self.active_in_house_list = None
            self.refresh_timestamp_display()
            self.data_updated.emit()
            QMessageBox.information(
                self,
                "Purge Complete",
                f"Database cleared successfully. {purged_count} JSON records, active traces, and caches were reset."
            )
        except Exception as e:
            QMessageBox.critical(self, "Purge Error", f"Failed to clear hotel database:\n{str(e)}")

    def refresh_block_exports(self) -> None:
        """Debounced refresh of room block exports."""
        if not hasattr(self, '_debounce_timer'):
            self._debounce_timer = QTimer(self)
            self._debounce_timer.setSingleShot(True)
            self._debounce_timer.timeout.connect(self._do_refresh_block_exports)
        self._debounce_timer.start(400)

    def _do_refresh_block_exports(self) -> None:
        """Actually performs the room block export refresh."""
        try:
            res = self.data_manager.export_room_block_json_data()
            self.data_updated.emit()
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {res['total_exported']} room block JSON payloads to PLOT/."
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export room blocks:\n{str(e)}")

    def _apply_date_override(self) -> None:
        """Applies the manual date override."""
        qdt = self.date_override.date()
        target_d = date(qdt.year(), qdt.month(), qdt.day())
        try:
            self.data_manager.set_last_sync_date(target_d)
            self.refresh_timestamp_display()
            self.data_updated.emit()
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.information(
                    self,
                    "Override Applied",
                    f"Operational date override applied successfully: {target_d.strftime('%Y-%m-%d')}"
                )
        except Exception as e:
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.critical(self, "Override Error", f"Failed to apply operational date override:\n{e}")

    def activate(self) -> None:
        """Called when this option is selected from the menu."""
        try:
            from OPTIONS.configuration_option import load_app_settings
            self.current_settings = load_app_settings()
            self.populate_settings_ui()
            self.refresh_timestamp_display()
        except Exception as e:
            print(f"[Configuration] Activation error: {e}")
