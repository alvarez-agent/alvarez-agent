"""Resolve ALVAREZ_HOME for standalone skill scripts.

Skill scripts may run outside the Alvarez process (e.g. system Python,
nix env, CI) where ``alvarez_constants`` is not importable.  This module
provides the same ``get_alvarez_home()`` and ``display_alvarez_home()``
contracts as ``alvarez_constants`` without requiring it on ``sys.path``.

When ``alvarez_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``alvarez_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``ALVAREZ_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from alvarez_constants import display_alvarez_home as display_alvarez_home
    from alvarez_constants import get_alvarez_home as get_alvarez_home
except (ModuleNotFoundError, ImportError):

    def get_alvarez_home() -> Path:
        """Return the Alvarez home directory (default: ~/.alvarez).

        Mirrors ``alvarez_constants.get_alvarez_home()``."""
        val = os.environ.get("ALVAREZ_HOME", "").strip()
        return Path(val) if val else Path.home() / ".alvarez"

    def display_alvarez_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``alvarez_constants.display_alvarez_home()``."""
        home = get_alvarez_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
