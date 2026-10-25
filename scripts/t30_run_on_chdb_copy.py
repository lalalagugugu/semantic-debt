"""T30 runner: use only this card's private chDB copy (hard rule 9)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import executors  # noqa: E402

COPY = Path(os.environ["SEMDEBT_DATA_DIR"]) / "chdb-t30"
executors.default_chdb_path = lambda: str(COPY)

if __name__ == "__main__":
    from harness import run_direct

    if "--dry-run" not in sys.argv and not COPY.is_dir():
        sys.exit("Missing private chDB copy: SEMDEBT_DATA_DIR/chdb-t30")
    sys.exit(run_direct.main(sys.argv[1:]))
