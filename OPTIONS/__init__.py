"""
Options Package: Modular menu option registry for Guest Relation Workspace.
===========================================================================
Each option module provides a dedicated QWidget subclass with an activate() method.
The OPTION_REGISTRY maps menu keys to their widget classes for dictionary-based dispatch.
"""

from OPTIONS.configuration_option import ConfigurationWidget
from OPTIONS.stats_option import StatsWidget
from OPTIONS.moves_option import MovesWidget
from OPTIONS.todo_option import TodoWidget
from OPTIONS.offers_option import OffersOptionWidget
from OPTIONS.allergies_option import AllergiesWidget
from OPTIONS.cake_memo_option import CakeMemoOptionWidget
from OPTIONS.booking_calls_option import BookingCallsOptionWidget
from OPTIONS.system_data_option import SystemDataOptionWidget
from OPTIONS.logs_option import LogsWidget

# Dispatch table: maps menu category keys to widget classes.
# Each class must implement activate() -> None.
OPTION_REGISTRY = {
    "CONFIG":      ConfigurationWidget,
    "STATS":       StatsWidget,
    "MOVES":       MovesWidget,
    "TODO":        TodoWidget,
    "OFFERS":      OffersOptionWidget,
    "ALLERGIES":   AllergiesWidget,
    "CAKE":        CakeMemoOptionWidget,
    "BOOKING":     BookingCallsOptionWidget,
    "SYSTEM_DATA": SystemDataOptionWidget,
    "LOGS":        LogsWidget,
}

__all__ = [
    "OPTION_REGISTRY",
    "ConfigurationWidget",
    "StatsWidget",
    "MovesWidget",
    "TodoWidget",
    "OffersOptionWidget",
    "AllergiesWidget",
    "CakeMemoOptionWidget",
    "BookingCallsOptionWidget",
    "SystemDataOptionWidget",
    "LogsWidget",
]
