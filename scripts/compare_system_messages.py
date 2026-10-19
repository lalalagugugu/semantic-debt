"""Which cells' system messages change against a git ref (default origin/main).

Builds every cell's full system message twice from the working tree's rendered contexts
(``build/contexts/``, external contexts from the bank): once with the syntax notes as they
are at ``--ref``, once with the working tree's notes. Agent cells (-E) wrap the direct
message; JSON-L2 and the DAX cells are built from their contexts directly. Prints one line
per cell with both hashes. Run ``render/render_all.py`` first and compare ``build/contexts``
separately (they do not read the syntax notes).

    SEMDEBT_EVAL_DIR=<eval-v1.2 worktree> uv run python scripts/compare_system_messages.py [--ref origin/main]
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import agent_prompt as A  # noqa: E402
from harness import prompt as P  # noqa: E402
from harness import run_direct as R  # noqa: E402
from harness import cells as C  # noqa: E402
from harness.cells import AGENT_CELLS, CELLS, CONTEXTS, REPO  # noqa: E402

LADDER_CELLS = getattr(C, "LADDER_CELLS", {})          # C13 (PR #141), when present
syntax_path = getattr(C, "syntax_path", lambda name: C.SYNTAX / name)

EXTRA = (("JSON-L2", "cube_json.md"), ("DAX-L0", "dax.md"), ("DAX-L1", "dax.md"), ("DAX-L2", "dax.md"))


def at_ref(ref: str, path: Path) -> str | None:
    out = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{path.relative_to(REPO)}"],
                         capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else None


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/main")
    args = ap.parse_args()
    rows = []
    for name, cell in [*CELLS.items(), *LADDER_CELLS.items(), *AGENT_CELLS.items()]:
        try:
            context = R.context_text(cell)
        except FileNotFoundError:
            rows.append((name, cell.syntax, "-", "-", "not built"))
            continue
        lang = "yaml" if cell.context.startswith("build:") else None
        path = syntax_path(cell.syntax)
        old_note = at_ref(args.ref, path)
        new = P.system_message(context, path.read_text(encoding="utf-8"), lang)
        old = P.system_message(context, old_note, lang) if old_note is not None else None
        if name in AGENT_CELLS:
            new, old = A.agent_system_message(new), (A.agent_system_message(old) if old is not None else None)
        rows.append((name, cell.syntax, digest(old) if old else "(new)", digest(new),
                     "same" if old == new else "CHANGED"))
    for name, note in EXTRA:
        context = (CONTEXTS / f"{name}.yaml").read_text(encoding="utf-8")
        path = syntax_path(note)
        old_note = at_ref(args.ref, path)
        new = P.system_message(context, path.read_text(encoding="utf-8"), "yaml")
        old = P.system_message(context, old_note, "yaml") if old_note is not None else None
        rows.append((name, note, digest(old) if old else "(new)", digest(new), "same" if old == new else "CHANGED"))
    for row in rows:
        print(" | ".join(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
