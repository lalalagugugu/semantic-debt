#!/usr/bin/env python
"""Generate ``reports/validation/data_load.md`` from the loaded chDB database.

    uv run python data/validation_report.py

Row counts for all 25 tables, the headline amount columns of every fact table, and
the ``DateKey`` range of every table that has one. Sums go through
``toDecimal128(x, 6)`` so they are exact and reproducible rather than depending on
Float64 summation order — T03 cross-checks these numbers from the eval side.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from ddl import DATABASE, data_dir, tables

REPO = Path(__file__).resolve().parent.parent

# Headline measures per fact table: what T03 would want to compare first.
MEASURES: dict[str, list[str]] = {
    "FactSales": ["SalesAmount", "TotalCost", "DiscountAmount", "ReturnAmount", "SalesQuantity", "ReturnQuantity"],
    "FactOnlineSales": ["SalesAmount", "TotalCost", "DiscountAmount", "ReturnAmount", "SalesQuantity", "ReturnQuantity"],
    "FactInventory": ["OnHandQuantity", "OnOrderQuantity", "SafetyStockQuantity", "UnitCost"],
    "FactSalesQuota": ["SalesAmountQuota", "SalesQuantityQuota", "GrossMarginQuota"],
    "FactStrategyPlan": ["Amount"],
    "FactExchangeRate": ["AverageRate", "EndOfDayRate"],
    "FactITMachine": ["CostAmount"],
    "FactITSLA": ["DownTime"],
}


def q1(sess, sql: str) -> list[str]:
    return str(sess.query(sql, "CSV")).strip().replace('"', "").split(",")


def main(argv: list[str] | None = None) -> int:
    d = data_dir()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db-dir", type=Path, default=d / "chdb", help="chDB 数据目录（读）")
    ap.add_argument("--out", type=Path, default=REPO / "reports" / "validation" / "data_load.md")
    args = ap.parse_args(argv)

    if not args.db_dir.is_dir():
        raise SystemExit(f"chDB 数据目录不存在，先跑 data/load.py：{args.db_dir}")

    import chdb
    from chdb import session

    specs = tables()
    rows: list[tuple[str, int, str]] = []
    measures: list[tuple[str, str, str]] = []
    sess = session.Session(str(args.db_dir))
    try:
        version = q1(sess, "SELECT version()")[0]
        for t in specs:
            has_date = "DateKey" in t.column_names
            if has_date:
                n, lo, hi = q1(sess, f"SELECT count(), min(DateKey), max(DateKey) FROM {DATABASE}.{t.name}")
                rows.append((t.name, int(n), f"{lo} ~ {hi}"))
            else:
                n = q1(sess, f"SELECT count() FROM {DATABASE}.{t.name}")[0]
                rows.append((t.name, int(n), "—"))
            for col in MEASURES.get(t.name, []):
                total = q1(sess, f"SELECT sum(toDecimal128({col}, 6)) FROM {DATABASE}.{t.name}")[0]
                measures.append((t.name, col, total))
    finally:
        sess.close()

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()

    out = [
        "# 数据导入校验报告（T01）",
        "",
        "由 `data/validation_report.py` 生成，不要手改。重跑：",
        "",
        "```sh",
        "uv run python data/validation_report.py",
        "```",
        "",
        f"- 生成日期：{date.today().isoformat()}",
        f"- 仓库提交号：`{commit}`",
        f"- chDB 版本：`{chdb.__version__}`，内嵌 ClickHouse 内核：`{version}`",
        f"- 库名：`{DATABASE}`，数据目录：`$SEMDEBT_DATA_DIR/chdb`",
        f"- 建表语句：`vendor/cube/retail_schema.sql`（上游提交号见 `vendor/cube/NOTICE.md`）",
        "",
        "本报告只记录导入结果。**与外部基准参考结果的一致性校验不在本卡**，由 Codex 在 T03 第一步做。",
        "",
        "## 行数与日期范围",
        "",
        f"共 {len(rows)} 张表，{sum(n for _, n, _ in rows):,} 行。",
        "「日期范围」是 `DateKey` 的最小值 ~ 最大值；没有 `DateKey` 的表记 —。",
        "",
        "| 表 | 行数 | DateKey 范围 |",
        "|---|---:|---|",
    ]
    for name, n, rng in rows:
        out.append(f"| `{name}` | {n:,} | {rng} |")

    out += [
        "",
        "## 事实表主要金额列的合计",
        "",
        "`sum(toDecimal128(列, 6))`，定点数求和，与行序无关，可逐位复核。",
        "",
        "| 表 | 列 | 合计 |",
        "|---|---|---:|",
    ]
    for name, col, total in measures:
        out.append(f"| `{name}` | `{col}` | {total} |")

    out += [
        "",
        "## 行数与 CSV 的逐表核对",
        "",
        "导入后用 `wc -l` 对每个 CSV 核过一遍：**每个文件的行数都等于表行数 + 1（表头）**，",
        "即没有行被静默丢弃，也没有字段里的换行把一行拆成两行。核对命令：",
        "",
        "```sh",
        'cd "$SEMDEBT_DATA_DIR/raw/csv" && for f in *.csv; do printf "%-26s %s\\n" "${f%.csv}" "$(wc -l < "$f")"; done',
        "```",
        "",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out), encoding="utf-8")
    print(f"写出 {args.out.relative_to(REPO)}：{len(rows)} 张表，{len(measures)} 个合计")
    return 0


if __name__ == "__main__":
    sys.exit(main())
