"""
Analytics Registry Module
-------------------------
Keyed registry of visual operational chart specifications for the Guest Relation
Visual Analytics Suite. Decouples positional chart indexing into frozen ChartSpec
metadata descriptors.
"""

from dataclasses import dataclass
from typing import Dict, List

from MODULES.trace_analytics import (
    LENS_ALL,
    LENS_DIETARY,
    LENS_GR_TRACES,
    LENS_ROOM_STAY,
)


@dataclass(frozen=True)
class ChartSpec:
    key: str
    title: str
    subtitle: str
    icon: str
    lenses: frozenset[str]
    render_attr: str


CHART_REGISTRY: List[ChartSpec] = [
    ChartSpec(
        key="tour_operator_mix",
        title="Tour Operator / Market Mix",
        subtitle="Guest share categorized by tour operator / travel agency (operators <2% grouped into Other).",
        icon="🌍",
        lenses=frozenset({LENS_ALL}),
        render_attr="render_tour_operator_mix",
    ),
    ChartSpec(
        key="length_of_stay",
        title="Length of Stay Distribution",
        subtitle="Calculated integer nights binned into 1–3, 4–6, 7–13, and 14+ nights.",
        icon="📅",
        lenses=frozenset({LENS_ALL}),
        render_attr="render_length_of_stay",
    ),
    ChartSpec(
        key="room_type_upgrade_downgrade",
        title="Room Type Booked vs. Assigned (Upgrade/Downgrade Tracker)",
        subtitle="Comparison between Booked and Assigned room types tracking upgrades and downgrades.",
        icon="🔄",
        lenses=frozenset({LENS_ALL, LENS_ROOM_STAY}),
        render_attr="render_room_type_upgrade_downgrade",
    ),
    ChartSpec(
        key="trace_category_breakdown",
        title="Trace Category Breakdown",
        subtitle="Frequency volume across primary Guest Relation trace categories.",
        icon="📑",
        lenses=frozenset({LENS_ALL, LENS_GR_TRACES}),
        render_attr="render_trace_category_breakdown",
    ),
    ChartSpec(
        key="rcr_reason_tagging",
        title="Room Change Request: Reason Tagging",
        subtitle="Deterministic keyword classification of free-text complaint notes.",
        icon="🏷️",
        lenses=frozenset({LENS_ALL, LENS_ROOM_STAY}),
        render_attr="render_rcr_reason_tagging",
    ),
    ChartSpec(
        key="allergy_dietary_frequency",
        title="Allergy & Dietary Requirement Frequency",
        subtitle="Occurrences of dietary tokens parsed from allergy traces.",
        icon="🥗",
        lenses=frozenset({LENS_ALL, LENS_DIETARY}),
        render_attr="render_allergy_dietary_frequency",
    ),
    ChartSpec(
        key="repeat_issue_rooms",
        title="Repeat-Issue Rooms (Occurrences ≥ 2)",
        subtitle="Ranked rooms with 2 or more traces logged (excluding allocation text), highlighting recurring complaint tags.",
        icon="⚠️",
        lenses=frozenset({LENS_ALL, LENS_ROOM_STAY}),
        render_attr="render_repeat_issue_rooms",
    ),
    ChartSpec(
        key="block_floor_density",
        title="Resort Spatial Complaint Density (Block vs. Floor)",
        subtitle="2D heatmap matrix of complaint concentration across accommodation blocks and floors.",
        icon="🗺️",
        lenses=frozenset({LENS_ALL, LENS_ROOM_STAY}),
        render_attr="render_block_floor_density",
    ),
    ChartSpec(
        key="trace_subcategory_breakdown",
        title="Trace Sub-Category Breakdown",
        subtitle="Deep-dive operational classification of generic Trace items (Room Follow-up, Feedback, Maintenance, Complaints, Front Desk).",
        icon="🔍",
        lenses=frozenset({LENS_ALL, LENS_GR_TRACES}),
        render_attr="render_trace_subcategory_breakdown",
    ),
    ChartSpec(
        key="trace_room_change_correlation",
        title="Trace & Room Change Correlation",
        subtitle="Four-metric diagnostic comparing rooms with prior traces, zero prior, offer volume, and approved moves.",
        icon="🔗",
        lenses=frozenset({LENS_ALL, LENS_ROOM_STAY, LENS_GR_TRACES}),
        render_attr="render_trace_room_change_correlation",
    ),
    ChartSpec(
        key="occupancy_normalized_issue_density",
        title="Occupancy-Normalized Issue Density",
        subtitle="Spatial defect rate per block normalized against active room counts.",
        icon="⚖️",
        lenses=frozenset({LENS_ALL, LENS_ROOM_STAY}),
        render_attr="render_occupancy_normalized_issue_density",
    ),
    ChartSpec(
        key="profile_friction_index",
        title="Profile Friction Index",
        subtitle="Ratio of trace generation rates segmented by guest classification (First-time vs. Repeaters vs. VIPs).",
        icon="👥",
        lenses=frozenset({LENS_ALL, LENS_GR_TRACES}),
        render_attr="render_profile_friction_index",
    ),
]

_REGISTRY_MAP: Dict[str, ChartSpec] = {spec.key: spec for spec in CHART_REGISTRY}


def get_spec(key: str) -> ChartSpec:
    """Returns ChartSpec for key, raising KeyError if not found."""
    if key not in _REGISTRY_MAP:
        raise KeyError(f"Chart specification not found for key: {key!r}")
    return _REGISTRY_MAP[key]
