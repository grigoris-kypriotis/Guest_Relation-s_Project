"""
Shared UI Widgets Package: Infrastructure-level components used across multiple option modules.
=====================================================================================
Extracted from the original monolithic _shared_widgets.py to comply with file size limits.
Contains no business logic — only UI structure and COM/Office integration.
"""

from OPTIONS._shared.nav import HamburgerButton, Sidebar
from OPTIONS._shared.task_widget import TaskWidget
from OPTIONS._shared.office_viewer import OfficeViewer
from OPTIONS._shared.workspace_viewer import WorkspaceViewerDialog
from OPTIONS._shared.chart_card import ChartCardWidget, _with_alpha
from OPTIONS._shared.mpl_helpers import WheelPassThroughFilter, NonScrollableFigureCanvas

__all__ = [
    "HamburgerButton",
    "Sidebar",
    "TaskWidget",
    "OfficeViewer",
    "WorkspaceViewerDialog",
    "ChartCardWidget",
    "_with_alpha",
    "WheelPassThroughFilter",
    "NonScrollableFigureCanvas",
]
