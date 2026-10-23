"""Build the zip that goes to the Windows machine for T17 (Mac side).

    uv run python scripts/t17_windows_bundle.py
    → $SEMDEBT_DATA_DIR/t17-windows/t17-bundle-<commit>.zip

Contents (unzip on Windows into %SEMDEBT_DATA_DIR%\\t17-bundle\\, see windows/README.md):

    parquet/*.parquet   the 25 tables, as exported by T01 (what the probe's reference numbers come from)
    pbip/retail-L{0,1,2}/  the three Power BI projects, rendered with DataDir left as a placeholder,
                        so the files and their hashes do not depend on this machine's paths;
                        ``dax_probe.py prepare`` makes working copies with the Windows path filled in
    MANIFEST.sha256     sha256 of every file above (``<hash>  <path>``)
    BUNDLE.txt          the commit it was built from

The code is not in the zip: the Windows machine checks out the same commit with git.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    data = Path(os.environ["SEMDEBT_DATA_DIR"]).expanduser()
    parquet = data / "parquet"
    dirty = git("status", "--porcelain", "--", "render", "semantic", "harness", "windows")
    if dirty:
        print(f"render/、semantic/、harness/、windows/ 有未提交的改动，先提交再打包：\n{dirty}")
        return 1
    commit = git("rev-parse", "HEAD")

    from render import tmdl

    os.environ.pop("SEMDEBT_DATA_DIR")          # DataDir = placeholder: hashes independent of this machine
    try:
        stage = Path(tempfile.mkdtemp(prefix="t17-bundle-"))
        for tier in ("L0", "L1", "L2"):
            tmdl.Project(tier).write(stage / "pbip")
    finally:
        os.environ["SEMDEBT_DATA_DIR"] = str(data)

    files = [(p, f"parquet/{p.name}") for p in sorted(parquet.glob("*.parquet"))]
    files += [(p, p.relative_to(stage).as_posix()) for p in sorted((stage / "pbip").rglob("*")) if p.is_file()]
    if len([f for f in files if f[1].startswith("parquet/")]) != 25:
        print(f"{parquet} 里应有 25 个 parquet 文件")
        return 1
    manifest = "".join(f"{sha256(p)}  {rel}\n" for p, rel in files)
    note = (f"T17 Windows bundle\ncommit {commit}\nbuilt {datetime.now().isoformat(timespec='seconds')}\n"
            "unzip into %SEMDEBT_DATA_DIR%\\t17-bundle\\ ; then follow windows/README.md\n")

    out_dir = data / "t17-windows"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"t17-bundle-{commit[:7]}.zip"
    with zipfile.ZipFile(out, "w") as z:
        for p, rel in files:
            z.write(p, rel, compress_type=zipfile.ZIP_STORED if rel.endswith(".parquet") else zipfile.ZIP_DEFLATED)
        z.writestr("MANIFEST.sha256", manifest, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("BUNDLE.txt", note, compress_type=zipfile.ZIP_DEFLATED)
    print(f"写入 {out}（{out.stat().st_size / 1e6:.0f} MB，{len(files)} 个文件，commit {commit[:7]}）")
    print(f"sha256 {sha256(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
