#!/usr/bin/env python
"""Re-execute the public benchmark and compare deterministic verdicts.

The output contains only system names, question IDs, verdicts, row counts, and
diagnostic codes.  Questions and SQL remain in ``SEMDEBT_EVAL_DIR``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from harness.scorer import ExecError, score_detailed  # noqa: E402


RUN_ID = "paper-2026-04-22"
EXCLUDED_QUESTION_IDS = {33}
ORDERED_QUESTION_IDS = {
    7, 22, 25, 27, 33, 45, 46, 67, 69, 73, 74, 78, 79, 85, 87, 88,
    92, 94, 97, 98,
}
TOP_N_RULES = {
    7: (10, (1,)),
    25: (1, (1,)),
    27: (10, (3,)),
    46: (1, (1,)),
    73: (10, (3,)),
    79: (10, (3,)),
    87: (20, (3,)),
    88: (20, (1,)),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    data_dir = os.environ.get("SEMDEBT_DATA_DIR")
    eval_dir = os.environ.get("SEMDEBT_EVAL_DIR")
    if not data_dir or not eval_dir:
        raise SystemExit("SEMDEBT_DATA_DIR and SEMDEBT_EVAL_DIR must be set")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-dir", type=Path, default=Path(data_dir) / "chdb-eval")
    parser.add_argument("--eval-dir", type=Path, default=Path(eval_dir))
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def question_rules(question_id: int) -> dict[str, object]:
    top_rule = TOP_N_RULES.get(question_id)
    return {
        "ordered": question_id in ORDERED_QUESTION_IDS,
        "top_n": top_rule[0] if top_rule else None,
        "tie_columns": list(top_rule[1]) if top_rule else [],
    }


def extend_boundary_ties(sql: str, question_id: int) -> str:
    top_rule = TOP_N_RULES.get(question_id)
    if not top_rule:
        return sql
    top_n = top_rule[0]
    pattern = re.compile(rf"\bLIMIT\s+{top_n}\s*;?\s*$", re.IGNORECASE)
    extended, replacements = pattern.subn(f"LIMIT {top_n} WITH TIES", sql)
    if replacements != 1:
        raise ValueError(f"q{question_id:02d}: cannot extend Top-N reference boundary")
    return extended


def execute_rows(sess: Any, sql: str) -> list[list[object]] | ExecError:
    try:
        output = str(sess.query(sql, "JSONCompactEachRow"))
        rows = [json.loads(line) for line in output.splitlines() if line.strip()]
    except Exception as error:
        return ExecError(str(error))
    return rows


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    benchmark_path = args.eval_dir / "vendor/cube/text_to_sql_benchmark.json"
    run_root = args.eval_dir / "vendor/cube/published-runs" / RUN_ID
    benchmark = load_json(benchmark_path)
    questions = {int(item["id"]): item for item in benchmark["questions"]}
    systems = sorted(
        path.name
        for path in run_root.iterdir()
        if path.is_dir() and path.name not in {"reference", "scoring"}
    )
    if len(questions) != 100 or len(systems) != 6:
        raise SystemExit(f"expected 100 questions and 6 systems, got {len(questions)} and {len(systems)}")

    from chdb import session

    sess = session.Session(str(args.db_dir))
    records: list[dict[str, object]] = []
    references: dict[int, list[list[object]] | ExecError] = {}
    try:
        sess.query("SET max_execution_time = 30")
        for question_id, question in sorted(questions.items()):
            if question_id in EXCLUDED_QUESTION_IDS:
                references[question_id] = ExecError("published reference excluded")
                continue
            reference_sql = extend_boundary_ties(question["expected_sql"], question_id)
            references[question_id] = execute_rows(sess, reference_sql)
            if isinstance(references[question_id], ExecError):
                raise RuntimeError(f"q{question_id:02d} reference failed: {references[question_id].message}")

        completed = 0
        for system in systems:
            print(f"executing {system}", flush=True)
            for question_id in sorted(questions):
                candidate_record = load_json(run_root / system / f"q{question_id:02d}.json")
                candidate = execute_rows(sess, candidate_record["sql"])
                strict_record = load_json(run_root / "scoring" / system / f"q{question_id:02d}.json")
                reference = references[question_id]

                if question_id in EXCLUDED_QUESTION_IDS:
                    result_outcome = "excluded"
                    result_reason = "published_reference_unavailable"
                    reference_count = None
                elif isinstance(reference, ExecError):
                    raise AssertionError("unexpected reference error")
                else:
                    result = score_detailed(candidate, [reference], question_rules(question_id))
                    result_outcome = result.outcome
                    result_reason = result.reason
                    reference_count = len(reference)

                records.append(
                    {
                        "system": system,
                        "question_id": question_id,
                        "our_outcome": result_outcome,
                        "our_reason": result_reason,
                        "strict": strict_record["verdict"],
                        "analytical": strict_record["analytical_verdict"],
                        "candidate_row_count": None if isinstance(candidate, ExecError) else len(candidate),
                        "reference_row_count": reference_count,
                        "reexec_error": candidate.message if isinstance(candidate, ExecError) else None,
                    }
                )
                completed += 1
                if completed % 10 == 0:
                    print(f"executed {completed}/600", flush=True)
    finally:
        sess.close()

    strict_comparable = [record for record in records if record["our_outcome"] != "excluded"]
    strict_agreements = sum(
        (record["our_outcome"] == "correct") == (record["strict"] == "pass")
        for record in strict_comparable
    )
    analytical_agreements = sum(
        (record["our_outcome"] == "correct") == (record["analytical"] == "pass")
        for record in strict_comparable
    )
    output = {
        "run_id": RUN_ID,
        "systems": systems,
        "executed_candidates": len(records),
        "excluded_records": len(records) - len(strict_comparable),
        "strict_agreements": strict_agreements,
        "strict_comparable": len(strict_comparable),
        "strict_agreement_rate": strict_agreements / len(strict_comparable),
        "analytical_agreements": analytical_agreements,
        "analytical_agreement_rate": analytical_agreements / len(strict_comparable),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"strict agreement: {strict_agreements}/{len(strict_comparable)} "
        f"({strict_agreements / len(strict_comparable):.1%})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
