"""Export a tuning packet for the T14 B role, and check it against the question-bank split.

tasks/T14-tuning.md step 1: the packet holds **only tuning-split questions that the first run
got wrong**: for each, the question, the model's queries and assumptions, a summary of what they
returned, and the reference result (what an analyst would have verified). No correct attempt, no
held-out question, no other cell's results. Judge questions are skipped
(decisions/2026-10-23-tuning-instructions.md §1).

"Got wrong" is per attempt, like a user's thumbs-down: a question is in the packet when at least
one of its 3 first-run attempts is not ``correct``, and only those attempts are shown. The
reference SQL is not shown, only the reference result and its interpretation (card: 「正确的参考
结果」). The model's reasoning is never shown.

The packet goes to ``build/tuning-packet/<name>/`` (not committed: it holds question text). The
check writes ``reports/tuning/packet-<name>-check.md`` and ``packet-<name>-manifest.json``
(question ids only), which are committed.

    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python -m harness.tuning_packet
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_direct as R  # noqa: E402
from harness.cells import REPO  # noqa: E402
from harness.questions import eval_dir, question_files, verify_eval_tag  # noqa: E402
from harness.rescore import candidate_of  # noqa: E402
from harness.scorer_v2 import REFUSAL, ExecError  # noqa: E402

PACKET_ROOT = REPO / "build" / "tuning-packet"
REPORT_DIR = REPO / "reports" / "tuning"
REF_ROWS = 20        # first rows of each reference result
ATTEMPT_ROWS = 10    # first rows of each attempt's result
CELL_CHARS = 200     # one value longer than this is cut (the row count is always given)
ERROR_CHARS = 1500

# name → (source run with the final verdicts, the run whose runs-raw it reuses, cell, tuning file)
PACKETS = {
    "sql-l1": ("20261018-T13-sql-direct-01-rescore-01", "20261018-T13-sql-direct-01", "SQL-L1", "SQL-L1"),
}
QID = re.compile(r"\bQ\d+\b")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Inputs


def bank_records(root: Path) -> dict[str, dict]:
    import yaml

    out = {}
    for path in question_files(root):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rec in data["questions"] if isinstance(data, dict) else data:
            out[str(rec["id"])] = rec
    return out


def source_lines(run_id: str, cell: str) -> list[dict]:
    path = REPO / "runs" / run_id / f"{cell}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def selected(lines: list[dict], bank: dict[str, dict]) -> dict[str, list[dict]]:
    """qid → its non-correct attempts (rep order), tuning split and non-judge questions only."""
    out: dict[str, list[dict]] = {}
    for r in lines:
        q = bank[r["qid"]]
        if q.get("split") != "tuning" or q["scoring"] == "judge":
            continue
        if r.get("status") != "done" or r["final"]["outcome"] == "correct":
            continue
        out.setdefault(r["qid"], []).append(r)
    return {qid: sorted(out[qid], key=lambda r: r["rep"]) for qid in sorted(out, key=lambda x: int(x[1:]))}


# ---------------------------------------------------------------------------
# Rendering one case


def _cell(v) -> object:
    if isinstance(v, str) and len(v) > CELL_CHARS:
        return v[:CELL_CHARS] + "…"
    return v


def _rows(columns: list[str], rows: list[list], limit: int) -> str:
    lines = [f"列：{json.dumps(columns, ensure_ascii=False)}",
             f"共 {len(rows)} 行" + (f"，以下是前 {limit} 行" if len(rows) > limit else "") + "："]
    lines += [json.dumps([_cell(v) for v in row], ensure_ascii=False, default=str) for row in rows[:limit]]
    return "\n".join(lines)


def _ref_rows(path: Path) -> tuple[list[str], list[list]]:
    with path.open(encoding="utf-8", newline="") as fh:
        table = list(csv.reader(fh))
    return table[0], table[1:]


def _turn(turn: dict, raw_dir: Path, qid: str, rep: int) -> list[str]:
    parts = [f"假设说明：{turn.get('assumption') or '（无）'}"]
    if turn.get("query"):
        parts += ["```sql", turn["query"].strip(), "```"]
    cand = candidate_of(turn, raw_dir, qid, rep)
    if cand == REFUSAL:
        parts.append("结果：拒答（CANNOT_ANSWER）")
    elif isinstance(cand, ExecError):
        parts.append(f"结果：执行失败。报错：{cand.message[:ERROR_CHARS]}")
    else:
        cols = [c["name"] for c in turn["exec"].get("columns", [])]
        parts.append(_rows(cols, cand, ATTEMPT_ROWS))
    return parts


OUTCOME_ZH = {"wrong": "结果与参考不一致", "exec_error": "执行失败", "refused": "拒答", "pending": "未判定"}


def _names(cols: list[str], idx: list[int]) -> str:
    return "、".join(f"`{cols[i]}`" for i in idx)


def ranking_rule(rules: dict, cols: list[str]) -> list[str]:
    """Scorer v2's row-count rule for top_n and selection questions, in words (T14-1, user ruling (a)).

    The reference lists every member tied at the boundary, but an answer must return exactly N rows
    (exactly n per group); listing all the tied members scores wrong."""
    top, sel = rules.get("top_n"), rules.get("selection")
    if top is not None:
        return [f"评分规则：前 {top} 名要**恰好返回 {top} 行**（核实结果不足 {top} 行时全部返回）。"
                f"按 {_names(cols, rules['tie_columns'])} 排名，第 {top} 名有并列时，下面的核实结果列出了并列的全部成员，"
                f"作答从并列成员里任取几个凑足 {top} 行即可；把并列成员全部列出、行数多于 {top} 会判错。"]
    if sel:
        out = []
        for k, st in enumerate(sel["stages"], 1):
            scope = "在全部结果中" if not st["group_columns"] else f"每个 {_names(cols, st['group_columns'])} 分组内"
            if st["parent"] is not None:
                scope = f"在第 {st['parent'] + 1} 层选中的对象内，{scope}"
            order = "、".join(f"{_names(cols, [o['column']])} {'从大到小' if o['descending'] else '从小到大'}"
                              for o in st["order_by"])
            layer = f"第 {k} 层：" if len(sel["stages"]) > 1 else ""
            short = f"（不足 {st['n']} 个的分组全取）" if st["n"] > 1 else ""
            out.append(f"{layer}{scope}按 {order}取前 {st['n']} 个 {_names(cols, st['object_columns'])}，"
                       f"**恰好 {st['n']} 个**{short}。")
        lead = "评分规则（分层选取）：" if len(out) > 1 else "评分规则："
        return [lead + "".join(out) + "第 n 名有并列时，核实结果列出了并列的全部成员，作答从中任取凑足 n 个即可；"
                "把并列成员全部列出、个数多于 n 会判错。"]
    return []


def case_text(qid: str, q: dict, attempts: list[dict], raw_dir: Path, root: Path) -> str:
    n_refs = len(q["refs"])
    head = (f"共 {n_refs} 种可接受的结果，作答与其中任一种一致即算对" if n_refs > 1
            else "作答要与它一致")
    parts = [f"# {qid}", "", "## 问题", q["text_zh"].strip(), "", f"## 核实后的正确结果（{head}）"]
    for i, ref in enumerate(q["refs"], 1):
        cols, rows = _ref_rows(root / ref["result_path"])
        # a reference may carry its own rules (questions.load_zh: ref_rules), else the question's
        rules = ref.get("rules") if ref.get("rules") is not None else (q.get("rules") or {})
        parts += ["", f"### 正确结果 {i}", f"口径：{ref['interpretation'].strip()}", *ranking_rule(rules, cols),
                  _rows(cols, rows, REF_ROWS)]
    parts += ["", f"## 模型答错的作答（共 {len(attempts)} 次）"]
    for n, rec in enumerate(attempts, 1):
        f = rec["final"]
        parts += ["", f"### 作答 {n}",
                  f"判定：{OUTCOME_ZH.get(f['outcome'], f['outcome'])}" + (f"（{f['reason']}）" if f.get("reason") else "")]
        turns = rec["turns"]
        for t in turns:
            if len(turns) > 1:
                label = "第一次查询（执行报错，报错已发回模型修正一次）" if t["turn"] == 0 else "修正后的查询"
                parts += ["", f"#### {label}"]
            parts += _turn(t, raw_dir, qid, rec["rep"])
    return "\n".join(parts).rstrip() + "\n"


README = """# 调优包 {name}（T14 B 角）

## 这是什么

你在模拟一个已上线的智能问数系统的运营：用户对答错的回答点了踩，分析师核实了正确结果。
`cases/` 里每个文件是一道这样的题：问题、模型的查询与假设说明、查询返回的结果摘要、核实后的正确结果。
只有答错的作答，没有答对的作答。被测系统的语义层（L1）在工作目录的 `semantic/` 里，
模型看到的上下文由 `semantic/source.yaml` 渲染而来（物理名是 ClickHouse 的 `库名.表名`）。

共 {n_q} 道题、{n_a} 次答错的作答。清单见 `MANIFEST.json`。

## 你的任务

把这些 bad case 反馈进语义层，让系统在**没见过的问题**上也答得更好：

1. 可以补充或改写约定、字段描述、同义词；可以写**不超过 15 条**「问题 → 查询」示例，示例只能来自本调优包里的题。
2. 全部写进 `semantic/tuning/{tuning}.yaml`（任意 YAML 映射；渲染器会把它整体挂在上下文的 `tuning:` 节下，原样给模型看）。
   「改写」也写在这个文件里，说明它取代原文哪一条；**不得改动 `semantic/` 下的其他文件**（`source.yaml` 已冻结，只能叠加）。
3. 查询用 ClickHouse SQL，表名和列名照 `semantic/source.yaml` 的物理名写。
4. 记下你写补充花了多少小时，写在文件末尾的注释里。

## 不能做

- 不得设法获取完整题库、其他题目、其他单元的结果；不得用子 agent 代替你做这件事。
- 不得上网查找任何公开 text-to-SQL 基准的题目、参考 SQL 或语义文档。
"""


# ---------------------------------------------------------------------------
# Export and check


def export(name: str, eval_tag: str, out: Path) -> dict:
    run_id, raw_run, cell, tuning = PACKETS[name]
    root = eval_dir()
    eval_full = verify_eval_tag(eval_tag, root)
    bank = bank_records(root)
    lines = source_lines(run_id, cell)
    picks = selected(lines, bank)
    raw_dir = R.raw_root() / raw_run / cell
    if out.exists():
        shutil.rmtree(out)
    (out / "cases").mkdir(parents=True)
    files = {}
    for qid, attempts in picks.items():
        text = case_text(qid, bank[qid], attempts, raw_dir, root)
        (out / "cases" / f"{qid}.md").write_text(text, encoding="utf-8")
        files[f"cases/{qid}.md"] = sha256(text.encode("utf-8"))
    n_a = sum(len(a) for a in picks.values())
    (out / "README.md").write_text(README.format(name=name, n_q=len(picks), n_a=n_a, tuning=tuning), encoding="utf-8")
    manifest = {
        "packet": name, "cell": cell, "tuning_file": f"semantic/tuning/{tuning}.yaml",
        "questions": [{"qid": qid, "reps": [r["rep"] for r in a]} for qid, a in picks.items()],
        "n_questions": len(picks), "n_attempts": n_a, "files": files,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # provenance stays outside the packet: B needs no run ids or bank commits
    manifest["provenance"] = {"source_run": run_id, "runs_raw": raw_run, "eval_tag": eval_tag,
                              "eval_commit": eval_full, "harness_commit": R.harness_commit()}
    return manifest


def check(name: str, out: Path, manifest: dict) -> list[str]:
    """Every check against the bank split and the source log; returns failures (empty = pass)."""
    run_id, _raw, cell, _t = PACKETS[name]
    bank = bank_records(eval_dir())
    lines = source_lines(run_id, cell)
    by_key = {(r["qid"], r["rep"]): r for r in lines}
    fails = []
    listed = {q["qid"] for q in manifest["questions"]}
    on_disk = {p.stem for p in (out / "cases").glob("*.md")}
    if listed != on_disk:
        fails.append(f"manifest and cases/ differ: {sorted(listed ^ on_disk)}")
    for q in manifest["questions"]:
        rec = bank.get(q["qid"])
        if rec is None:
            fails.append(f"{q['qid']}: not in the bank")
            continue
        if rec.get("split") != "tuning":
            fails.append(f"{q['qid']}: split is {rec.get('split')!r}, not tuning")
        if rec["scoring"] == "judge":
            fails.append(f"{q['qid']}: judge question")
        for rep in q["reps"]:
            if by_key[(q["qid"], rep)]["final"]["outcome"] == "correct":
                fails.append(f"{q['qid']} r{rep}: a correct attempt is in the packet")
    # completeness: every non-correct, non-judge tuning attempt is in
    want = {(r["qid"], r["rep"]) for r in lines if bank[r["qid"]].get("split") == "tuning"
            and bank[r["qid"]]["scoring"] != "judge" and r["final"]["outcome"] != "correct"}
    have = {(q["qid"], rep) for q in manifest["questions"] for rep in q["reps"]}
    if want != have:
        fails.append(f"attempts missing or extra: {sorted(want ^ have)}")
    # leakage: no file names another question, and no held-out question text appears
    allowed_files = {"README.md", "MANIFEST.json"} | {f"cases/{qid}.md" for qid in listed}
    present = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
    if present != allowed_files:
        fails.append(f"unexpected files: {sorted(present ^ allowed_files)}")
    heldout_text = {qid: r["text_zh"].strip() for qid, r in bank.items() if r.get("split") != "tuning"}
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        stranger = ({m for m in QID.findall(text)} & set(bank)) - listed   # Q1–Q4 quarter labels are not ids
        if stranger:
            fails.append(f"{path.relative_to(out)} names questions outside the packet: {sorted(stranger)}")
        for qid, t in heldout_text.items():
            if t and t in text:
                fails.append(f"{path.relative_to(out)} contains the text of held-out/other {qid}")
        for other in ("SQL-L0", "SQL-R", "SQL-L1c", "SQL-L1.5", "SQL-L2", "DAX-", "JSON-L2"):
            if other in text:
                fails.append(f"{path.relative_to(out)} mentions another cell {other}")
    return fails


def split_table(name: str, manifest: dict) -> list[str]:
    """Question-by-question cross-check against the bank split (ids only)."""
    run_id, _raw, cell, _t = PACKETS[name]
    bank = bank_records(eval_dir())
    lines = source_lines(run_id, cell)
    outcomes: dict[str, list[str]] = {}
    for r in sorted(lines, key=lambda r: r["rep"]):
        outcomes.setdefault(r["qid"], []).append(r["final"]["outcome"])
    listed = {q["qid"]: q["reps"] for q in manifest["questions"]}
    rows = ["| 题号 | 划分 | 评分 | 第一次运行 r1/r2/r3 | 进包 | 理由 |", "|---|---|---|---|---|---|"]
    for qid in sorted(bank, key=lambda x: int(x[1:])):
        rec = bank[qid]
        if rec.get("split") != "tuning":
            why = "留出题"
        elif rec["scoring"] == "judge":
            why = "judge 题"
        elif qid in listed:
            why = f"答错 r{','.join(map(str, listed[qid]))}"
        else:
            why = "3 次全对"
        rows.append(f"| {qid} | {rec.get('split')} | {rec['scoring']} | {'/'.join(outcomes.get(qid, []))} | "
                    f"{'是' if qid in listed else '否'} | {why} |")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packet", default="sql-l1", choices=sorted(PACKETS))
    ap.add_argument("--eval-tag", default="eval-v1.2")
    args = ap.parse_args(argv)

    out = PACKET_ROOT / args.packet
    manifest = export(args.packet, args.eval_tag, out)
    fails = check(args.packet, out, manifest)
    bank = bank_records(eval_dir())
    counts = {s: sum(1 for r in bank.values() if r.get("split") == s and r["scoring"] != "judge") for s in ("tuning", "heldout")}
    judge = sum(1 for r in bank.values() if r["scoring"] == "judge")
    p = manifest["provenance"]
    report = [
        f"# 调优包 {args.packet}：清单与题集划分逐题核对", "",
        f"- 生成：`uv run python -m harness.tuning_packet --packet {args.packet} --eval-tag {args.eval_tag}`"
        f"（harness `{p['harness_commit'][:7]}`）",
        f"- 题库：`{p['eval_tag']}` = `{p['eval_commit'][:7]}`（只读 worktree，`verify_eval_tag` 校验通过）",
        f"- 第一次运行：`runs/{p['source_run']}/{PACKETS[args.packet][2]}.jsonl`（harness-v1.1 最终判定），"
        f"作答结果取自 `$SEMDEBT_DATA_DIR/runs-raw/{p['runs_raw']}/`（逐个核对 sha256）",
        f"- 题库 {len(bank)} 题：调优题 {counts['tuning']}、留出题 {counts['heldout']}（均不含 judge），judge {judge}",
        f"- 进包：{manifest['n_questions']} 题、{manifest['n_attempts']} 次答错的作答；"
        "规则：调优题、非 judge、第一次运行 3 次中至少 1 次不是 correct，只放不是 correct 的那几次",
        f"- 包的位置：`build/tuning-packet/{args.packet}/`（不入库，含题面）；B 角写 `{manifest['tuning_file']}`",
        "", "## 自动核对", "",
    ]
    checks = ["清单题号与 `cases/` 文件一一对应", "进包的题全部是 `split: tuning`", "没有 judge 题",
              "没有 correct 的作答", "调优题里所有非 correct 的作答都在包里（不漏）",
              "包里只有 README、MANIFEST 与清单里的题文件", "任何文件都不出现包外的题号（与题库题号比对；Q1–Q4 是季度）",
              "任何文件都不含留出题的题面", "不提及其他单元"]
    report += [f"- {'✅' if not fails else '—'} {c}" for c in checks]
    report += [""] + ([f"**失败**：{f}" for f in fails] if fails else ["结果：全部通过。"])
    report += ["", "## 逐题对照（题号、划分、第一次运行的判定）", ""] + split_table(args.packet, manifest)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"packet-{args.packet}-check.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    committed = {k: v for k, v in manifest.items()}
    (REPORT_DIR / f"packet-{args.packet}-manifest.json").write_text(
        json.dumps(committed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out}: {manifest['n_questions']} questions, {manifest['n_attempts']} attempts")
    print("check: " + ("PASS" if not fails else "FAIL\n  " + "\n  ".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
