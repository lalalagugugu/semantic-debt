"""T19b spot-check packet: the 10 sampled disagreements with question, references, the attempt and
both labels, written to $SEMDEBT_DATA_DIR/t19b-spotcheck/spotcheck.md (question text: never in the repo).

    SEMDEBT_EVAL_DIR=$SEMDEBT_DATA_DIR/eval-ro-eval-v1.2 uv run python scripts/t19b_spotcheck_packet.py
"""
import csv, json, os, re, sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness import attribute_l1 as A, run_direct as R

SPOT = [("Q17", 1), ("Q24", 2), ("Q31", 1), ("Q61", 1), ("Q65", 1),
        ("Q76", 2), ("Q87", 2), ("Q89", 1), ("Q99", 1), ("Q113", 2)]
ROOTS = {1: "文档没写", 2: "文档写了但有歧义", 3: "文档清楚，模型没理解或没用上", 4: "题面本身有歧义", 5: "参考答案或评分可疑"}
ctx = yaml.safe_load(Path("build/contexts/SQL-L1.yaml").read_text(encoding="utf-8"))


def resolve(loc: str) -> str:
    loc = loc.strip()
    m = re.fullmatch(r"conventions#(\d+)", loc)
    if m:
        for c in ctx["conventions"]:
            if str(c["id"]) == m.group(1):
                return yaml.safe_dump(c, allow_unicode=True, sort_keys=False)
    m = re.fullmatch(r"datasets\.(\w+\.\w+)(?:\.(columns)\.(\w+)|\.(\w+))?", loc)
    if m:
        for d in ctx["datasets"]:
            if d["name"] == m.group(1):
                if m.group(3):
                    for c in d["columns"]:
                        if c["name"] == m.group(3):
                            return yaml.safe_dump(c, allow_unicode=True, sort_keys=False)
                if m.group(4):
                    return f"{m.group(4)}: {d.get(m.group(4))}"
                return yaml.safe_dump({k: v for k, v in d.items() if k != "columns"}, allow_unicode=True, sort_keys=False)
    m = re.fullmatch(r"metrics\.(.+)", loc)
    if m:
        for x in ctx["metrics"]:
            if x["name"] == m.group(1):
                return yaml.safe_dump(x, allow_unicode=True, sort_keys=False)
    m = re.fullmatch(r"data_quality#(.+)", loc)
    if m:
        for x in ctx["data_quality"]:
            if str(x["id"]) == m.group(1):
                return yaml.safe_dump(x, allow_unicode=True, sort_keys=False)
    m = re.fullmatch(r"(data_quality|relationships|conventions|metrics|datasets)\[(\d+)\]", loc)
    if m and int(m.group(2)) < len(ctx[m.group(1)]):
        return yaml.safe_dump(ctx[m.group(1)][int(m.group(2))], allow_unicode=True, sort_keys=False)
    return "（无法自动定位这个位置，请在 build/contexts/SQL-L1.yaml 里搜索）"


def evidence(locs: str) -> list[str]:
    if locs in ("未找到", "不涉及文档", ""):
        return [f"**{locs or '（空）'}**"]
    out = []
    for loc in locs.split("；"):
        out += [f"`{loc}`", "```yaml", resolve(loc).rstrip(), "```"]
    return out


bank = A.bank_records()
src = {(r["qid"], r["rep"]): r for r in A.source_lines()}
raw_src = R.raw_root() / "20261018-T13-sql-direct-01" / "SQL-L1"
flash = {(r["qid"], r["rep"]): r for r in map(json.loads, open("runs/20261020-T19b-attrib-01/attribution.jsonl"))}
codex = {(r["question_id"], int(r["round"])): r for r in csv.DictReader(open("reports/attribution/codex.csv"))}
fraw = R.raw_root() / "20261020-T19b-attrib-01"

md = ["# T19b 抽检包（含题面，不入库）", "",
      "每条先看材料，自己判出根因（1–5），写在「你的判定」里，再展开看两家的判定和理由。",
      "根因：" + "；".join(f"{k} = {v}" for k, v in ROOTS.items()) + "。",
      "判定标准见 `reports/attribution/codebook.md` 第三节。", ""]
for i, (q, rep) in enumerate(SPOT, 1):
    rec = src[(q, rep)]
    msg = A.user_message(rec, bank[q], raw_src).replace("\n## ", "\n#### ").replace("\n### ", "\n##### ")
    msg = re.sub(r"^## ", "#### ", msg)
    f, c = flash[(q, rep)], codex[(q, rep)]
    fnote = json.loads(json.loads((fraw / f"{q}_r{rep}.json").read_text())["choices"][0]["message"]["content"])["note"]
    md += [f"## {i}. {q} 第 {rep} 次", "", msg.rstrip(), "",
           "**你的判定**：根因 ___　理由：", "",
           "<details><summary>展开：两家的判定</summary>", "",
           f"- **Flash**：{f['labels']['category']}，根因 {f['labels']['root_cause']}（{ROOTS[f['labels']['root_cause']]}），"
           f"已声明假设 {f['labels']['declared_assumption']}。理由：{fnote}"]
    md += ["- Flash 引用的 L1 位置："] + evidence(f["labels"]["doc_evidence"])
    md += [f"- **Codex**：{c['category']}，根因 {c['root_cause']}（{ROOTS[int(c['root_cause'])]}），"
           f"已声明假设 {c['declared_assumption']}。理由：{c['note']}"]
    md += ["- Codex 引用的 L1 位置："] + evidence(c["doc_evidence"])
    md += ["", "</details>", "", "---", ""]
out = Path(os.environ["SEMDEBT_DATA_DIR"]) / "t19b-spotcheck" / "spotcheck.md"
out.parent.mkdir(exist_ok=True)
out.write_text("\n".join(md), encoding="utf-8")
print(out, len("\n".join(md)))
