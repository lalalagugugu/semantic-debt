"""Offline audit and frozen v2 screening of the T29 expanded pilot."""
import csv
from decimal import Decimal
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness import prompt as P
from harness.executors import mask_sql, strip_trailing_semicolons
from harness.questions import load_questions, verify_eval_tag
from harness.selective_v2 import best_group, confidence_auc, confidence_record, screening

RUN = "20261026-T29-expanded-01"
COMMIT = "f726f5bb1a5779a8d6b3a31a5103de510206129c"
FP = "e72d3c7f663d3e1383b00b3884cb4501"
C = "SQL-L1plus-confidence"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def format_error(text):
    if text.strip() == P.REFUSAL:
        return False
    parsed = P.parse_response(text)
    return (not (parsed.query and parsed.n_code_blocks == 1)
            or ";" in mask_sql(strip_trailing_semicolons(parsed.query or "")))


def public_record(record):
    """Keep hashes and categories; queries, assumptions and SQL errors stay private."""
    result = json.loads(json.dumps(record))
    result.get("confidence", {}).pop("value", None)
    for turn in result.get("turns", []):
        turn.pop("query", None)
        turn.pop("assumption", None)
        for key in ("error", "columns", "detail"):
            turn.get("exec", {}).pop(key, None)
    return result


def confidence_category(value, native):
    if native:
        return "native_refusal"
    if value is None:
        return "invalid"
    for threshold, category in ((90, "ge90"), (75, "75_to_90"), (50, "50_to_75")):
        if value >= threshold:
            return category
    return "below50"


def audit_ledger(path, raw):
    outstanding, calls = {}, {}
    total = Decimal(0)
    maximum = None
    for line in path.read_text().splitlines():
        r = json.loads(line)
        assert r["model"] == "deepseek-flash" and Decimal(r["limit_cny"]) == 3
        maximum = Decimal(r["max_call_cost_cny"])
        ticket = r["request_id"]
        if r["event"] == "request":
            assert ticket not in outstanding
            outstanding[ticket] = r
            assert total + len(outstanding)*maximum <= 3
        elif r["event"] == "charge":
            request = outstanding.pop(ticket)
            key = tuple(request[k] for k in ("cell", "qid", "rep", "turn"))
            assert key not in calls
            cell, qid, rep, turn = key
            payload = json.loads((raw / cell / f"{qid}_r{rep}_t{turn}.json").read_bytes())
            u = payload["usage"]
            assert all(type(u.get(k)) is int and u[k] >= 0 for k in (
                "prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens"))
            assert u["prompt_cache_hit_tokens"] + u["prompt_cache_miss_tokens"] == u["prompt_tokens"]
            cost = (Decimal(u["prompt_cache_hit_tokens"])*Decimal(".02")
                    + Decimal(u["prompt_cache_miss_tokens"])
                    + Decimal(u["completion_tokens"])*4)/Decimal(1_000_000)
            assert abs(cost-Decimal(r["cost_cny"])) < Decimal("1e-12")
            total += cost
            calls[key] = dict(usage=u, cost=cost, payload=payload)
        elif r["event"] == "closed":
            assert r["admission_closed"]
        else:
            raise AssertionError("unknown ledger event")
    assert not outstanding, "unsettled API calls"
    return calls, total, maximum


def write_report(result, preflight, out):
    def pct(value):
        return "—" if value is None else f"{value:.1%}"
    cells, metrics, auc = result["cells"], result["metrics"], result["auc"]
    lines = ["# T29 扩展试跑：v2 按约定交付率口径", "",
             f"`{RUN}`：C → B → A，169次首轮全部完成，含40次执行纠错，共{result['total_calls']}次官方API调用，实花 **{result['total_cost_cny']}元**（预计{preflight['expected_cost_cny']:.8f}元，上限3元）。2026-10-26北京时间12:04启动，午休内全部完成，未触发14:00高峰或预算停发。", "",
             "结果出来前的双口径与B组拆分决定已提交并推送，登记提交`798c44a`早于所有本次付费作答。下表的v2判对率即现行「按约定交付率」，不等于尚待实施的只看内容准确率。", "",
             "|单元|首轮|含纠错调用|模型拒答|最终格式错|全部调用格式错|费用（元）|",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for name in preflight["execution_order"]:
        s = cells[name]
        lines.append(f"|{name}|{s['attempts']}|{s['calls']}|{s['refusals']}|{s['final_format_errors']}|{s['format_error_calls']}|{s['cost_cny']}|")
    lines += ["", "C最终13次格式错均为缺少把握行，按冻结规则在三个门槛都拒答；模型原生拒答0次。未改提示、未补跑，执行纠错仍最多一次。C三门槛共用同一批49次作答，门槛不增加API调用。", "",
              "## 预登记筛选（v2，试跑只筛选）", "",
              "条件同时满足才达标：作答比例≥50%；作答部分v2判对率高于同题原3次的逐题平均；原基线在被拒题上的判对率低于被答题。多组达标按+1/−3/0每题均分优选，同分取作答比例。A仅诊断，不是正式候选。", "",
              "|单元/门槛|作答/题数|作答比例|v2判对/作答|同题原三次均值|原基线：被答/被拒|k3每题均分|三项筛选|",
              "|---|---:|---:|---:|---:|---:|---:|---|"]
    for name, m in metrics.items():
        lines.append(f"|{name}|{m['answered']}/{m['questions']}|{pct(m['coverage'])}|{m['correct_answered']}/{m['answered']}（{pct(m['accuracy_answered'])}）|{pct(m['baseline_accuracy'])}|{pct(m['baseline_answered'])}/{pct(m['baseline_rejected'])}|{m['score_k3']:.4f}|{'达标' if m['eligible'] else '未达标'}|")
    lines += ["", "B两档均未拒答，无法满足被拒题基线低于被答题的第三项；即使作答部分v2判对率高于基线，也不算筛选达标。C≥50与≥75的作答比例和作答部分v2判对率满足前两项，但被拒题基线反而更高；C≥90作答比例仅42.9%，第三项也未满足。B/C没有达标候选。", "",
              f"C用全部{auc['n']}个有效原始把握值区分v2对错，AUC **{auc['auc']:.3f}**，按题bootstrap 95%区间 **[{auc['lo']:.3f}, {auc['hi']:.3f}]**。使用10,000次、种子20261019，{auc['bootstrap_valid']}次有效，单类重采样3次跳过；13次无把握不补0。AUC与门槛无关。", ""]
    if result["v2_no_formal_condition"]:
        lines += ["A四档、B两档拒答均0（均<5%），C的AUC 95%区间含0.5，触发预登记的v2停止条件：**「在本模型上未看到提示词能让模型取舍」**。限定为单一模型、调优题样本，C仅36个有效把握且有13次格式缺失；不写「证明不能」，不作为正式效果结论。", ""]
    lines += ["## 后续决定仍待双口径", "",
              "v2下暂不进入正式运行，B未达标，当前不触发拆分试跑。按用户结果前登记：待内容准确率口径确定，对同一批结果与同题基线用相同筛选规则复算；两种口径不一致交用户裁决，正式运行要等两种口径都算完再决定。若B在所需复算中达标，正式前仍先补只挪位置、只改措辞两组k3原20题×1的拆分试跑（约0.3元，另PR、另tag、另批）；位置与措辞的作用不能从本次B分开归因。", "",
              "## 费用与完整性", "",
              f"逐份检查{result['total_calls']}个原包、全部最终执行文件及其哈希，usage与API账单字段一致；重算费用与乱序费用账本及作答日志逐项核对。未结算0、传输重试0、指纹变化0、API异常0。最大单次实际费用{result['max_observed_call_cost_cny']}元，低于预估{result['max_estimated_call_cost_cny']}元，超预估调用0。准入已预扣在途费用；单次实际费用不超过预估时总花费不超过上限，单次超出时如实记账并停发。", "",
              f"实际每调用平均输出{result['mean_output_tokens']:.1f} tokens（原估算974），缓存命中占比{result['cache_hit_ratio']:.2%}；实际费用高于预计，但低于3元上限，未事后回写preflight。", "",
              "早间首次启动仅外部包装器参数错误、API调用0、费用0；169条失败日志原样保留，随后在同run-id追加169条完成日志。午休直接执行冻结原入口，不使用包装器或其他截止机制。harness-sel-v2=f726f5b；日志f726f5b-dirty仅因运行副本恢复冻结semantic/render，harness源码、入口与preflight均通过tag校验。chDB仅同一个运行进程使用T29独立副本。", "",
              "原始API回包、执行结果及账本均在SEMDEBT_DATA_DIR/runs-raw同名目录。公开日志移除SQL、假设、引擎错误原文与原始把握值；保留题号、单元、类别、计数和审计元数据。原始回包不入库。`t29-expanded-audit.json`记录汇总与源/公开日志哈希，`t29-expanded-attempts.csv`为逐题类别，`runs/20261026-T29-expanded-01/manifest.json`为不可改写清单。", "",
              "复现：设置已确认的SEMDEBT_DATA_DIR及eval-v1.2题库环境后，`uv run --offline python scripts/t29_expanded_report.py`（只读私有原包，无API或查询执行）。免费D、B2已分别提交75e0ac4、23b83d4，本报告不改变它们的v2敏感性数字。", ""]
    (out / "t29-expanded.md").write_text("\n".join(lines))


def main():
    data = Path(os.environ["SEMDEBT_DATA_DIR"])
    work = data / "t29-expanded-sel-v2"
    raw = data / "runs-raw" / RUN
    preflight = json.loads((ROOT / "reports/validation/t29-expanded-preflight.json").read_text())
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip() == COMMIT
    subprocess.run(["git", "diff", "--exit-code", "harness-sel-v2", "--", "harness",
                    "scripts/t29_expanded_pilot.py", "reports/validation/t29-expanded-preflight.json"], cwd=work, check=True)
    baseline_source = ROOT / "runs/20261025-T22b-l1plus-l3a-03-rescore-01/SQL-L1plus.jsonl"
    base_rows = [json.loads(s) for s in baseline_source.read_text().splitlines()]
    assert len(base_rows) == 327 and len({(r['qid'],r['rep']) for r in base_rows}) == 327
    baseline = {q: sum(r["final"]["outcome"] == "correct" for r in base_rows if r["qid"] == q)/3
                for q in {r["qid"] for r in base_rows}}
    old = set(json.loads((ROOT / "reports/validation/t29-pilot-preflight.json").read_text())["pilot_qids"])
    verify_eval_tag("eval-v1.2")
    questions = {q.qid: q for q in load_questions(lang="zh")}
    c_scope = {q.qid for q in questions.values() if q.scoring == "deterministic"
               and q.meta.get("split") == "tuning" and not q.meta.get("low_discrimination")}
    assert len(c_scope) == 49 and set(preflight["authorized_qids"]) == c_scope | old
    calls, total, maximum = audit_ledger(raw / "spend-ledger.jsonl", raw)
    assert maximum == Decimal(str(preflight["max_call_cost_cny"]))
    attempts, groups, cell_stats, logs, started_at = [], {}, {}, {}, []
    used_calls = set()
    confidence_values = []
    for cell in preflight["execution_order"]:
        path = work / "runs" / RUN / f"{cell}.jsonl"
        source = [json.loads(s) for s in path.read_text().splitlines()]
        failures = [r for r in source if r["status"] != "done"]
        assert all(r["status"] == "harness_error" and r["error"] == "TypeError: stop_window() takes 0 positional arguments but 1 was given" for r in failures)
        records = [r for r in source if r["status"] == "done"]
        expected = 49 if cell == C else 20
        assert len(records) == expected and len({r["qid"] for r in records}) == expected
        assert all(r["rep"] == 1 for r in records)
        if cell != C:
            assert {r["qid"] for r in records} == old
        else:
            assert {r["qid"] for r in records} == c_scope
        stats = dict(attempts=expected, refusals=0, final_format_errors=0, final_format_categories={},
                     format_error_calls=0, calls=0, cost_cny=Decimal(0))
        selected = []
        for r in records:
            started_at.append(r["started_at"])
            assert r["system_sha256"] == preflight["system_sha256"][cell]
            assert r["harness_commit"] == "f726f5b-dirty" and r["eval_commit"] == "90e13b3"
            assert r["semantic_tag"] == "semantic-v1.6-l1plus" and r["eval_tag"] == "eval-v1.2" and not r["peak"]
            assert r["qid"] in preflight["authorized_qids"]
            assert r["question_sha256"] == sha(questions[r["qid"]].text.encode())
            assert r["final"]["outcome"] in ("correct", "wrong", "refused", "exec_error")
            cost, format_calls = Decimal(0), 0
            for t in r["turns"]:
                key = (cell, r["qid"], r["rep"], t["turn"])
                call = calls[key]
                used_calls.add(key)
                b = (raw / cell / f"{r['qid']}_r1_t{t['turn']}.json").read_bytes()
                assert sha(b) == t["raw_sha256"]
                payload, u = call["payload"], call["usage"]
                assert payload["system_fingerprint"] == FP and t["transport_retries"] == 0
                assert t["usage"]["prompt_tokens"] == u["prompt_tokens"]
                assert t["usage"]["completion_tokens"] == u["completion_tokens"]
                assert t["usage"]["cache_hit_tokens"] == u["prompt_cache_hit_tokens"]
                assert t["usage"]["cache_miss_tokens"] == u["prompt_cache_miss_tokens"]
                text = payload["choices"][0]["message"].get("content") or ""
                error = format_error(text)
                if cell == C:
                    parsed_confidence = confidence_record(text, r["final"])
                    error = False if parsed_confidence["native_refusal"] else error or parsed_confidence["format_error"]
                format_calls += error
                cost += call["cost"]
                if t["exec"].get("exec_raw_sha256"):
                    eb = (raw / cell / f"{r['qid']}_r1_t{t['turn']}.exec.json").read_bytes()
                    assert sha(eb) == t["exec"]["exec_raw_sha256"]
            assert abs(cost-Decimal(str(r["cost_cny"]))) < Decimal("1e-12")
            native = P.parse_response(text).refused
            assert native == (r["final"]["outcome"] == "refused")
            final_error = format_error(text)
            if cell == C:
                confidence = confidence_record(text, r["final"])
                assert confidence == r["confidence"]
                final_error = False if native else final_error or confidence["format_error"]
                if confidence["value"] is not None:
                    confidence_values.append((confidence["value"], r["final"]["outcome"] == "correct"))
                for gate, value in confidence["gates"].items():
                    groups.setdefault(f"{cell}-ge{gate}", []).append(dict(qid=r["qid"], answered=value["answered"], correct=r["final"]["outcome"] == "correct"))
            else:
                selected.append(dict(qid=r["qid"], answered=not native, correct=r["final"]["outcome"] == "correct"))
            error_category = "none"
            if final_error:
                error_category = "response_protocol"
                if cell == C and confidence["format_error"]:
                    lines = re.findall(r"^\s*把握\s*[:：](.*?)$", text, re.MULTILINE)
                    error_category = "missing_confidence" if not lines else "duplicate_confidence" if len(lines) > 1 else "invalid_confidence"
                categories = stats["final_format_categories"]
                categories[error_category] = categories.get(error_category, 0)+1
            attempts.append(dict(cell=cell, qid=r["qid"], rep=1, native_refusal=native,
                                 final_format_error=bool(final_error), format_error_calls=format_calls,
                                 format_category=error_category,
                                 calls=len(r["turns"]), cost_cny=str(cost), outcome=r["final"]["outcome"],
                                 confidence_category=confidence_category(r.get("confidence", {}).get("value"), native)
                                 if cell == C else "not_requested"))
            stats["refusals"] += native
            stats["final_format_errors"] += bool(final_error)
            stats["format_error_calls"] += format_calls
            stats["calls"] += len(r["turns"])
            stats["cost_cny"] += cost
        if cell != C:
            groups[cell] = selected
        stats["cost_cny"] = str(stats["cost_cny"])
        cell_stats[cell] = stats
        logs[cell] = dict(source_sha256=sha(path.read_bytes()), initial_startup_error_lines=len(failures))
    assert used_calls == set(calls) and len(attempts) == 169
    assert len(list(raw.glob("*/Q*_r*_t[01].json"))) == len(calls)
    assert sum(Decimal(s["cost_cny"]) for s in cell_stats.values()) == total
    metrics = {}
    for name, rows in groups.items():
        m = screening(rows, baseline)
        m.update(refusals=len(rows)-m["answered"], correct_answered=sum(r["answered"] and r["correct"] for r in rows),
                 format_errors=cell_stats[C if name.startswith(C) else name]["final_format_errors"])
        metrics[name] = m
    candidates = {n: m for n, m in metrics.items() if n.startswith(C) or "-front-" in n}
    auc = confidence_auc(confidence_values)
    no_formal = (all(s["refusals"]/s["attempts"] < .05 for n, s in cell_stats.items() if n != C)
                 and auc["indistinguishable"] is True)
    registration = subprocess.check_output(["git", "rev-parse", "798c44a"], cwd=ROOT, text=True).strip()
    registered_at = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", registration], cwd=ROOT, text=True))
    assert registered_at <= min(datetime.fromisoformat(t).timestamp() for t in started_at)
    usage_totals = {k: sum(c["usage"][k] for c in calls.values()) for k in (
        "prompt_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens")}
    result = dict(run_id=RUN, harness_tag="harness-sel-v2", harness_commit=COMMIT, scoring="v2_delivery",
                  model="deepseek-flash", system_fingerprint=FP,
                  registration_commit=registration, first_attempt_started_at=min(started_at),
                  last_response_created_at=datetime.fromtimestamp(max(c["payload"]["created"] for c in calls.values()), ZoneInfo("Asia/Shanghai")).isoformat(),
                  preflight_sha256=sha((ROOT / "reports/validation/t29-expanded-preflight.json").read_bytes()),
                  baseline_sha256=sha(baseline_source.read_bytes()), ledger_sha256=sha((raw / "spend-ledger.jsonl").read_bytes()),
                  total_calls=len(calls), total_cost_cny=str(total), max_estimated_call_cost_cny=str(maximum),
                  max_observed_call_cost_cny=str(max(c["cost"] for c in calls.values())),
                  calls_over_estimate=sum(c["cost"] > maximum for c in calls.values()),
                  usage_totals=usage_totals, mean_output_tokens=usage_totals["completion_tokens"]/len(calls),
                  cache_hit_ratio=usage_totals["prompt_cache_hit_tokens"]/usage_totals["prompt_tokens"],
                  budget_cny=3, pending_requests=0, cells=cell_stats, metrics=metrics, auc=auc,
                  v2_selection=best_group(candidates), v2_no_formal_condition=no_formal, logs=logs,
                  limitations=["single_model_tuning_sample", "screening_only", "content_accuracy_pending",
                               "both_metrics_required_before_formal", "B_requires_separate_factor_pilot_if_eligible"])
    out = ROOT / "reports/validation"
    with (out / "t29-expanded-attempts.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(attempts[0])); w.writeheader(); w.writerows(attempts)
    # Append only a sanitized suffix, retaining the initial failed-start lines byte for byte.
    for cell in preflight["execution_order"]:
        src = work / "runs" / RUN / f"{cell}.jsonl"
        dst = ROOT / "runs" / RUN / src.name
        existing = dst.read_text().splitlines() if dst.exists() else []
        lines = src.read_text().splitlines()
        rendered = [json.dumps(public_record(json.loads(line)), ensure_ascii=False) if json.loads(line)["status"] == "done" else line for line in lines]
        assert rendered[:len(existing)] == existing, "committed logs cannot be rewritten"
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("a") as f:
            for line in rendered[len(existing):]:
                f.write(line+"\n")
        logs[cell]["public_sha256"] = sha(dst.read_bytes())
    manifest = dict(run_id=RUN, harness_tag="harness-sel-v2", harness_commit=COMMIT,
                    registration_commit=registration, preflight_sha256=result["preflight_sha256"],
                    ledger_sha256=result["ledger_sha256"], logs=logs, completed_attempts=169,
                    initial_startup_error_lines=sum(r["initial_startup_error_lines"] for r in logs.values()),
                    total_calls=len(calls), total_cost_cny=str(total), pending_requests=0,
                    dirty_reason="Only semantic/ and render/ restored to semantic-v1.6-l1plus; frozen harness and entry match harness-sel-v2.")
    manifest_path = ROOT / "runs" / RUN / "manifest.json"
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2)+"\n"
    if manifest_path.exists():
        assert manifest_path.read_text() == serialized, "run manifest is immutable"
    else:
        with manifest_path.open("x") as f:
            f.write(serialized)
    (out / "t29-expanded-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    write_report(result, preflight, out)
    print(json.dumps({k: result[k] for k in ("total_calls", "total_cost_cny", "cells", "metrics", "auc", "v2_selection", "v2_no_formal_condition")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
