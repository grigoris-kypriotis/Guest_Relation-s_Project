import os
import sys
import shutil
import tempfile
import unittest
from datetime import date
from unittest.mock import patch, MagicMock
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from OPTIONS.configuration_option import ConfigurationWidget


class TestInHouseBackup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_inhouse_backup_")
        self.temp_backup_dir = os.path.join(self.temp_dir, "DATA_BACKUP")
        self.source_dir = os.path.join(self.temp_dir, "SOURCE")
        os.makedirs(self.source_dir, exist_ok=True)

        self.sample_csv_path = os.path.join(self.source_dir, "in_house_manifest.csv")
        self.sample_content = "Room;Guest;Arrival;Departure\n101;John Doe;01/06/2025;05/06/2025\n"
        with open(self.sample_csv_path, "w", encoding="cp1253") as f:
            f.write(self.sample_content)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backup_copy_success(self):
        """
        Test that loading an in-house file creates a backup copy in DATA_BACKUP_DIR
        with the expected naming format and preserves the original file untouched.
        """
        widget = ConfigurationWidget()
        mock_dm = MagicMock()
        mock_dm.parse_in_house_file.return_value = {"101": {"guest": "John Doe"}}
        mock_dm.compare_and_update.return_value = {
            "total_in_house": 1,
            "room_moves": [],
            "check_outs": []
        }
        widget.data_manager = mock_dm

        rep_date = date(2025, 6, 1)

        with patch("OPTIONS.configuration_option.QFileDialog.getOpenFileName", return_value=(self.sample_csv_path, "")), \
             patch("OPTIONS.configuration_option.extract_inhouse_report_date", return_value=(rep_date, "01/06/2025 10:00")), \
             patch("OPTIONS.configuration_option.DATA_BACKUP_DIR", self.temp_backup_dir), \
             patch("OPTIONS.configuration_option.QMessageBox.question", return_value=16384):  # QMessageBox.StandardButton.Yes
            widget.load_inhouse_list()

        # Verify exactly one file created in backup dir
        backup_files = os.listdir(self.temp_backup_dir)
        self.assertEqual(len(backup_files), 1)

        expected_backup_name = f"in_house_manifest_{rep_date.strftime('%Y-%m-%d')}.csv"
        self.assertEqual(backup_files[0], expected_backup_name)

        # Verify content of backup file
        backup_file_path = os.path.join(self.temp_backup_dir, expected_backup_name)
        with open(backup_file_path, "r", encoding="cp1253") as f:
            self.assertEqual(f.read(), self.sample_content)

        # Verify original source file still exists and is untouched
        self.assertTrue(os.path.exists(self.sample_csv_path))
        with open(self.sample_csv_path, "r", encoding="cp1253") as f:
            self.assertEqual(f.read(), self.sample_content)

    def test_backup_copy_failure_does_not_block_ingestion(self):
        """
        Test that if backup copying raises an exception (e.g. unwritable destination),
        the exception is caught and the ingestion flow still completes successfully.
        """
        widget = ConfigurationWidget()
        mock_dm = MagicMock()
        mock_dm.parse_in_house_file.return_value = {"101": {"guest": "John Doe"}}
        mock_dm.compare_and_update.return_value = {
            "total_in_house": 1,
            "room_moves": [],
            "check_outs": []
        }
        widget.data_manager = mock_dm

        rep_date = date(2025, 6, 1)
        signal_emitted = []
        widget.data_updated.connect(lambda: signal_emitted.append(True))

        with patch("OPTIONS.configuration_option.QFileDialog.getOpenFileName", return_value=(self.sample_csv_path, "")), \
             patch("OPTIONS.configuration_option.extract_inhouse_report_date", return_value=(rep_date, "01/06/2025 10:00")), \
             patch("OPTIONS.configuration_option.DATA_BACKUP_DIR", self.temp_backup_dir), \
             patch("OPTIONS.configuration_option.shutil.copy2", side_effect=PermissionError("Simulated backup failure")), \
             patch("OPTIONS.configuration_option.QMessageBox.question", return_value=16384):
            # Must not raise
            try:
                widget.load_inhouse_list()
            except Exception as e:
                self.fail(f"load_inhouse_list raised an unexpected exception: {e}")

        # Verify signal was still emitted
        self.assertEqual(len(signal_emitted), 1)
        # Verify active_in_house_list was set
        self.assertEqual(widget.active_in_house_list, "2025-06-01")

    def test_ensure_workspace_directories_creates_backup_dir(self):
        """
        Verify that ensure_workspace_directories includes DATA_BACKUP_DIR in creation.
        """
        from MODULES.common.paths_config import ensure_workspace_directories
        test_backup = os.path.join(self.temp_dir, "ENSURE_BACKUP")
        with patch("MODULES.common.paths_config.DATA_BACKUP_DIR", test_backup), \
             patch("MODULES.common.paths_config.DATABASE_DIR", os.path.join(self.temp_dir, "DB")), \
             patch("MODULES.common.paths_config.HOTEL_STATE_DIR", os.path.join(self.temp_dir, "HS")), \
             patch("MODULES.common.paths_config.BOOKING_CALLS_TODAY_DIR", os.path.join(self.temp_dir, "BC")), \
             patch("MODULES.common.paths_config.CHECKOUT_HISTORY_DIR", os.path.join(self.temp_dir, "CO")), \
             patch("MODULES.common.paths_config.ROOM_MOVES_DIR", os.path.join(self.temp_dir, "RM")), \
             patch("MODULES.common.paths_config.SANDY_BEACH_DIR", os.path.join(self.temp_dir, "SB")), \
             patch("MODULES.common.paths_config.SANDY_BEACH_ARRIVALS_DIR", os.path.join(self.temp_dir, "SBA")), \
             patch("MODULES.common.paths_config.SANDY_BEACH_DEPARTURE_DIR", os.path.join(self.temp_dir, "SBD")), \
             patch("MODULES.common.paths_config.TEMPLATES_DIR", os.path.join(self.temp_dir, "TPL")), \
             patch("MODULES.common.paths_config.OUTPUT_DIR", os.path.join(self.temp_dir, "OUT")), \
             patch("MODULES.common.paths_config.TODAYS_LIST_DIR", os.path.join(self.temp_dir, "TL")), \
             patch("MODULES.common.paths_config.TRASH_DIR", os.path.join(self.temp_dir, "TR")), \
             patch("MODULES.common.paths_config.BOOKING_CALLS_DIR", os.path.join(self.temp_dir, "BCD")), \
             patch("MODULES.common.paths_config.PLOT_DIR", os.path.join(self.temp_dir, "PLD")):
            ensure_workspace_directories()
            self.assertTrue(os.path.isdir(test_backup))


if __name__ == "__main__":
    unittest.main()
