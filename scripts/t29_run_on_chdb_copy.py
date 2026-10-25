"""Run the frozen T29 harness against its independent chDB data copy."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from harness import executors  # noqa: E402

COPY = Path(os.environ["SEMDEBT_DATA_DIR"]) / "chdb-t29"
executors.default_chdb_path = lambda: str(COPY)

if __name__ == "__main__":
    from harness import run_direct

    if "--dry-run" not in sys.argv and not COPY.is_dir():
        sys.exit("Missing private chDB copy: SEMDEBT_DATA_DIR/chdb-t29")
    sys.exit(run_direct.main(sys.argv[1:]))
