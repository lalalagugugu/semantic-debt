"""Mechanical comparison of the two independent required-columns annotations.

T05b (Claude Code) and Codex each marked, per reference, which output columns a
question asks for (decisions/2026-10-18-reference-columns-asked-only.md). This
script only compares them; it does not judge which side is right. Output is
question ids, column numbers and counts only (no question text), for the repo:

    uv run python scripts/compare_required_columns.py \\
        --t05b "$SEMDEBT_DATA_DIR/handoff-claude/T05b-required-columns.v4.json" \\
        --codex "$SEMDEBT_DATA_DIR/handoff-codex/required-columns.json" > reports/required-columns-compare.md

Disagreement types come from the role T05b gave the disputed column (``non_required``).
A Codex note starting with 「边界」 is its boundary mark; T05b has no boundary field.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path

ROLE_TYPE = {
    "rank_key": "一方把排序依据列（含名次列）标成必答",
    "filter_value": "一方把筛选依据列标成必答",
    "alt_identifier": "标识列选名还是选键",
    "alt_measure": "百分比与金额是否同为必答（T05b 标 alt_measure）",
    "not_asked": "一方把 T05b 判为「题目没问的量」的列标成必答",
    "placeholder_name": "占位名称列是否必答",
}
NO_ROLE = "T05b 必答、Codex 非必答（T05b 无角色）"


def order(ref: str) -> tuple[int, str]:
    return int(ref[1:].split("-")[0]), ref


def compare(t05b: dict, codex: dict) -> list[dict]:
    ann = {r["ref"].split("/")[-1].removesuffix(".csv"): r for r in t05b["references"] if "required_columns" in r}
    if set(ann) != set(codex):
        raise SystemExit(f"reference sets differ: only T05b {sorted(set(ann) - set(codex))}, "
                         f"only Codex {sorted(set(codex) - set(ann))}")
    missing_t05b = t05b.get("missing_asked_columns") or {}
    rows = []
    for ref in sorted(ann, key=order):
        a, b = ann[ref], codex[ref]
        ca, cb = set(a["required_columns"]), set(b["required"])
        roles = {n["position"]: n["role"] for n in a["non_required"]}
        types = []
        for col in sorted(ca ^ cb):
            t = ROLE_TYPE.get(roles.get(col), NO_ROLE)
            if t == NO_ROLE and a["columns"][col].split(".")[-1].endswith("Key"):
                t = ROLE_TYPE["alt_identifier"]
            if t not in types:
                types.append(t)
        rows.append({"ref": ref, "t05b": sorted(ca), "codex": sorted(cb), "agree": ca == cb, "types": types,
                     "missing_agree": (missing_t05b.get(a["question_id"]) or None) == (b["missing_asked"] or None),
                     "codex_boundary": b["note"].startswith("边界")})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--t05b", required=True)
    ap.add_argument("--codex", required=True)
    args = ap.parse_args()
    raw = {k: Path(getattr(args, k)).read_bytes() for k in ("t05b", "codex")}
    t05b, codex = json.loads(raw["t05b"]), json.loads(raw["codex"])
    rows = compare(t05b, codex)
    dis = [r for r in rows if not r["agree"]]
    boundary = [r for r in rows if r["codex_boundary"]]
    n_refs = len(t05b["references"])
    out = [
        "# 必答列标注比对摘要（T05b vs Codex）", "",
        f"- T05b：`handoff-claude/{Path(args.t05b).name}`，sha256 `{hashlib.sha256(raw['t05b']).hexdigest()[:12]}`，"
        f"题库 `{t05b.get('eval_commit', '?')[:7]}`",
        f"- Codex：`handoff-codex/{Path(args.codex).name}`，sha256 `{hashlib.sha256(raw['codex']).hexdigest()[:12]}`",
        "- 两份都基于题库 main `455e96f`（#18 合并后；T05b 记的 `56ade6c` 与之同树）",
        "- 只做机械比对，不评判谁对；只含题号、列号和计数。带题面、表头和前 3 行的版本在 "
        "`$SEMDEBT_DATA_DIR/handoff-compare/required-columns-compare.md`（不入库）",
        f"- 复现：`uv run python scripts/compare_required_columns.py --t05b … --codex …`", "",
        "## 计数", "",
        "| 项 | 数 |", "|---|---:|",
        f"| 参考 | {n_refs} |",
        f"| judge（两边都不标） | {n_refs - len(rows)} |",
        f"| 标注（两边集合相同） | {len(rows)} |",
        f"| required 一致 | {len(rows) - len(dis)} |",
        f"| required 分歧 | {len(dis)} |",
        f"| missing_asked 一致 | {sum(r['missing_agree'] for r in rows)}（两边都没有缺列） |", "",
        "## 分歧类型", "",
        "| 类型 | 份数 | 参考 |", "|---|---:|---|",
    ]
    by_type = collections.OrderedDict()
    for r in dis:
        for t in r["types"]:
            by_type.setdefault(t, []).append(r["ref"])
    out += [f"| {t} | {len(v)} | {'、'.join(v)} |" for t, v in by_type.items()]
    out += ["", "## 分歧逐份（列号从 0 开始）", "",
            "| 参考 | T05b 必答 | Codex 必答 | 分歧列 | Codex 边界 |", "|---|---|---|---|---|"]
    for r in dis:
        diff = sorted(set(r["t05b"]) ^ set(r["codex"]))
        out.append(f"| {r['ref']} | {r['t05b']} | {r['codex']} | {diff} | {'是' if r['codex_boundary'] else '否'} |")
    agree_b = [r["ref"] for r in boundary if r["agree"]]
    dis_b = [r["ref"] for r in boundary if not r["agree"]]
    out += ["", "## 边界标记", "",
            f"- Codex 标「边界」：{len(boundary)} 份；T05b 没有边界标记字段（v4 只有备注），**两边都标边界：0 份**",
            f"- Codex 边界且分歧：{len(dis_b)} 份（{'、'.join(dis_b)}）",
            f"- Codex 边界但一致：{len(agree_b)} 份（{'、'.join(agree_b)}）——请用户过一眼",
            f"- 分歧但 Codex 未标边界：{sum(1 for r in dis if not r['codex_boundary'])} 份"
            f"（{'、'.join(r['ref'] for r in dis if not r['codex_boundary'])}）"]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
