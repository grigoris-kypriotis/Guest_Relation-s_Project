"""
Settings Store: Application settings persistence.
==================================================
Handles loading and saving app configuration from/to DATABASE/app_settings.json.
Uses deferred facade import to respect monkeypatches from tests.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any

from MODULES.data_manager import (
    DATABASE_DIR, OUTPUT_DIR, TEMPLATES_DIR, BOOKING_CALLS_DIR,
)

APP_SETTINGS_PATH = os.path.join(DATABASE_DIR, "app_settings.json")

DEFAULT_APP_SETTINGS: Dict[str, Any] = {
    "properties": {
        "sandy_beach_rooms": 660,
    },
    "paths": {
        "database_dir": DATABASE_DIR,
        "templates_dir": TEMPLATES_DIR,
        "booking_calls_workbook": os.path.join(BOOKING_CALLS_DIR, "BOOKING CALLS.xlsx"),
    },
    "booking_calls": {
        "sheet_name": "FOLLOW UP",
        "mirror_follow_up_1": True,
    },
    "exclusivi": {
        "enabled": False,
        "api_base_url": "",
        "api_key": "",
        "last_test_status": None,
        "last_test_timestamp": None,
    },
    "storage": {
        "offer_lists_dir": os.path.join(OUTPUT_DIR, "OFFERS"),
        "cake_memos_dir": os.path.join(OUTPUT_DIR, "CAKE_MEMOS"),
    },
    "preferences": {
        "default_fit_view": True,
        "active_property": "Sandy Beach (Exclusive Active Property)",
        "operational_mode": "Production (Standard Gatekeeper & Centralized Database)",
    },
    "last_saved": None,
}


def load_app_settings() -> Dict[str, Any]:
    """Safely loads app settings from DATABASE/app_settings.json with defaults fallback.

    Uses deferred import of facade to respect test monkeypatches on APP_SETTINGS_PATH.
    """
    from OPTIONS import configuration_option as facade

    if os.path.exists(facade.APP_SETTINGS_PATH):
        try:
            with open(facade.APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings = json.loads(json.dumps(facade.DEFAULT_APP_SETTINGS))
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(settings.get(k), dict):
                    settings[k].update(v)
                else:
                    settings[k] = v
            return settings
        except Exception as e:
            print(f"[Configuration] Error loading settings: {e}")
    return json.loads(json.dumps(facade.DEFAULT_APP_SETTINGS))


def save_app_settings(settings: Dict[str, Any]) -> bool:
    """Persists app settings to DATABASE/app_settings.json.

    Uses deferred import of facade to respect test monkeypatches on APP_SETTINGS_PATH.
    """
    from OPTIONS import configuration_option as facade

    try:
        os.makedirs(os.path.dirname(facade.APP_SETTINGS_PATH), exist_ok=True)
        settings["last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(facade.APP_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Configuration] Error saving settings: {e}")
        return False
