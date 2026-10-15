"""建 L1.5W 的明细宽表视图，并核对行数。

把 `semantic/widetables.sql` 里的语句在 chDB 上执行（视图建在独立库 `dwd`，`retail` 不动），
然后核对每个视图的行数与对应事实表一致——「当前库存」除外，它按约定 11 做了行筛选。

用法：
    uv run python render/build_widetables.py              # 建视图 + 核对
    uv run python render/build_widetables.py --check-only # 只核对，不重建

产物（不入库）：reports/validation/widetables.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SQL_FILE = REPO / "semantic" / "widetables.sql"
REPORT = REPO / "reports" / "validation" / "widetables.md"

# 视图 → 对应事实表。行数必须相等（关联和行级派生不该改变行数）。
ROW_COUNT_EQUAL: dict[str, str] = {
    "dwd.wide_online_sales": "retail.FactOnlineSales",
    "dwd.wide_all_channel_sales": "retail.FactSales",
    "dwd.wide_sales_quota": "retail.FactSalesQuota",
    "dwd.wide_strategy_plan": "retail.FactStrategyPlan",
}

# 做了行筛选、行数本就不等于事实表的视图：单独说明并单独核对。
ROW_COUNT_FILTERED: dict[str, str] = {
    "dwd.wide_current_inventory": (
        "retail.FactInventory 按约定 11 取每个门店 × 产品最近一次快照，"
        "所以行数等于门店 × 产品组合数，而不是事实表行数"
    ),
}


def chdb_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        sys.exit("SEMDEBT_DATA_DIR 未设置（见 AGENTS.md「环境」）")
    d = Path(root).expanduser() / "chdb"
    if not d.is_dir():
        sys.exit(f"chDB 数据目录不存在：{d}（先跑 data/load.py）")
    return d


def statements(sql: str) -> list[str]:
    """按分号切语句，去掉注释行和空语句。"""
    no_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def scalar(sess, sql: str) -> str:
    return sess.query(sql, "TabSeparated").bytes().decode("utf-8").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true", help="不重建视图，只核对行数")
    args = ap.parse_args()

    from chdb import session

    sql = SQL_FILE.read_text(encoding="utf-8")
    sess = session.Session(str(chdb_dir()))
    rows: list[tuple[str, str, int, int | None, str]] = []
    failures: list[str] = []
    try:
        if not args.check_only:
            for stmt in statements(sql):
                name = re.search(r"(?:CREATE OR REPLACE VIEW|CREATE DATABASE IF NOT EXISTS)\s+(\S+)", stmt)
                print(f"执行：{name.group(1) if name else stmt[:40]}", flush=True)
                sess.query(stmt)

        for view, fact in ROW_COUNT_EQUAL.items():
            v = int(scalar(sess, f"SELECT count() FROM {view}"))
            f = int(scalar(sess, f"SELECT count() FROM {fact}"))
            ok = v == f
            rows.append((view, fact, v, f, "一致" if ok else "**不一致**"))
            print(f"{view}: {v:,} 行；{fact}: {f:,} 行 → {'一致' if ok else '不一致'}", flush=True)
            if not ok:
                failures.append(f"{view} 有 {v} 行，{fact} 有 {f} 行")

        for view, why in ROW_COUNT_FILTERED.items():
            v = int(scalar(sess, f"SELECT count() FROM {view}"))
            expected = int(
                scalar(sess, "SELECT uniqExact((StoreKey, ProductKey)) FROM retail.FactInventory")
            )
            ok = v == expected
            rows.append((view, why, v, expected, "按说明一致" if ok else "**不一致**"))
            print(f"{view}: {v:,} 行；门店 × 产品组合数 {expected:,} → {'一致' if ok else '不一致'}", flush=True)
            if not ok:
                failures.append(f"{view} 有 {v} 行，门店 × 产品组合数是 {expected}")

        # 宽表不改金额：销售额与毛利的合计必须与事实表一致（定点数求和，与行序无关）
        money: list[tuple[str, str, str, str]] = []
        for view, fact, col_v, col_f in [
            ("dwd.wide_online_sales", "retail.FactOnlineSales", "销售金额", "SalesAmount"),
            ("dwd.wide_all_channel_sales", "retail.FactSales", "销售金额", "SalesAmount"),
            ("dwd.wide_all_channel_sales", "retail.FactSales", "总成本", "TotalCost"),
            ("dwd.wide_sales_quota", "retail.FactSalesQuota", "目标销售额", "SalesAmountQuota"),
            ("dwd.wide_strategy_plan", "retail.FactStrategyPlan", "计划金额", "Amount"),
        ]:
            a = scalar(sess, f"SELECT sum(toDecimal128(`{col_v}`, 6)) FROM {view}")
            b = scalar(sess, f"SELECT sum(toDecimal128(`{col_f}`, 6)) FROM {fact}")
            money.append((f"{view}.{col_v}", f"{fact}.{col_f}", a, "一致" if a == b else f"**不一致**（事实表 {b}）"))
            if a != b:
                failures.append(f"{view}.{col_v} 合计 {a} ≠ {fact}.{col_f} 合计 {b}")
    finally:
        sess.close()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 明细宽表（L1.5W）校验报告",
        "",
        "由 `render/build_widetables.py` 生成，不要手改。重跑：",
        "",
        "```sh",
        "uv run python render/build_widetables.py",
        "```",
        "",
        "视图定义在 `semantic/widetables.sql`，建在独立库 `dwd`，`retail` 库不动。",
        "",
        "## 行数核对",
        "",
        "关联和行级派生不应改变行数，所以除「当前库存」外每个视图的行数都必须等于对应事实表。",
        "",
        "| 视图 | 对应事实表 / 说明 | 视图行数 | 应为 | 判定 |",
        "|---|---|---:|---:|---|",
    ]
    for view, fact, v, f, verdict in rows:
        lines.append(f"| `{view}` | {fact if fact.startswith('retail.') and ' ' not in fact else fact} | {v:,} | {f:,} | {verdict} |")
    lines += [
        "",
        "## 金额合计核对",
        "",
        "宽表只关联、不改金额，所以金额列的合计必须与事实表逐位相同（`sum(toDecimal128(列, 6))`，与行序无关）。",
        "",
        "| 视图列 | 事实表列 | 合计 | 判定 |",
        "|---|---|---:|---|",
    ]
    for a, b, total, verdict in money:
        lines.append(f"| `{a}` | `{b}` | {total} | {verdict} |")
    lines += ["", "## 结论", "", "全部通过。" if not failures else "**未通过：**\n" + "\n".join(f"- {x}" for x in failures), ""]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"写出 {REPORT}")

    if failures:
        sys.exit("校验未通过：\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
