"""
Path constants for the cake_memo module.
"""

import os
import sys

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

from MODULES.common.paths_config import resolve_template_path, OUTPUT_DIR

CAKE_MEMO_TEMPLATE_PATH = resolve_template_path("cake_memo") or os.path.abspath(
    os.path.join(BASE_DIR, "TEMPLATES", "CAKE MEMO TEMPLATE", "CAKE MEMO.docx")
)
DEFAULT_CAKE_MEMOS_DIR = os.path.join(OUTPUT_DIR, "CAKE_MEMOS")

os.makedirs(DEFAULT_CAKE_MEMOS_DIR, exist_ok=True)
