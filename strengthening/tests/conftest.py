"""Pytest bootstrap for the `strengthening` test suite.

Puts the repository root on ``sys.path`` so that tests can import the
implicit namespace package ``strengthening.*`` regardless of how pytest was
invoked (from the worktree root or from inside ``strengthening/tests``).

This file deliberately contains no network access, no API clients and no
credential lookups of any kind.
"""

from __future__ import annotations

import sys
from pathlib import Path

# strengthening/tests/conftest.py -> strengthening/tests -> strengthening -> <root>
_REPO_ROOT = Path(__file__).resolve().parents[2]

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
