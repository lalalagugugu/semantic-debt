"""Run harness.run_direct against a private chDB copy (hard rule 9: another session may have $SEMDEBT_DATA_DIR/chdb open).

Only the executor's data directory changes; harness code is untouched.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from harness import executors  # noqa: E402

COPY = str(Path(os.environ["SEMDEBT_DATA_DIR"]) / "chdb-t14")
executors.default_chdb_path = lambda: COPY

# The scorer's child processes use spawn, which re-imports this file as __mp_main__:
# without this guard every child would start another run.
if __name__ == "__main__":
    from harness import run_direct

    sys.exit(run_direct.main(sys.argv[1:]))
