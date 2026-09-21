"""
Trace Keywords Taxonomy & Classification Engine
================================================
Deterministic keyword taxonomies, regex patterns, and deterministic
classification filters for trace analytics.
"""

import re
from typing import Dict, List, Tuple, Any, Optional

# Tier 1: Physical Room Defects & Change Requests (Asset-focused)
PHYSICAL_DEFECT_TAGS: Dict[str, List[str]] = {
    "Plumbing/Water": [
        r"\bno\s+hot\s+water\b", r"\bhot\s+water\b", r"\bleak\b", r"\bleaking\b",
        r"\bpressure\b", r"\bclogged\b", r"\btoilet\b", r"\bshower\b", r"\bdrain\b"
    ],
    "HVAC/Climate": [
        r"\ba/?c\b", r"\bair\s+condition\b", r"\bcold\b", r"\bheating\b", r"\bfan\b"
    ],
    "Noise/Disturbance": [
        r"\bnoise\b", r"\bnoisy\b", r"\bloud\b", r"\bmusic\b", r"\btraffic\b",
        r"\bgenerator\b", r"\bbar\s+noise\b"
    ],
    "Odor/Hygiene": [
        r"\bsmell\b", r"\bodor\b", r"\bstink\b", r"\bhumidity\b", r"\bdamp\b",
        r"\bmold\b", r"\bsewer\b", r"\bdirty\b"
    ],
    "Room Allocation/View": [
        r"\bview\b", r"\bsea\s+view\b", r"\bgarden\b", r"\bground\s+floor\b",
        r"\bhigh\s+floor\b", r"\bstairs\b", r"\bwalking\s+distance\b", r"\belevator\b"
    ],
    "Room Merge/Adjoining": [
        r"\bmerge\b", r"\badjoining\b", r"\bconnecting\b", r"\bnext\s+door\b"
    ],
    "Furniture/Fixtures": [
        r"\bbed\b", r"\bdoor\b", r"\bwindow\b", r"\bbalcony\b", r"\block\b"
    ],
    "Pest/Insect": [
        r"\bcockroach(?:es)?\b", r"\bmosquito(?:es)?\b", r"\binsects?\b",
        r"\bants?\b", r"\bwasps?\b", r"\bbugs?\b", r"\bspiders?\b"
    ],
    "Electronics/Safe": [
        r"\bsafe\s*box\b",
        r"\bsafe\s+(?:(?:is|isn't|isnt|not|does|doesn't|doesnt|won't|wont|was|wasn't|wasnt)\s+\w*\s*)?(?:work|working|open|close|lock|unlock|jammed|broken|beep|beeping)\b",
        r"\bkey\s+(?:for|from)\s+(?:the\s+)?safe\b",
        r"\bfridge\b", r"\bminibar\b", r"\bmini[- ]bar\b",
        r"\brefrigerator\b", r"\bsockets?\b", r"\bpower\s+outage\b", r"\bblackout\b",
        r"\bhair[- ]?dryer(?:s)?\b", r"\blight\s+bulb(?:s)?\b"
    ],
    "Furniture/Bedding": [
        r"\bmattress(?:es)?\b", r"\bbedding\b", r"\blinen\b", r"\bblankets?\b",
        r"\bpillows?\b", r"\bcurtains?\b", r"\bblinds?\b", r"\btopper\b", r"\bduvet\b"
    ],
    "Cosmetic/Surface": [
        r"\brust(?:y)?\b", r"\bpaint(?:ing)?\b", r"\bcracked?\b", r"\bscratched?\b",
        r"\bpeeling\b", r"\bcosmetic\b"
    ]
}

# Tier 2: Clear Operational / Courtesy Traces (Guest-focused)
CLEAR_SERVICE_CATEGORIES: List[str] = [
    "Allergies", "Allergies/dietary requirments", "Late Check Out",
    "Offer", "Birthday", "Decoration", "Flowers", "Special Requests",
    "Feedback", "Allocation Comments", "Booking", "Restaurants"
]

EXCLUDED_TERMS: List[str] = [
    "allergy", "gluten", "lactose", "nuts", "vegan", "late check out", "birthday", "cake"
]

TAG_DICTIONARY: Dict[str, List[str]] = {
    "Noise": ["noise", "noisy", "loud", "music", "traffic", "bar", "sound", "tv", "quiet"],
    "Smell": ["smell", "odor", "stink", "drain", "humidity", "stinks", "smells", "damp"],
    "View Mismatch": ["view", "garden", "sea view", "pool view", "side sea view", "trees"],
    "Water/Plumbing": ["hot water", "no water", "pressure", "leak", "clogged", "toilet", "shower", "bath", "plumbing"],
    "Accessibility": ["stairs", "elevator", "lift", "wheelchair", "walking", "distance", "disabled", "disable", "handicap", "baby"],
    "Room Merge/Adjoining": ["merge", "adjoining", "connecting", "together", "next door", "merged"],
    "AC / Air Conditioning": ["ac", "air con", "air conditioning", "aircon", "a/c"],
    "Floor Preference": ["high floor", "higher floor", "upper floor", "ground floor", "low floor"],
    "Proximity Request": ["close to", "near the", "next to", "distance from"],
    "Furniture/Fixtures": ["bed", "door", "window", "balcony"],
}

SPECIFIC_TAG_PATTERNS: List[Tuple[str, str]] = [
    (r"\bno\s+hot\s+water\b", "no_hot_water"),
    (r"\bhot\s+water\b", "water_plumbing"),
    (r"\bleak\b|\bpressure\b|\bclogged\b|\btoilet\b|\bshower\b", "water_plumbing"),
    (r"\bnoise\b|\bnoisy\b|\bloud\b|\bmusic\b|\bquiet\b", "noise"),
    (r"\bsmell\b|\bstink\b|\bodor\b|\bdrain\b", "smell"),
    (r"\bsea\s+view\b|\bview\b|\bgarden\b", "view_mismatch"),
    (r"\bwheelchair\b|\bdisabled\b|\bdisable\b|\bstairs\b|\belevator\b|\blift\b", "accessibility"),
    (r"\bmerge\b|\badjoining\b|\bconnecting\b", "room_merge"),
    (r"\ba/?c\b|\bair\s+con(?:ditioning)?\b|\baircon\b", "ac_air_conditioning"),
    (r"\b(?:high|higher|upper|ground|low)\s+floor\b", "floor_preference"),
    (r"\b(?:close\s+to|near\s+the|next\s+to|distance\s+from)\b", "proximity_request"),
    (r"\b(?:bed|door|window|balcony)\b", "furniture_fixtures"),
]

ALLERGY_TOKENS: Dict[str, List[str]] = {
    "Gluten": ["gluten", "celiac", "coeliac", "wheat"],
    "Lactose/Dairy": ["lactose", "dairy", "milk", "cheese", "butter"],
    "Nuts/Peanuts": ["nuts", "nut", "peanut", "peanuts", "walnut", "almond", "hazelnut", "cashew"],
    "Shellfish/Seafood": ["shellfish", "seafood", "shrimp", "prawn", "crab", "lobster", "fish", "salmon", "tuna"],
    "Mushrooms": ["mushroom", "mushrooms", "fungi"],
    "Vegan": ["vegan", "vegetarian", "plant based"],
    "Egg": ["egg", "eggs", "albumen"],
}

PRIMARY_TRACE_CATEGORIES: List[str] = [
    "Room Change Request",
    "Allergies",
    "Late Check Out",
    "Trace",
    "Feedback",
    "Offer",
    "Allocation Comments",
    "Booking",
    "Decoration",
    "Birthday",
    "Special Requests",
    "Restaurants",
    "Flowers",
]

# Single source of truth for Room Issues (Item 1)
ROOM_ISSUE_CATEGORIES: List[str] = [
    "Room Change Request",
    "Trace",
]

EXCLUDED_ROOM_ISSUE_CATEGORIES: List[str] = [
    "Allergies",
    "Allergies/dietary requirments",
    "Offer",
    "Birthday",
    "Decoration",
    "Flowers",
    "Booking",
    "Late Check Out",
    "Allocation Comments",
    "Allocation",
    "Allocation comments",
]

# Sub-classification taxonomy for category == "Trace" (Item 3)
TRACE_SUBCATEGORIES: List[str] = [
    "Room Follow-up",
    "NPS / Feedback Outreach",
    "Maintenance Log",
    "Complaint Log",
    "Reception Interaction",
    "Special Request",
    "Positive Feedback",
    "Other / General",
]

TRACE_SUBCATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Room Follow-up": ["sent note", "new room", "moved"],
    "NPS / Feedback Outreach": ["feedback", "nps", "gr asked", "came to gr", "survey"],
    "Maintenance Log": ["maintenance", "technician", "engineer", "repair", "fix", "maint"],
    "Complaint Log": ["complain", "not happy", "upset", "mad", "angry"],
    "Reception Interaction": ["reception", "came to rec", "front desk"],
    "Special Request": ["water bottle", "extra", "deliver", "bring"],
    "Positive Feedback": ["happy", "great", "excellent", "love", "wonderful", "satisfied"],
}

# 3-Lens Top-Level Filter Categories (Item 4)
LENS_ROOM_STAY = "Room & Stay Requests"
LENS_GR_TRACES = "Guest Relations Traces"
LENS_DIETARY = "Dietary & Medical"
LENS_ALL = "All Analytics"

LENS_CATEGORIES: Dict[str, List[str]] = {
    LENS_ROOM_STAY: ["Room Change Request", "Late Check Out", "Allocation Comments", "Booking"],
    LENS_GR_TRACES: ["Trace", "Feedback", "Offer", "Birthday", "Decoration", "Flowers", "Special Requests", "Restaurants"],
    LENS_DIETARY: ["Allergies", "Allergies/dietary requirments"],
}


def classify_trace_subcategory(notes: str) -> str:
    """Classifies free-text notes for category == 'Trace' into distinct operational work streams."""
    if not notes:
        return "Other / General"
    notes_low = str(notes).lower()
    for subcat, keywords in TRACE_SUBCATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw == "maint":
                if re.search(r"\bmaint\w*\b", notes_low):
                    return subcat
            elif kw == "mad":
                if re.search(r"\bmad\b", notes_low):
                    return subcat
            elif kw in notes_low:
                return subcat
    return "Other / General"


def is_room_issue_trace(trace: Dict[str, Any]) -> bool:
    """
    Deterministic filter identifying whether a trace record represents a physical or operational room issue.
    Single source of truth used by both repeat-issue rooms and the block/floor complaint density heatmap.
    Explicitly excludes non-asset traces (Allergies, Offer, Birthday, Decoration, Flowers, Booking, Late Check Out).
    For 'Trace' entries, only counts if it received an operational maintenance/complaint tag.
    For 'Room Change Request' entries, requires a verified/operational signal rather than unconditional acceptance.
    """
    cat = str(trace.get("category", "")).strip()
    cat_low = cat.lower()
    notes_low = str(trace.get("notes", "")).lower()

    # Explicitly exclude non-asset categories
    if any(ex.lower() in cat_low for ex in EXCLUDED_ROOM_ISSUE_CATEGORIES):
        return False
    if "allocation" in cat_low or "allocation" in notes_low:
        return False
    if any(tok in notes_low for tok in ["gluten", "lactose", "celiac", "coeliac", "peanuts", "nuts", "vegan"]):
        return False

    tags = trace.get("tags", [])
    has_operational_tag = any(
        tg in [
            "smell", "leak", "water_plumbing", "water / plumbing", "ac", "ac_air_conditioning",
            "ac___air_conditioning", "no_hot_water", "noise", "noise_complaint",
            "furniture_fixtures", "view_mismatch", "cleanliness", "hvac", "insects", "key_lock"
        ]
        for tg in tags
    )

    # Defect #1 fix: RCR requires a verified/operational tag or room defect signal
    if cat == "Room Change Request" or "room change" in cat_low:
        has_verified_tag = any(tg not in ["unclassified", "trace"] for tg in tags)
        return bool(has_verified_tag or has_operational_tag or trace.get("is_room_defect"))

    if cat == "Trace" or "trace" in cat_low:
        subcat = trace.get("trace_subcategory") or classify_trace_subcategory(trace.get("notes", ""))
        if subcat in ["Maintenance Log", "Complaint Log"]:
            return True
        if trace.get("is_room_defect"):
            return True
        if has_operational_tag:
            return True
        # Check physical defect regex patterns
        has_defect_tag = any(
            re.search(pat, notes_low)
            for patterns in PHYSICAL_DEFECT_TAGS.values()
            for pat in patterns
        )
        return has_defect_tag

    # If category is Feedback or other, count if it carries a physical defect tag or explicit defect flag
    if has_operational_tag or trace.get("is_room_defect"):
        return True

    # Check primary ROOM_ISSUE_CATEGORIES
    if cat in ROOM_ISSUE_CATEGORIES:
        return True

    return False
