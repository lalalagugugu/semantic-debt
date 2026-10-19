"""Python sandbox for the planning agent (T21): run model code with no network and no files.

Each execution is a fresh container of the image built from
``harness/pysandbox_image/Dockerfile``, started by its pinned image ID:

    docker run --rm -i --name semdebt-py-<hex> --network none --read-only --tmpfs /tmp:... \\
        --memory 2g --memory-swap 2g --cpus 2 --pids-limit 256 --cap-drop ALL \\
        --security-opt no-new-privileges --user 10001:10001 sha256:<IMAGE_ID>

That argv is the only docker command the harness ever runs: ``docker_command`` builds it
and ``check_command`` refuses anything that is not exactly that shape (no volume or mount,
no network other than ``none``, no privilege, no device, no published port, image =
the pinned ID). Tests pin both. Data reaches the code only through stdin, as the rows
``run_sql`` returned, so the code cannot see the question bank, ``runs/``, runs-raw,
Parquet or the chDB directory (hard rule 1; T21 card, isolation).

The 30-second limit is enforced inside the image (``timeout -s KILL 30``), so no
``docker kill`` is needed; the host waits a little longer and gives up on the client
process only as a backstop.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field

# Image ID of `docker build -t semdebt-pysandbox:1 harness/pysandbox_image` (recorded in the T21 card).
IMAGE_ID = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
TIMEOUT_S = 30              # baked into the image's ENTRYPOINT; here only to classify and to wait
HOST_GRACE_S = 15           # container start-up and the transfer of the input rows
TMPFS = "/tmp:rw,noexec,nosuid,size=256m"

_IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")
_NAME = re.compile(r"^semdebt-py-[0-9a-f]{12}$")


@dataclass(frozen=True)
class PyResult:
    """One execution: ``ok`` with captured stdout (and ``answer`` when asked for), or an error."""

    ok: bool
    stdout: str = ""
    error: str | None = None
    error_class: str | None = None      # python_error / timeout / resource_limit / sandbox_error
    answer: dict | None = None          # {"columns": [...], "rows": [...]}
    elapsed_s: float = 0.0

    def summary(self) -> dict:
        out = {"status": "ok" if self.ok else "error", "elapsed_s": round(self.elapsed_s, 3),
               "stdout_chars": len(self.stdout)}
        if not self.ok:
            out["error_class"] = self.error_class
            out["error"] = (self.error or "")[:500]
        if self.answer is not None:
            out["answer_rows"] = len(self.answer.get("rows") or [])
            out["answer_columns"] = self.answer.get("columns")
        return out


def docker_command(name: str, image: str = IMAGE_ID) -> list[str]:
    return ["docker", "run", "--rm", "-i", "--name", name,
            "--network", "none", "--read-only", "--tmpfs", TMPFS,
            "--memory", "2g", "--memory-swap", "2g", "--cpus", "2", "--pids-limit", "256",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "10001:10001",
            image]


def check_command(cmd: list[str], image: str = IMAGE_ID) -> None:
    """Refuse every docker invocation except the one fixed sandbox argv."""
    if len(cmd) < 6 or not _NAME.match(cmd[5]):
        raise ValueError("not the sandbox command")
    if not _IMAGE.match(image) or cmd != docker_command(cmd[5], image):
        raise ValueError("only the fixed `docker run --rm -i --network none --read-only <pinned image>` is allowed")


@dataclass
class DockerSandbox:
    image: str = IMAGE_ID
    name: str = "docker"
    launched: list[list[str]] = field(default_factory=list)

    def run(self, code: str, tables: dict[int, dict], want_answer: bool = False) -> PyResult:
        """Run ``code`` with ``results`` = {n: DataFrame of tables[n]}; ``tables[n]`` =
        {"columns": [...], "rows": [...]} as the executor returned them."""
        cmd = docker_command(f"semdebt-py-{uuid.uuid4().hex[:12]}", self.image)
        check_command(cmd, self.image)
        self.launched.append(cmd)
        payload = json.dumps({"code": code, "tables": {str(k): v for k, v in tables.items()},
                              "want_answer": want_answer}, ensure_ascii=False, default=str).encode()
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, input=payload, capture_output=True, timeout=TIMEOUT_S + HOST_GRACE_S)
        except subprocess.TimeoutExpired:
            return PyResult(False, error=f"Python 执行超过 {TIMEOUT_S} 秒，已终止。", error_class="timeout",
                            elapsed_s=time.monotonic() - start)
        return parse_output(proc.returncode, proc.stdout, proc.stderr, time.monotonic() - start)


def parse_output(returncode: int, stdout: bytes, stderr: bytes, elapsed: float) -> PyResult:
    try:
        out = json.loads(stdout.decode("utf-8", "replace"))
    except ValueError:
        detail = stderr.decode("utf-8", "replace").strip()[-500:]
        if returncode == 137 and elapsed >= TIMEOUT_S:
            return PyResult(False, error=f"Python 执行超过 {TIMEOUT_S} 秒，已终止。", error_class="timeout",
                            elapsed_s=elapsed, stdout=detail)
        if returncode == 137:
            return PyResult(False, error="Python 进程内存超限，已终止。", error_class="resource_limit",
                            elapsed_s=elapsed, stdout=detail)
        return PyResult(False, error=f"Python 沙箱执行失败（退出码 {returncode}）。", error_class="sandbox_error",
                        elapsed_s=elapsed, stdout=detail)
    if not out.get("ok"):
        return PyResult(False, stdout=out.get("stdout") or "", error=out.get("error") or "Python error",
                        error_class="python_error", elapsed_s=elapsed)
    return PyResult(True, stdout=out.get("stdout") or "", answer=out.get("answer"), elapsed_s=elapsed)
