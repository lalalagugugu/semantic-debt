"""Isolation probe for the Python sandbox (T21 card, acceptance 1).

Prints the JSON request that, run through the sandbox, tries to read the question bank,
``runs/``, runs-raw, a Parquet file and the chDB directory at their host paths, list the
filesystem root and the mounts, and reach the network (DNS and a TCP connection to the
DeepSeek API and to a public IP). Every probe must fail; the code prints one line per probe.

    uv run python harness/pysandbox_image/isolation_probe.py > "$TMPDIR/probe.json"
    docker run --rm -i --network none --read-only ... semdebt-pysandbox:1 < "$TMPDIR/probe.json"

The host paths come from the environment (SEMDEBT_EVAL_DIR, SEMDEBT_DATA_DIR) and the repo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PROBE = r'''
import os, socket
def probe(label, fn):
    try:
        r = fn()
        print(f"REACHED  {label}: {str(r)[:120]!r}")
    except Exception as e:
        print(f"blocked  {label}: {type(e).__name__}: {str(e)[:120]}")
for label, path in PATHS:
    probe("read " + label, lambda p=path: (os.listdir(p) if os.path.isdir(p) else open(p, "rb").read(64)))
probe("stat " + "root listing", lambda: sorted(os.listdir("/")))
probe("mounts (host binds)", lambda: [l for l in open("/proc/mounts") if "/Users" in l or "/host" in l] or (_ for _ in ()).throw(LookupError("no host bind mounts")))
probe("dns api.deepseek.com", lambda: socket.getaddrinfo("api.deepseek.com", 443))
probe("tcp 1.1.1.1:443", lambda: socket.create_connection(("1.1.1.1", 443), timeout=3))
probe("tcp 116.205.40.120:443", lambda: socket.create_connection(("116.205.40.120", 443), timeout=3))
probe("write /work", lambda: open("/probe.txt", "w").write("x"))
'''


def request() -> dict:
    eval_dir = Path(os.environ["SEMDEBT_EVAL_DIR"]).expanduser()
    data_dir = Path(os.environ["SEMDEBT_DATA_DIR"]).expanduser()
    parquet = next(iter(sorted((data_dir / "parquet").glob("*.parquet"))), data_dir / "parquet" / "x.parquet")
    paths = [("question bank README", str(eval_dir / "README.md")),
             ("question bank dir", str(eval_dir)),
             ("runs/", str(REPO / "runs")),
             ("runs-raw", str(data_dir / "runs-raw")),
             ("parquet file", str(parquet)),
             ("chdb dir", str(data_dir / "chdb"))]
    code = f"PATHS = {paths!r}\n" + PROBE
    return {"code": code, "tables": {}, "want_answer": False}


if __name__ == "__main__":
    print(json.dumps(request(), ensure_ascii=False))
