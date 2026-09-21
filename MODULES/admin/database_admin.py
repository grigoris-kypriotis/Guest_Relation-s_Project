"""
Database Administration & Export Engine
=======================================
Provides administrative operations for the Guest Relation Workspace:
  - Database purge and reset (clearing transient records while maintaining schemas).
  - Room block JSON export (aggregating room occupancy by block and floor for PLOT/).
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from MODULES.common.paths_config import (
    BASE_DIR,
    DATABASE_DIR,
    OUTPUT_DIR,
    ROOMS_DIR,
    PLOT_DIR,
    HOTEL_DATASET_PATH,
    MASTER_STATE_PATH,
    STATE_META_PATH,
    CHECKOUTS_JSON,
    ROOM_MOVES_JSON,
    BOOKING_CALLS_TODAY_JSON,
    ARRIVALS_BEACH_PATH,
    save_and_archive_json,
)


def purge_hotel_database() -> Dict[str, Any]:
    """
    Purges transient room and guest records from DATABASE/HOTEL STATE/,
    checkouts, room moves, booking calls, and all auxiliary system JSON files,
    stripping dynamic runtime fields from HotelDataSet.json and resetting
    room block JSON exports.
    """
    purged_count = 0

    # 1. Reset master_state.json
    save_and_archive_json({}, MASTER_STATE_PATH)
    purged_count += 1

    # 2. Reset state_metadata.json
    reset_meta = {
        "last_sync_date": None,
        "last_updated_at": None,
        "total_bookings": 0,
        "last_processed_date": None
    }
    save_and_archive_json(reset_meta, STATE_META_PATH)
    purged_count += 1

    # 3. Reset checkouts history
    try:
        save_and_archive_json({"records": []}, CHECKOUTS_JSON)
        purged_count += 1
    except Exception:
        pass

    # 4. Reset room moves history
    try:
        save_and_archive_json([], ROOM_MOVES_JSON)
        purged_count += 1
    except Exception:
        pass

    # 5. Reset today's booking calls and arrivals
    try:
        if os.path.exists(BOOKING_CALLS_TODAY_JSON):
            save_and_archive_json([], BOOKING_CALLS_TODAY_JSON)
            purged_count += 1
    except Exception:
        pass

    try:
        if os.path.exists(ARRIVALS_BEACH_PATH):
            save_and_archive_json({}, ARRIVALS_BEACH_PATH)
            purged_count += 1
    except Exception:
        pass

    # 6. Target auxiliary JSON files across workspace
    aux_target_files = [
        "guest_manifest.json",
        "cake_memos.json",
        "offer_list.json",
        "reservations.json",
        "allocations.json",
        "stats_cache.json",
        "memos.json",
        "offers.json"
    ]
    search_dirs = [BASE_DIR, DATABASE_DIR, OUTPUT_DIR]
    for s_dir in search_dirs:
        if not os.path.exists(s_dir):
            continue
        for fname in aux_target_files:
            fpath = os.path.join(s_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump([], f, indent=2)
                    purged_count += 1
                except Exception:
                    pass

    # 7. Purge active trace collections and room mapping files in ROOMS/
    try:
        if os.path.exists(ROOMS_DIR):
            for f_name in os.listdir(ROOMS_DIR):
                if f_name.lower().endswith(".json"):
                    try:
                        os.remove(os.path.join(ROOMS_DIR, f_name))
                        purged_count += 1
                    except Exception:
                        pass
    except Exception as e:
        print(f"[purge_hotel_database] Warning resetting ROOMS/ files: {e}")

    # 8. Purge raw trace export files and trace caches in DATABASE/
    try:
        if os.path.exists(DATABASE_DIR):
            for root, _, files in os.walk(DATABASE_DIR):
                for f_name in files:
                    f_lower = f_name.lower()
                    ext = os.path.splitext(f_name)[1].lower()
                    is_raw_trace = (
                        ext in [".xlsx", ".xls", ".csv"]
                        and ("trace" in f_lower or "traces" in f_lower or "trace list" in root.lower())
                    )
                    is_cached_trace = (
                        ext == ".json"
                        and (
                            f_lower in ["trace_cache.json", "trace_analytics.json"]
                            or "trace" in f_lower
                        )
                    )
                    if is_raw_trace or is_cached_trace:
                        f_path = os.path.join(root, f_name)
                        try:
                            os.remove(f_path)
                            purged_count += 1
                        except Exception as err:
                            print(f"[purge_hotel_database] Warning removing trace file {f_name}: {err}")
    except Exception as e:
        print(f"[purge_hotel_database] Warning scanning DATABASE/ for trace files: {e}")

    # 9. Flush dynamic runtime fields in HotelDataSet.json (occupancies and assignments)
    hotel_ds_path = Path(HOTEL_DATASET_PATH)
    if hotel_ds_path.exists():
        try:
            with open(hotel_ds_path, "r", encoding="utf-8") as f:
                records = json.load(f)
            if isinstance(records, list):
                for node in records:
                    if isinstance(node, dict):
                        node.pop("current_occupancy", None)
                        node.pop("assigned_guests", None)
                        node.pop("live_status", None)
                with open(hotel_ds_path, "w", encoding="utf-8") as f:
                    json.dump(records, f, indent=2, ensure_ascii=False)
                purged_count += 1
        except Exception as err:
            print(f"[purge_hotel_database] Warning resetting HotelDataSet.json: {err}")

    # 10. Synchronize / reset PLOT block files
    try:
        export_room_block_json_data()
    except Exception as e:
        print(f"[purge_hotel_database] Warning resetting block files on purge: {e}")

    # 11. Purge in_house*.csv, *παραμένοντες*, and inhouselist.csv
    backup_dir = os.path.join(BASE_DIR, "DATA_BACKUP")
    trash_dir = os.path.join(BASE_DIR, "TRASH")

    def _matches_inhouse_target(filename: str) -> bool:
        fn_lower = filename.lower()
        if fn_lower.endswith(".json"):
            return False
        if fn_lower.startswith("in_house") and fn_lower.endswith(".csv"):
            return True
        if "παραμένοντες" in fn_lower:
            return True
        if fn_lower == "inhouselist.csv":
            return True
        return False

    # A. DATABASE/ (recursive)
    if os.path.exists(DATABASE_DIR):
        for root, _, files in os.walk(DATABASE_DIR):
            for f in files:
                if _matches_inhouse_target(f):
                    try:
                        os.remove(os.path.join(root, f))
                        purged_count += 1
                    except Exception:
                        pass

    # B. BASE_DIR (top-level only; never touches TEMPLATES, BOOKING CALLS, or PLOT)
    if os.path.exists(BASE_DIR):
        for f in os.listdir(BASE_DIR):
            f_path = os.path.join(BASE_DIR, f)
            if os.path.isfile(f_path) and _matches_inhouse_target(f):
                try:
                    os.remove(f_path)
                    purged_count += 1
                except Exception:
                    pass

    # C. DATA_BACKUP/ and TRASH/
    for target_dir in [backup_dir, trash_dir]:
        if os.path.exists(target_dir):
            for root, _, files in os.walk(target_dir):
                for f in files:
                    if _matches_inhouse_target(f):
                        try:
                            os.remove(os.path.join(root, f))
                            purged_count += 1
                        except Exception:
                            pass

    return {"success": True, "purged_count": purged_count}


def export_room_block_json_data(
    plot_dir: Optional[Union[str, Path]] = None,
    hotel_dataset_path: Optional[Union[str, Path]] = None,
    master_state: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Iterates over every room block defined in HotelDataSet.json.
    For each block:
      - Creates a subfolder named after the block (e.g., BLOCK_1100).
      - Calculates live occupancy metrics against active In-House List.
      - Saves <BLOCK_NAME>.json inside the subfolder.
    """
    plot_dir_p = Path(plot_dir or PLOT_DIR)
    dataset_path = Path(hotel_dataset_path or HOTEL_DATASET_PATH)

    if not dataset_path.exists():
        raise FileNotFoundError(f"Hotel dataset not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    if master_state is None:
        if os.path.exists(MASTER_STATE_PATH):
            try:
                with open(MASTER_STATE_PATH, "r", encoding="utf-8") as mf:
                    master_state = json.load(mf)
            except Exception:
                master_state = {}
        else:
            master_state = {}

    occupied_rooms = set()
    if isinstance(master_state, dict):
        for b_data in master_state.values():
            if isinstance(b_data, dict):
                rm = str(b_data.get("Δωμάτιο") or b_data.get("room") or b_data.get("Room") or b_data.get("room_number") or "").strip()
                if rm:
                    occupied_rooms.add(rm)

    def expand_range(rng_str: str) -> List[str]:
        m = re.match(r"^(\d+)-(\d+)$", rng_str.strip())
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            return [str(r) for r in range(start, end + 1)]
        return [rng_str.strip()]

    exported_blocks = []
    os.makedirs(plot_dir_p, exist_ok=True)
    now_iso = datetime.now().isoformat()

    for item in dataset:
        cat = str(item.get("category", ""))
        name = str(item.get("name", ""))

        if "Rooms" not in cat and not name.upper().startswith("BLOCK"):
            continue

        rooms = set()
        rd = item.get("room_details", {})
        floors = rd.get("floors", {})
        for floor_name, r_list in floors.items():
            for r_entry in r_list:
                for r in expand_range(r_entry):
                    rooms.add(r)

        total_rooms = rd.get("total_rooms") or len(rooms)
        if total_rooms <= 0:
            total_rooms = len(rooms) if len(rooms) > 0 else 1

        occupied_count = len(rooms.intersection(occupied_rooms))
        vacant_count = max(0, total_rooms - occupied_count)
        occ_pct = round((occupied_count / total_rooms) * 100, 2) if total_rooms > 0 else 0.0

        payload = json.loads(json.dumps(item))
        payload["occupancy_metrics"] = {
            "total_rooms": int(total_rooms),
            "occupied_rooms": int(occupied_count),
            "vacant_rooms": int(vacant_count),
            "occupancy_percentage": occ_pct,
            "last_updated": now_iso
        }

        block_slug = re.sub(r"[^\w\d]+", "_", name.strip()).strip("_")
        block_folder = plot_dir_p / block_slug
        os.makedirs(block_folder, exist_ok=True)

        json_path = block_folder / f"{block_slug}.json"
        with open(json_path, "w", encoding="utf-8") as out_f:
            json.dump(payload, out_f, indent=4, ensure_ascii=False)

        exported_blocks.append({
            "block": name,
            "slug": block_slug,
            "path": str(json_path),
            "metrics": payload["occupancy_metrics"]
        })

    return {
        "total_exported": len(exported_blocks),
        "blocks": exported_blocks,
        "timestamp": now_iso
    }
