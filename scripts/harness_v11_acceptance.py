"""harness-v1.1 acceptance: rescore the shared scorer corpora through the harness's own
scoring path and count the verdicts.

Each case goes through ``run_direct.score_question`` exactly as an attempt does in a run or
in ``harness.rescore``: judge questions are ``pending``, execution errors and refusals are
scored in-process, a row set is scored by scorer v2 in a child process with the run's time
limit (``score_guard``). No model call, no query. Only counts reach stdout.

    uv run python scripts/harness_v11_acceptance.py \\
        $SEMDEBT_DATA_DIR/scorer-corpus/{t13,pilot288,ext600}.jsonl

"Final" counts take each attempt's last turn (the cases whose ``case_id`` does not end in
``/t0``), as T05b's reconciliation report does; judge cases are counted apart, whatever their
candidate. Anything that is not one of the four verdicts (``pending`` from the time limit,
``unscored``) is printed separately and must be absent.
"""

from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_direct as R  # noqa: E402
from harness.questions import Question  # noqa: E402
from harness.scorer_corpus import load_corpus  # noqa: E402


def question_of(case: dict) -> Question:
    rules = case["rules"] or []
    return Question(case["question_id"], "", refs=case["refs"], rules=rules[0] if rules else None,
                    ref_rules=rules or None, scoring="judge" if case["judge"] else "deterministic")


def verdict(case: dict) -> str:
    return R.score_question(case["candidate"], question_of(case))["outcome"]


def main(paths: list[str]) -> int:
    for path in paths:
        cases = [c for c in load_corpus(Path(path)) if not c["case_id"].endswith("/t0")]
        judge = [c for c in cases if c["judge"]]
        scored = [c for c in cases if not c["judge"]]
        with ThreadPoolExecutor(8) as pool:
            n = Counter(pool.map(verdict, scored))
        other = {k: v for k, v in n.items() if k not in ("correct", "wrong", "exec_error", "refused")}
        print(f"{Path(path).stem}: {len(cases)} final cases; correct/wrong/exec_error/refused = "
              f"{n['correct']}/{n['wrong']}/{n['exec_error']}/{n['refused']} (+{len(judge)} judge)"
              f"{'; not a verdict: ' + str(other) if other else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
