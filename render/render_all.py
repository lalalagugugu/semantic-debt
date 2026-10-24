"""Rebuild every T10 product from semantic/ in one go (no database needed).

    uv run python render/render_all.py

Runs, in order: contexts (with the L0 / R leak checks) → Cube model → PBIP →
equivalence check → DAX contexts against the PBIP (check_pbip) → context sizes.
Stops at the first failure.

Two steps need the chDB data directory and are run on their own:
    uv run python render/snapshot_schema.py   # after a dwd / ads / l0 view changes
    uv run python render/verify_cube.py       # Cube measure SQL against chDB
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render import check_equivalence, check_pbip, context, context_sizes, cube, tmdl  # noqa: E402


def main() -> None:
    context.main([])
    cube.main()
    tmdl.main()
    check_equivalence.main()
    if check_pbip.main():
        sys.exit(1)
    context_sizes.main()


if __name__ == "__main__":
    main()
