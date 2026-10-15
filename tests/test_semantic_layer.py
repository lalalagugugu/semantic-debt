"""语义层的静态校验（T08）。

真正的检查逻辑在 `semantic/schema/validate.py` 里，这里只是把它接进 pytest，
让 `uv run pytest` 能覆盖到。只跑不连数据库的那部分（`--no-data`）：
连 chDB 的第 7 项要几十秒，而且 chDB 的同一个数据目录不能被两个进程同时打开
（硬规则 9），放进测试会和别的脚本抢。第 7 项由

    uv run python semantic/schema/validate.py

单独跑。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "semantic" / "schema" / "validate.py"
SOURCE = REPO / "semantic" / "source.yaml"


def test_validator_exists() -> None:
    assert VALIDATOR.is_file(), "缺 semantic/schema/validate.py（T08 的验收项要求有校验脚本）"


@pytest.mark.skipif(not SOURCE.is_file(), reason="semantic/source.yaml 还没写")
def test_semantic_layer_validates() -> None:
    r = subprocess.run(
        [sys.executable, str(VALIDATOR), "--no-data"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert r.returncode == 0, f"语义层校验未通过：\n{r.stdout}\n{r.stderr}"


@pytest.mark.skipif(not SOURCE.is_file(), reason="semantic/source.yaml 还没写")
def test_frozen_artifacts_present() -> None:
    """G1 要冻结的东西（tag `semantic-v1`）都在仓库里。

    L0 映射（l0_map.yaml）和汇总层由 T09 / T08 第二步补，这里只检查本卡第一步的产物。
    """
    for rel in (
        "semantic/conventions.md",
        "semantic/source.yaml",
        "semantic/widetables.sql",
        "semantic/metrics.yaml",
        "semantic/summary/requirements.md",
        "semantic/profiling/README.md",
    ):
        assert (REPO / rel).is_file(), f"缺 {rel}"
