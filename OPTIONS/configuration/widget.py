"""Configuration Widget."""
import os
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame
from PyQt6.QtCore import pyqtSignal
from MODULES.data_manager import InHouseDataManager, DATABASE_DIR, TEMPLATES_DIR, BOOKING_CALLS_DIR, OUTPUT_DIR
from OPTIONS.configuration.settings_store import load_app_settings
from OPTIONS.configuration.card_ingestion import build_ingestion_card, IngestionMixin
from OPTIONS.configuration.card_properties_locations import build_properties_card, build_data_locations_card, LocationsMixin
from OPTIONS.configuration.card_booking_exclusivi import build_booking_calls_card, build_exclusivi_card, ExclusiviMixin
from OPTIONS.configuration.card_storage import build_storage_card, StorageMixin
from OPTIONS.configuration.card_preferences_actions_purge import build_preferences_card, build_actions_card, build_purge_card

class ConfigurationWidget(QWidget, IngestionMixin, LocationsMixin, ExclusiviMixin, StorageMixin):
    """Configuration Page widget."""
    data_updated = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data_manager = InHouseDataManager()
        self.current_settings = load_app_settings()
        self.active_in_house_list = None
        self._init_ui()
        self.populate_settings_ui()
        self.refresh_timestamp_display()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        lbl_title = QLabel("SYSTEM CONFIGURATION & WORKSPACE PREFERENCES")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #800020;")
        main_layout.addWidget(lbl_title)
        cfg_scroll = QScrollArea()
        cfg_scroll.setWidgetResizable(True)
        cfg_content = QWidget()
        scroll_layout = QVBoxLayout(cfg_content)
        scroll_layout.addWidget(build_ingestion_card(self))
        scroll_layout.addWidget(build_properties_card(self))
        scroll_layout.addWidget(build_data_locations_card(self))
        scroll_layout.addWidget(build_booking_calls_card(self))
        scroll_layout.addWidget(build_exclusivi_card(self))
        scroll_layout.addWidget(build_storage_card(self))
        scroll_layout.addWidget(build_preferences_card(self))
        scroll_layout.addWidget(build_actions_card(self))
        scroll_layout.addWidget(build_purge_card(self))
        scroll_layout.addStretch()
        cfg_scroll.setWidget(cfg_content)
        main_layout.addWidget(cfg_scroll)

    def populate_settings_ui(self) -> None:
        s = self.current_settings
        props = s.get("properties", {})
        self.spin_beach_rooms.setValue(int(props.get("sandy_beach_rooms", 660)))
        paths = s.get("paths", {})
        self.txt_database_dir.setText(str(paths.get("database_dir", DATABASE_DIR)))
        self.txt_templates_dir.setText(str(paths.get("templates_dir", TEMPLATES_DIR)))
        self.txt_booking_calls_path.setText(str(paths.get("booking_calls_workbook", os.path.join(BOOKING_CALLS_DIR, "BOOKING CALLS.xlsx"))))
        bc = s.get("booking_calls", {})
        self.txt_sheet_name.setText(str(bc.get("sheet_name", "FOLLOW UP")))
        self.chk_mirror_sheet.setChecked(bool(bc.get("mirror_follow_up_1", True)))
        ex = s.get("exclusivi", {})
        self.chk_exclusivi_enabled.setChecked(bool(ex.get("enabled", False)))
        self.txt_exclusivi_url.setText(str(ex.get("api_base_url", "")))
        self.txt_exclusivi_key.setText(str(ex.get("api_key", "")))
        self._toggle_exclusivi_fields(self.chk_exclusivi_enabled.isChecked())
        storage = s.get("storage", {})
        self.txt_offer_lists_dir.setText(str(storage.get("offer_lists_dir", os.path.join(OUTPUT_DIR, "OFFERS"))))
        self.txt_cake_memos_dir.setText(str(storage.get("cake_memos_dir", os.path.join(OUTPUT_DIR, "CAKE_MEMOS"))))
        prefs = s.get("preferences", {})
        self.chk_fit_view.setChecked(bool(prefs.get("default_fit_view", True)))
        self.combo_prop.setCurrentIndex(0)
        self.combo_mode.setCurrentIndex(0)
        last_saved = s.get("last_saved")
        if last_saved:
            self.lbl_saved_timestamp.setText(f"Last saved: {last_saved}")
        self._refresh_storage_summary()

    def collect_settings_from_ui(self) -> Dict[str, Any]:
        return {
            "properties": {"sandy_beach_rooms": self.spin_beach_rooms.value()},
            "paths": {"database_dir": self.txt_database_dir.text().strip(), "templates_dir": self.txt_templates_dir.text().strip(), "booking_calls_workbook": self.txt_booking_calls_path.text().strip()},
            "booking_calls": {"sheet_name": self.txt_sheet_name.text().strip(), "mirror_follow_up_1": self.chk_mirror_sheet.isChecked()},
            "exclusivi": {"enabled": self.chk_exclusivi_enabled.isChecked(), "api_base_url": self.txt_exclusivi_url.text().strip(), "api_key": self.txt_exclusivi_key.text().strip(), "last_test_status": self.current_settings.get("exclusivi", {}).get("last_test_status"), "last_test_timestamp": self.current_settings.get("exclusivi", {}).get("last_test_timestamp")},
            "storage": {"offer_lists_dir": self.txt_offer_lists_dir.text().strip(), "cake_memos_dir": self.txt_cake_memos_dir.text().strip()},
            "preferences": {"default_fit_view": self.chk_fit_view.isChecked(), "active_property": self.combo_prop.currentText(), "operational_mode": self.combo_mode.currentText()},
        }

    def save_configuration(self, show_dialog: bool = True) -> bool:
        from OPTIONS.configuration.settings_store import save_app_settings
        from PyQt6.QtWidgets import QMessageBox
        new_settings = self.collect_settings_from_ui()
        success = save_app_settings(new_settings)
        if success:
            self.current_settings = load_app_settings()
            self.data_updated.emit()
            if show_dialog and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.information(self, "Configuration Saved", "Settings saved successfully.")
        return success

    def reload_configuration(self, show_dialog: bool = True) -> None:
        from PyQt6.QtWidgets import QMessageBox
        self.current_settings = load_app_settings()
        self.populate_settings_ui()
        if show_dialog and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            QMessageBox.information(self, "Settings Reloaded", "Settings reloaded from disk.")
