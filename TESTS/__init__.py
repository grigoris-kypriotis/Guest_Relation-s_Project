"""
TESTS Package: Automated test suite for Guest Relation Workspace.
"""

import sys
import os

# Ensure the workspace root is always in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
