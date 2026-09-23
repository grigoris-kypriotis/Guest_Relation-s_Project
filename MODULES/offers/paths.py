"""
Path constants and task logging for the offers module.
"""

import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def _load_env_file():
    """Load environment variables from .env file if present."""
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


_load_env_file()

from MODULES.common.paths_config import resolve_template_path, DATABASE_DIR, OUTPUT_DIR, TODAYS_LIST_DIR

ARRIVALS_FOLDER = os.path.abspath(DATABASE_DIR)
FINAL_FOLDER = os.path.abspath(os.path.join(OUTPUT_DIR, "OFFERS"))
TODAY_LIST_FOLDER = os.path.abspath(TODAYS_LIST_DIR)

TEMPLATE_PATH = resolve_template_path("offer_list") or os.path.abspath(os.path.join(BASE_DIR, "TEMPLATES", "OFFER LIST TEMPLATE", "OFFER LIST TEMPLATE.docx"))

CHECK_MEMO_TEMPLATE_PATH = resolve_template_path("check_memo") or os.path.abspath(os.path.join(BASE_DIR, "TEMPLATES", "CHECK MEMO TEMPLATE", "CHECK MEMO.docx"))
CAKE_TEMPLATE_PATH = CHECK_MEMO_TEMPLATE_PATH
CAKE_MEMO_TEMPLATE_PATH = CHECK_MEMO_TEMPLATE_PATH

os.makedirs(FINAL_FOLDER, exist_ok=True)
os.makedirs(TODAY_LIST_FOLDER, exist_ok=True)


def log_task(task_text, status):
    """Log a task with timestamp to today's task log file."""
    os.makedirs(TODAY_LIST_FOLDER, exist_ok=True)
    now = datetime.now()
    filepath = os.path.abspath(os.path.join(TODAY_LIST_FOLDER, f"Tasks_{now.strftime('%Y-%m-%d')}.txt"))
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"[{now.strftime('%H:%M:%S')}] {status}: {task_text}\n")
