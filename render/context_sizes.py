"""Token counts of every rendered context → reports/validation/context_sizes.md.

The tested model's tokenizer is not available offline (and the blind cards may not
fetch it), so the counts use DeepSeek's published rule of thumb: one Chinese
character ≈ 0.6 token, one other character ≈ 0.3 token. They are estimates for
comparing cells and budgeting; T11/T12 replace them with the usage the API reports.

    uv run python render/context_sizes.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from render.common import REPO  # noqa: E402
from render.context import CELLS, OUT_DIR  # noqa: E402

REPORT = REPO / "reports" / "validation" / "context_sizes.md"
SYNTAX = REPO / "render" / "syntax"
SYNTAX_OF = {"sql": "clickhouse_sql.md", "cube_sql": "cube_sql.md", "cube_json": "cube_json.md", "dax": "dax.md"}
_CJK = re.compile(r"[　-〿㐀-鿿＀-￯]")


def estimate_tokens(text: str) -> int:
    cjk = len(_CJK.findall(text))
    return round(cjk * 0.6 + (len(text) - cjk) * 0.3)


def main() -> None:
    lines = [
        "# 各单元语义上下文的 token 数（T10）", "",
        "由 `uv run python render/context_sizes.py` 生成，读的是 `build/contexts/` 下的渲染结果。",
        "",
        "**估算口径**：被测模型的分词器拿不到（盲模式也不得去取），按 DeepSeek 官方给的经验比例估算：",
        "中文字符 ≈ 0.6 token、其他字符 ≈ 0.3 token。用来比较单元之间的相对大小和做预算；",
        "T11 / T12 用 API 返回的实际用量替换。", "",
        "| 单元 | 字符数 | 其中中文 | 估算 token | 语法说明（估算 token） | 合计（估算） |",
        "|---|---|---|---|---|---|",
    ]
    totals = {}
    for cell, (stack, _tier, _tuning) in CELLS.items():
        path = OUT_DIR / f"{cell}.yaml"
        if not path.exists():
            lines.append(f"| {cell} | — | — | — | — | 尚无调优文件，未渲染 |")
            continue
        text = path.read_text(encoding="utf-8")
        syntax = (SYNTAX / SYNTAX_OF[stack]).read_text(encoding="utf-8")
        t, s = estimate_tokens(text), estimate_tokens(syntax)
        totals[cell] = t + s
        lines.append(f"| {cell} | {len(text):,} | {len(_CJK.findall(text)):,} | {t:,} | {s:,} | {t + s:,} |")

    lines += ["", "## 语法说明", "", "| 文件 | 去空白字符数 | 估算 token |", "|---|---|---|"]
    counts = {}
    for f in sorted(SYNTAX_OF.values()):
        text = (SYNTAX / f).read_text(encoding="utf-8")
        counts[f] = len(re.sub(r"\s", "", text))
        lines.append(f"| `render/syntax/{f}` | {counts[f]:,} | {estimate_tokens(text):,} |")
    spread = max(counts.values()) / min(counts.values()) - 1
    lines += ["", f"最长与最短相差 {spread:.1%}（任务卡要求不超过 10%）。", ""]

    l1 = totals.get("SQL-L1")
    if l1:
        lines += [
            "## 与费用估算的对照", "",
            f"设计文档的费用按「直答每次输入约 1 万 token」估算；本表里 SQL-L1 的上下文加语法说明约 {l1:,} token，",
            f"是那个假设的 {l1 / 10000:.1f} 倍（还没算系统提示和问题本身）。上下文对同一单元的所有题相同、放在最前面，",
            "能命中缓存，但缓存命中的输入也计费。这一点交给 T11 / T12 用实测用量重估预算，本卡不改上下文去迁就它。", "",
        ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"写入 {REPORT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
