"""
Room Change Detector & Resolution Analytics Engine
==================================================
Calculates repeat-issue rooms, cross-references Room Change Requests (RCR)
against historical PMS room moves with date-window verification, and evaluates
trace room-change correlations.
"""

import os
import re
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Set
from collections import defaultdict, Counter

from MODULES.common.paths_config import DATABASE_DIR
from MODULES.trace_keywords import is_room_issue_trace


def _parse_date(d_val: Any) -> Optional[date]:
    """Parses date string or date/datetime object to datetime.date."""
    if not d_val:
        return None
    if isinstance(d_val, datetime):
        return d_val.date()
    if isinstance(d_val, date):
        return d_val
    d_str = str(d_val).strip()
    if not d_str:
        return None
    try:
        return date.fromisoformat(d_str[:10])
    except Exception:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(d_str, fmt).date()
        except Exception:
            pass
    return None


def _is_move_fallback_match(trace: Dict[str, Any], move: Dict[str, Any]) -> bool:
    """
    Fallback matching when booking_id does not match:
    Requires room-number match AND date overlap:
      - The trace's arrival/departure window overlaps the move record's arrival/departure, OR
      - The move's date falls within [trace.arrival, trace.departure].
    If the move record's arrival and departure are both empty strings, it must not be used
    as a fallback match — treat as unverifiable, do not match on room number alone.
    """
    rm = str(trace.get("room_number", "")).strip()
    m_old = str(move.get("old_room", "")).strip()
    if not rm or not m_old or rm != m_old:
        return False

    m_arr_raw = str(move.get("arrival", "") or "").strip()
    m_dep_raw = str(move.get("departure", "") or "").strip()
    if not m_arr_raw and not m_dep_raw:
        return False

    t_arr = _parse_date(trace.get("arrival"))
    t_dep = _parse_date(trace.get("departure"))
    m_arr = _parse_date(m_arr_raw)
    m_dep = _parse_date(m_dep_raw)
    m_date = _parse_date(move.get("date"))

    # Condition 1: move's date falls within [trace.arrival, trace.departure]
    if m_date:
        if t_arr and t_dep and (t_arr <= m_date <= t_dep):
            return True
        if t_arr and not t_dep and m_date >= t_arr:
            return True
        if not t_arr and t_dep and m_date <= t_dep:
            return True

    # Condition 2: trace's arrival/departure window overlaps move record's arrival/departure
    if t_arr and t_dep and m_arr and m_dep:
        if max(t_arr, m_arr) <= min(t_dep, m_dep):
            return True
    elif t_arr and m_dep and not t_dep and not m_arr:
        if t_arr <= m_dep:
            return True
    elif t_dep and m_arr and not t_arr and not m_dep:
        if t_dep >= m_arr:
            return True
    elif (t_arr or t_dep) and (m_arr or m_dep):
        s1 = t_arr or t_dep
        e1 = t_dep or t_arr
        s2 = m_arr or m_dep
        e2 = m_dep or m_arr
        if max(s1, s2) <= min(e1, e2):
            return True

    return False


def compute_repeat_issue_rooms(traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculates repeat-issue rooms strictly isolated to physical room defects.
    Explicitly excludes non-asset entries (dietary/allergies, late checkouts, courtesy).
    """
    # Step 1: Strictly isolate physical defect records using single source of truth; exclude allocation text
    defect_traces = [
        t for t in traces
        if is_room_issue_trace(t)
        and "allocation" not in str(t.get("category", "")).lower()
        and "allocation" not in str(t.get("notes", "")).lower()
    ]

    # Step 2: Aggregate by room number
    room_defects: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in defect_traces:
        rm = str(t.get("room_number", "")).strip()
        if rm and rm.isdigit():
            room_defects[rm].append(t)

    # Step 3: Retain only repeat issues (count >= 2)
    repeat_rooms = []
    for rm, r_traces in room_defects.items():
        if len(r_traces) >= 2:
            tag_counts: Counter = Counter()
            for tr in r_traces:
                for tag in tr.get("tags", []):
                    if tag not in ["unclassified", "trace"]:
                        tag_counts[tag.replace("_", " ").title()] += 1

            # Determine guest pattern: same_guest vs different_guests vs unknown
            guest_names = [str(tr.get("guest_name", "") or "").strip() for tr in r_traces]
            if any(not g for g in guest_names):
                guest_pattern = "unknown"
            else:
                unique_guests = {g.lower() for g in guest_names}
                if len(unique_guests) == 1:
                    guest_pattern = "same_guest"
                else:
                    guest_pattern = "different_guests"

            repeat_rooms.append({
                "room_number": rm,
                "total_traces": len(r_traces),
                "top_tags": [t for t, _ in tag_counts.most_common(2)],
                "defect_history": [{"date": tr.get("arrival"), "notes": tr.get("notes")} for tr in r_traces],
                "latest_guest": r_traces[-1].get("guest_name", ""),
                "guest_pattern": guest_pattern
            })
    return sorted(repeat_rooms, key=lambda x: x["total_traces"], reverse=True)


def compute_rcr_analytics(traces: List[Dict[str, Any]], room_moves_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes Room Change Request conversion, resolution velocity, and verified defects
    cross-referenced with room_moves.json.
    """
    from MODULES.trace_analytics import extract_rcr_tags, compute_rcr_resolution_status

    target_path = room_moves_path or os.path.join(DATABASE_DIR, "ROOM MOVES", "room_moves.json")
    room_moves: List[Dict[str, Any]] = []
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, list):
                    room_moves = d
                elif isinstance(d, dict) and "moves" in d:
                    room_moves = d["moves"]
        except Exception:
            pass

    executed_booking_ids = {str(m.get("booking_id", "")).strip() for m in room_moves if m.get("booking_id")}

    rcr_traces = [
        t for t in traces
        if "room change" in str(t.get("category", "")).lower()
        or t.get("category") == "Room Change Request"
        or t.get("is_room_defect")
    ]

    total_rcr = len(rcr_traces)
    verified_defects = 0
    moves_executed = 0
    moves_declined = 0
    pending_in_house = 0
    reason_freq: Counter = Counter()
    resolution_counts: Counter = Counter()

    # Defect #3 fix: Removed bare "stay" from decline_terms
    decline_terms = ["declined", "withdrawn", "refused", "cancelled", "canceled", "rejected", "decided to stay"]

    for t in rcr_traces:
        notes_low = str(t.get("notes", "")).lower()
        tags = t.get("tags", [])
        if not tags:
            tags = extract_rcr_tags(t.get("notes", ""))

        has_verified_tag = any(tg not in ["unclassified", "trace"] for tg in tags)
        if has_verified_tag:
            verified_defects += 1

        for tg in tags:
            reason_freq[tg.replace("_", " ").title()] += 1

        st = t.get("resolution_status")
        if not st:
            st = compute_rcr_resolution_status(t.get("notes", ""))
            t["resolution_status"] = st
        resolution_counts[st] += 1

        b_id = str(t.get("booking_id", "")).strip()

        # Defect #2 fix: Primary match on booking_id, fallback on room-number + date overlap
        is_executed = bool(b_id and b_id in executed_booking_ids)
        if not is_executed:
            is_executed = any(_is_move_fallback_match(t, m) for m in room_moves)

        if is_executed:
            moves_executed += 1
        elif (
            any(dt in notes_low for dt in decline_terms)
            or str(t.get("status", "")).lower() in ["declined", "canceled", "cancelled"]
            or st == "Decided to Stay"
        ):
            moves_declined += 1
        else:
            pending_in_house += 1

    resolution_rate = (moves_executed / total_rcr * 100.0) if total_rcr > 0 else 0.0

    res_moved = resolution_counts.get("Resolved / Moved", 0)
    res_att = resolution_counts.get("Attempted / No Answer", 0)
    res_stay = resolution_counts.get("Decided to Stay", 0)
    res_pend = resolution_counts.get("Pending / Unresolved", 0)
    res_rate_explicit = (res_moved / total_rcr * 100.0) if total_rcr > 0 else 0.0

    return {
        "total_move_requests": total_rcr,
        "total_rcr_logged": total_rcr,
        "verified_defects": verified_defects,
        "moves_executed": moves_executed,
        "moves_declined": moves_declined,
        "pending_in_house": pending_in_house,
        "resolution_rate": round(resolution_rate, 2),
        "resolution_rate_pct": round(resolution_rate, 2),
        "reason_frequency": dict(reason_freq.most_common()),
        "resolution_breakdown": {
            "Resolved / Moved": res_moved,
            "Attempted / No Answer": res_att,
            "Decided to Stay": res_stay,
            "Pending / Unresolved": res_pend,
            "resolution_rate_pct": round(res_rate_explicit, 1)
        }
    }


def compute_trace_room_change_correlation(
    traces: List[Dict[str, Any]],
    room_moves_path: Optional[str] = None,
    in_house_manifest: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Four-metric diagnostic visual measuring:
      (1) Rooms with traces logged prior to a room change request
      (2) Rooms requesting a change with zero prior traces
      (3) Total promotional offer volume assigned to both groups
      (4) Count of formally approved room changes
    """
    room_traces: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in traces:
        rm = str(t.get("room_number", "")).strip()
        if rm:
            room_traces[rm].append(t)

    target_path = room_moves_path or os.path.join(DATABASE_DIR, "ROOM MOVES", "room_moves.json")
    approved_moves_count = 0
    approved_rooms: Set[str] = set()
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                moves = d if isinstance(d, list) else d.get("moves", [])
                approved_moves_count = len(moves)
                for m in moves:
                    old_r = str(m.get("old_room", "")).strip()
                    if old_r:
                        approved_rooms.add(old_r)
        except Exception:
            pass

    rcr_rooms: Set[str] = set()
    for rm, t_list in room_traces.items():
        for t in t_list:
            cat_low = str(t.get("category", "")).lower()
            if "room change" in cat_low or t.get("category") == "Room Change Request":
                rcr_rooms.add(rm)
                break
    rcr_rooms.update(approved_rooms)

    rooms_with_prior = set()
    rooms_zero_prior = set()

    for rm in rcr_rooms:
        t_list = room_traces.get(rm, [])
        rcr_items = [t for t in t_list if "room change" in str(t.get("category", "")).lower() or t.get("category") == "Room Change Request"]
        non_rcr_items = [t for t in t_list if t not in rcr_items]
        if len(non_rcr_items) > 0:
            rooms_with_prior.add(rm)
        else:
            rooms_zero_prior.add(rm)

    offers_prior = 0
    offers_zero = 0

    for rm, t_list in room_traces.items():
        offer_count = sum(
            1 for t in t_list
            if "offer" in str(t.get("category", "")).lower()
            or "offer" in str(t.get("notes", "")).lower()
            or "cake" in str(t.get("notes", "")).lower()
            or "wine" in str(t.get("notes", "")).lower()
        )
        if rm in rooms_with_prior:
            offers_prior += offer_count
        elif rm in rooms_zero_prior:
            offers_zero += offer_count

    if approved_moves_count == 0:
        for t in traces:
            if t.get("resolution_status") == "Resolved / Moved":
                approved_moves_count += 1

    num_prior = len(rooms_with_prior)
    num_zero = len(rooms_zero_prior)
    total_rcr_rooms = num_prior + num_zero
    prior_trace_rate = round((num_prior / total_rcr_rooms) * 100.0, 1) if total_rcr_rooms > 0 else 0.0

    return {
        "rooms_with_prior_traces": num_prior,
        "rooms_zero_prior_traces": num_zero,
        "offers_assigned_prior_group": offers_prior,
        "offers_assigned_zero_group": offers_zero,
        "total_offers_assigned": offers_prior + offers_zero,
        "formally_approved_room_changes": approved_moves_count,
        "prior_trace_rate": prior_trace_rate
    }
