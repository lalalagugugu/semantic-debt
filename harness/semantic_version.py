"""The semantic layer a run reads must be the content of a frozen tag (``--semantic-tag``).

Same idea as ``verify_eval_tag`` for the question bank, with one difference: the
semantic layer lives in this repository, whose HEAD moves on after the tag (harness
work), so the check is on content, not on HEAD:

1. ``semantic/`` and ``render/`` in the working tree equal the tag's tree: no
   committed, staged or unstaged difference, no untracked file (hard rule 2: the
   ``semantic-v*`` tags freeze both the sources and the renderer);
2. every ``build/contexts/<cell>.yaml`` a run will send is what the renderer makes
   from those sources now, i.e. the build is not stale.

Anything else raises ``SemanticVersionError`` and the run does not start.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path

SEMANTIC_PATHS = ("semantic", "render")


class SemanticVersionError(RuntimeError):
    """The semantic layer the harness would read is not the content of the frozen tag."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def render_context(name: str) -> str:
    """The text ``render/context.py`` writes to ``build/contexts/<name>.yaml``."""
    from render.context import dump_yaml, render_cell

    ctx = render_cell(name)
    if ctx is None:
        raise SemanticVersionError(f"{name}: no tuning file, the cell cannot be rendered")
    return dump_yaml(ctx)


def verify_semantic_tag(tag: str, contexts: Iterable[str], *, root: Path, contexts_dir: Path,
                        render: Callable[[str], str] = render_context) -> str:
    """Full commit of ``tag`` if ``semantic/``, ``render/`` and the given built contexts are its content.

    ``contexts`` are context file names under ``contexts_dir`` (e.g. ``SQL-L1.yaml``).
    """
    tagged = _git(root, "rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}")
    if tagged.returncode != 0:
        raise SemanticVersionError(f"{root}: tag {tag!r} not found (git fetch --tags)")
    want = tagged.stdout.strip()
    changed = _git(root, "diff", "--name-only", want, "--", *SEMANTIC_PATHS)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "--", *SEMANTIC_PATHS)
    if changed.returncode != 0 or untracked.returncode != 0:
        raise SemanticVersionError(f"{root}: git failed: {(changed.stderr or untracked.stderr).strip()}")
    files = sorted(set(changed.stdout.split()) | set(untracked.stdout.split()))
    if files:
        shown = ", ".join(files[:5]) + (" …" if len(files) > 5 else "")
        raise SemanticVersionError(f"{root}: {', '.join(SEMANTIC_PATHS)} differ from {tag} ({want[:7]}): {shown}")
    for name in sorted(set(contexts)):
        path = contexts_dir / name
        if not path.exists():
            raise SemanticVersionError(f"{path} missing: run `uv run python render/render_all.py`")
        if path.read_text(encoding="utf-8") != render(Path(name).stem):
            raise SemanticVersionError(f"{path} is stale (not rendered from {tag}): "
                                       "run `uv run python render/render_all.py`")
    return want
