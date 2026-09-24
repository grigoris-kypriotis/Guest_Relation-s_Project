"""
Configuration Option: Re-export Facade
=======================================
Maintains 100% backward-compatible API access for all callers.
Delegates to modular subpackage OPTIONS.configuration:
  - OPTIONS.configuration.settings_store (APP_SETTINGS_PATH, DEFAULT_APP_SETTINGS, load/save functions)
  - OPTIONS.configuration.widget (ConfigurationWidget)
"""

from OPTIONS.configuration.settings_store import (
    APP_SETTINGS_PATH, DEFAULT_APP_SETTINGS, load_app_settings, save_app_settings,
)
from OPTIONS.configuration.widget import ConfigurationWidget

__all__ = [
    "ConfigurationWidget", 
    "load_app_settings", 
    "save_app_settings", 
    "APP_SETTINGS_PATH", 
    "DEFAULT_APP_SETTINGS"
]
