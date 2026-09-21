"""
Unit & Regression Tests for ChartCardWidget Badge Rendering (Stage 3c)
======================================================================
Tests:
  1. Direct verification of _with_alpha producing Qt #AARRGGBB format.
  2. Construction of ChartCardWidget in isolation using headless Qt offscreen platform.
  3. Verification that set_badges() builds stylesheets with valid #AARRGGBB tokens.
  4. Assertion that old buggy {color}15 / {color}50 suffix concatenation is absent.
"""

import unittest
from PyQt6.QtWidgets import QApplication

from OPTIONS._shared_widgets import _with_alpha, ChartCardWidget


class TestChartCardBadges(unittest.TestCase):
    """Hermetic unit tests for ChartCardWidget badge styling and _with_alpha."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["", "-platform", "offscreen"])

    def test_with_alpha_hex_argb_generation(self):
        """Verify _with_alpha formats 6-digit hex colors to 8-digit #AARRGGBB."""
        # Downgrades color (#EF4444)
        bg_red = _with_alpha("#EF4444", 21)
        border_red = _with_alpha("#EF4444", 80)
        self.assertEqual(bg_red.lower(), "#15ef4444")
        self.assertEqual(border_red.lower(), "#50ef4444")

        # Upgrades color (#3B82F6)
        bg_blue = _with_alpha("#3B82F6", 21)
        border_blue = _with_alpha("#3B82F6", 80)
        self.assertEqual(bg_blue.lower(), "#153b82f6")
        self.assertEqual(border_blue.lower(), "#503b82f6")

        # Exact Matches color (#10B981)
        bg_green = _with_alpha("#10B981", 21)
        border_green = _with_alpha("#10B981", 80)
        self.assertEqual(bg_green.lower(), "#1510b981")
        self.assertEqual(border_green.lower(), "#5010b981")

    def test_set_badges_pill_stylesheet(self):
        """Verify ChartCardWidget.set_badges builds pills with valid #AARRGGBB stylesheets."""
        card = ChartCardWidget(title="Room Type Upgrade / Downgrade", subtitle="Test Card")
        badges = [
            ("Upgrades", 5, "#3B82F6"),
            ("Downgrades", 11, "#EF4444"),
            ("Exact Matches", 42, "#10B981"),
        ]
        card.set_badges(badges)

        self.assertEqual(card.badge_box.count(), 3)

        for idx, (label, val, color) in enumerate(badges):
            pill = card.badge_box.itemAt(idx).widget()
            self.assertIsNotNone(pill)
            ss = pill.styleSheet().lower()

            # Assert valid #AARRGGBB color tokens present
            expected_bg = _with_alpha(color, 21).lower()
            expected_border = _with_alpha(color, 80).lower()
            self.assertIn(expected_bg, ss)
            self.assertIn(expected_border, ss)

            # Assert old malformed {color}XX pattern is NOT present
            malformed_bg = f"{color}15".lower()
            malformed_border = f"{color}50".lower()
            self.assertNotIn(malformed_bg, ss)
            self.assertNotIn(malformed_border, ss)


if __name__ == "__main__":
    unittest.main()
