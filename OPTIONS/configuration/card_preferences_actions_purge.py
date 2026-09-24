"""
Card Preferences, Actions & Purge: Workspace settings and maintenance.
======================================================================
Provides builders for Workspace Preferences (Card 7), Actions & Settings
Persistence (Card 8), and Database Purge & Reset (Card 9).
"""

import os

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QCheckBox, QComboBox,
)

from OPTIONS.configuration.card_shared import create_card


def build_preferences_card(widget) -> QFrame:
    """
    Builds the Workspace Preferences card (Card 7).

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.chk_fit_view (QCheckBox)
            - widget.combo_prop (QComboBox)
            - widget.combo_mode (QComboBox)

    Returns:
        QFrame containing the preferences card layout
    """
    card_prefs = create_card("\U0001f3a8 WORKSPACE PREFERENCES")
    p_layout = card_prefs.layout()

    widget.chk_fit_view = QCheckBox("Default 2D Map to 'Fit View' upon launch")
    widget.chk_fit_view.setChecked(True)
    widget.chk_fit_view.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    p_layout.addWidget(widget.chk_fit_view)

    row_prop = QHBoxLayout()
    lbl_prop = QLabel("Active Property Target:")
    lbl_prop.setFixedWidth(230)
    lbl_prop.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.combo_prop = QComboBox()
    widget.combo_prop.addItems(["Sandy Beach (Exclusive Active Property)"])
    widget.combo_prop.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
    row_prop.addWidget(lbl_prop)
    row_prop.addWidget(widget.combo_prop)
    row_prop.addStretch()
    p_layout.addLayout(row_prop)

    row_mode = QHBoxLayout()
    lbl_mode = QLabel("Operational Mode:")
    lbl_mode.setFixedWidth(230)
    lbl_mode.setStyleSheet("font-weight: bold; color: #1E293B; border: none;")
    widget.combo_mode = QComboBox()
    widget.combo_mode.addItems(["Production (Standard Gatekeeper & Centralized Database)", "Debug / Diagnostic"])
    widget.combo_mode.setStyleSheet("padding: 5px; border: 1px solid #FFB6C1; border-radius: 4px; background: white;")
    row_mode.addWidget(lbl_mode)
    row_mode.addWidget(widget.combo_mode)
    row_mode.addStretch()
    p_layout.addLayout(row_mode)

    return card_prefs


def build_actions_card(widget) -> QFrame:
    """
    Builds the Actions & Settings Persistence card (Card 8).

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.btn_save_config (QPushButton)
            - widget.btn_reload_config (QPushButton)
            - widget.lbl_saved_timestamp (QLabel)

    Returns:
        QFrame containing the actions card layout
    """
    card_actions = create_card("\U0001f4be ACTIONS & SETTINGS PERSISTENCE")
    act_layout = card_actions.layout()

    row_save = QHBoxLayout()
    widget.btn_save_config = QPushButton("\U0001f4be Save Configuration")
    widget.btn_save_config.setStyleSheet("""
        QPushButton {
            background-color: #800020;
            color: white;
            font-size: 13px;
            font-weight: bold;
            padding: 9px 22px;
            border-radius: 5px;
            border: none;
        }
        QPushButton:hover { background-color: #A00028; }
    """)
    widget.btn_save_config.clicked.connect(widget.save_configuration)

    widget.btn_reload_config = QPushButton("\U0001f504 Reload Settings")
    widget.btn_reload_config.setStyleSheet("""
        QPushButton {
            background-color: #F1F5F9;
            color: #1E293B;
            font-size: 12px;
            font-weight: bold;
            padding: 9px 18px;
            border-radius: 5px;
            border: 1px solid #CBD5E1;
        }
        QPushButton:hover { background-color: #E2E8F0; }
    """)
    widget.btn_reload_config.clicked.connect(widget.reload_configuration)

    widget.lbl_saved_timestamp = QLabel("Settings not saved yet.")
    widget.lbl_saved_timestamp.setStyleSheet("color: #64748B; font-size: 11px; font-style: italic; border: none;")

    row_save.addWidget(widget.btn_save_config)
    row_save.addWidget(widget.btn_reload_config)
    row_save.addSpacing(15)
    row_save.addWidget(widget.lbl_saved_timestamp)
    row_save.addStretch()
    act_layout.addLayout(row_save)

    return card_actions


def build_purge_card(widget) -> QFrame:
    """
    Builds the Database Purge & Reset card (Card 9).

    Args:
        widget: The ConfigurationWidget instance. Assigns:
            - widget.btn_export_blocks (QPushButton)
            - widget.btn_clear_db (QPushButton)

    Returns:
        QFrame containing the purge card layout
    """
    card_danger = create_card("\U0001f5d1️ DATABASE PURGE & RESET (MAINTENANCE)", accent_color="#DC2626")
    d_layout = card_danger.layout()

    d_desc = QLabel("Clearing the database completely resets all transaction logs, guest records, memo caches, and active bookings.")
    d_desc.setWordWrap(True)
    d_desc.setStyleSheet("color: #64748b; font-size: 11px; border: none;")
    d_layout.addWidget(d_desc)

    btn_box = QHBoxLayout()
    widget.btn_export_blocks = QPushButton("\U0001f504 Refresh Block Exports")
    widget.btn_export_blocks.setStyleSheet("""
        QPushButton {
            background-color: #2563EB;
            color: white;
            font-weight: bold;
            padding: 8px 16px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover { background-color: #1D4ED8; }
    """)
    widget.btn_export_blocks.clicked.connect(widget.refresh_block_exports)
    btn_box.addWidget(widget.btn_export_blocks)

    widget.btn_clear_db = QPushButton("\U0001f5d1️ Clear Hotel Database")
    widget.btn_clear_db.setStyleSheet("""
        QPushButton {
            background-color: #ef4444;
            color: white;
            font-weight: bold;
            padding: 8px 16px;
            border-radius: 4px;
            border: none;
        }
        QPushButton:hover { background-color: #dc2626; }
    """)
    widget.btn_clear_db.clicked.connect(widget.clear_hotel_database)
    btn_box.addWidget(widget.btn_clear_db)
    btn_box.addStretch()
    d_layout.addLayout(btn_box)

    return card_danger
