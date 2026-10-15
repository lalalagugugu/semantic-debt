"""逐列探查：不同取值数、空值率、低基数字符串列的全部取值、数值与日期范围。

写 L1 之前的唯一信息来源之一（另一个是建表语句和约定清单）。
产物：semantic/profiling/out/columns.md、semantic/profiling/out/columns.json

重跑：
    uv run python semantic/profiling/profile_columns.py

硬规则 9：同一个 chDB 数据目录不能被两个进程同时打开。本脚本用完即关。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from data.ddl import tables as ddl_tables  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"

# 低基数的判定线：不同取值少于这个数就把取值全列出来（任务卡写的是 50）
LOW_CARD_MAX = 50


def chdb_dir() -> Path:
    root = os.environ.get("SEMDEBT_DATA_DIR")
    if not root:
        sys.exit("SEMDEBT_DATA_DIR 未设置（见 AGENTS.md「环境」）")
    d = Path(root).expanduser() / "chdb"
    if not d.is_dir():
        sys.exit(f"chDB 数据目录不存在：{d}（先跑 data/load.py）")
    return d


def q(sess, sql: str) -> list[list[str]]:
    """跑一条查询，返回每行的字段列表（字段一律转成字符串）。

    用 JSONCompact 而不是 TabSeparated：TSV 会把取值里的 `\'`、`\t`、`\\` 转义掉，
    而本脚本的产物要原样进 source.yaml 的取值清单，带着转义符就是错的
    （实际踩过：DimEmployee.DepartmentName 的脏取值 `'Human Resources Contral`
    在 TSV 里成了 `\\'Human Resources Contral`）。
    """
    raw = sess.query(sql, "JSONCompact").bytes().decode("utf-8")
    if not raw.strip():
        return []
    rows = json.loads(raw).get("data", [])
    return [["" if v is None else str(v) for v in row] for row in rows]


def base_type(ch_type: str) -> str:
    t = ch_type
    while t.startswith("Nullable(") or t.startswith("LowCardinality("):
        t = t[t.index("(") + 1 : -1]
    return t


def is_numeric(t: str) -> bool:
    b = base_type(t)
    return b.startswith(("Int", "UInt", "Float", "Decimal"))


def is_date(t: str) -> bool:
    return base_type(t).startswith("Date")


def is_string(t: str) -> bool:
    return base_type(t) == "String"


def profile() -> dict:
    from chdb import session

    tables = {t.name: dict(t.columns) for t in ddl_tables()}
    sess = session.Session(str(chdb_dir()))
    result: dict[str, dict] = {}
    try:
        version = q(sess, "SELECT version()")[0][0]
        for tname, cols in tables.items():
            full = f"retail.{tname}"
            n = int(q(sess, f"SELECT count() FROM {full}")[0][0])
            print(f"{tname}: {n} 行", flush=True)

            # 一次查询拿到每列的 distinct 数与非空数，避免 25 张表 × N 列各来一趟
            parts = []
            for c, t in cols.items():
                parts.append(f"uniqExact(`{c}`) AS `d__{c}`")
                parts.append(f"countIf(`{c}` IS NOT NULL) AS `nn__{c}`")
            row = q(sess, f"SELECT {', '.join(parts)} FROM {full}")[0] if n else []

            tinfo: dict = {"rows": n, "columns": {}}
            for i, (c, t) in enumerate(cols.items()):
                distinct = int(row[2 * i]) if row else 0
                nonnull = int(row[2 * i + 1]) if row else 0
                cinfo = {
                    "type": t,
                    "distinct": distinct,
                    "nulls": n - nonnull,
                    "null_rate": round((n - nonnull) / n, 6) if n else None,
                }
                tinfo["columns"][c] = cinfo
            result[tname] = tinfo

            # 第二趟：低基数字符串列列全部取值；数值/日期列取范围
            for c, t in cols.items():
                cinfo = result[tname]["columns"][c]
                d = cinfo["distinct"]
                if is_string(t) and 0 < d <= LOW_CARD_MAX:
                    rows = q(
                        sess,
                        f"SELECT `{c}`, count() FROM {full} WHERE `{c}` IS NOT NULL "
                        f"GROUP BY `{c}` ORDER BY count() DESC, `{c}`",
                    )
                    cinfo["values"] = [{"value": r[0], "rows": int(r[1])} for r in rows]
                elif is_string(t) and d > LOW_CARD_MAX:
                    rows = q(
                        sess,
                        f"SELECT `{c}` FROM {full} WHERE `{c}` IS NOT NULL "
                        f"GROUP BY `{c}` ORDER BY count() DESC LIMIT 5",
                    )
                    cinfo["top_values"] = [r[0] for r in rows]
                elif is_numeric(t) or is_date(t):
                    r = q(sess, f"SELECT min(`{c}`), max(`{c}`) FROM {full}")[0]
                    cinfo["min"], cinfo["max"] = r[0], r[1]
                    if is_numeric(t) and d <= LOW_CARD_MAX and d > 0:
                        rows = q(
                            sess,
                            f"SELECT `{c}`, count() FROM {full} WHERE `{c}` IS NOT NULL "
                            f"GROUP BY `{c}` ORDER BY `{c}`",
                        )
                        cinfo["values"] = [{"value": r2[0], "rows": int(r2[1])} for r2 in rows]
    finally:
        sess.close()
    return {"chdb_version": version, "low_card_max": LOW_CARD_MAX, "tables": result}


def render_md(data: dict) -> str:
    lines = [
        "# 逐列探查结果",
        "",
        "由 `semantic/profiling/profile_columns.py` 生成，不要手改。",
        "",
        f"- chDB / ClickHouse 版本：`{data['chdb_version']}`",
        f"- 低基数判定线：不同取值 ≤ {data['low_card_max']} 就列出全部取值",
        "- 「空值率」只统计 SQL NULL；空字符串算一个取值，在取值表里看得到",
        "",
    ]
    for tname, t in data["tables"].items():
        lines += [f"## {tname}", "", f"行数：{t['rows']:,}", "", "| 列 | 类型 | 不同取值 | 空值率 | 范围 / 取值 |", "|---|---|---:|---:|---|"]
        for c, ci in t["columns"].items():
            rate = "—" if ci["null_rate"] is None else f"{ci['null_rate']:.2%}"
            if "values" in ci:
                shown = "；".join(f"`{v['value']}`({v['rows']:,})" for v in ci["values"])
                extra = shown
            elif "top_values" in ci:
                extra = "最常见：" + "、".join(f"`{v}`" for v in ci["top_values"])
            elif "min" in ci:
                extra = f"{ci['min']} ~ {ci['max']}"
            else:
                extra = "—"
            lines.append(f"| `{c}` | {ci['type']} | {ci['distinct']:,} | {rate} | {extra} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = profile()
    (OUT / "columns.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "columns.md").write_text(render_md(data), encoding="utf-8")
    print(f"写出 {OUT / 'columns.md'}")


if __name__ == "__main__":
    main()
