"""Re-score a finished run offline, from its runs-raw execution results.

No model call and no query execution: each attempt's candidate is rebuilt from
``$SEMDEBT_DATA_DIR/runs-raw/<source run>/<cell>/<qid>_r<rep>_t<turn>.exec.json``
(its sha256 must equal the ``exec_raw_sha256`` in the source log) and scored
against the question bank as it is now. Used when references or ``rules`` change
after a run (e.g. the rules backfill made ``no_rules`` attempts scorable).

The result goes to a *new* run directory (logs are append-only, hard rule 7):

    runs/<run-id>/<cell>.jsonl

Each line is the source line with ``run_id``, ``eval_tag``, ``eval_commit``, ``first`` and
``final`` replaced, ``cost_cny = 0`` (nothing was spent), and ``rescored_from``
holding the source run id, its eval tag and commit, and its ``first`` / ``final``.
``eval_tag`` is the tag the bank was verified against (``--eval-tag``), or null when the
bank was not checked against a tag: it never carries the source run's tag over. (Lines of
``20261018-T13-sql-direct-01-rescore-01``, written before this, carry the source's ``eval-v1.1``;
their ``eval_commit`` is the bank they were scored on, eval-v1.2. runs/INDEX.md.)
Lines of the source that are not ``status: done`` are not carried over. A line
whose ``question_sha256`` (logged since 2026-10-16) differs from the current
question text is refused: the answer belongs to a different question. Only an
explicit ``--allow-changed-question`` scores such lines anyway, against the
current references, and marks them ``question_changed: true`` so that reports
list them apart (used once: Q69 in the T12 final rescore). Logs from
before that field must be checked by hand (done for the T11 smoke run: Q02 and
Q101 have identical text, SQL and reference CSV in eval 4f13cb7 and 491ef16).
``--eval-tag`` refuses to start unless the bank is exactly that tag's content.

    uv run python -m harness.rescore --source 20261016-T11-smoke-01 --cell SQL-L1 \\
        --run-id 20261016-T11-smoke-01-rescore-01
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import run_direct as R  # noqa: E402
from harness.questions import EvalVersionError, Question, eval_commit, load_questions, verify_eval_tag  # noqa: E402
from harness.scorer_v2 import REFUSAL, ExecError  # noqa: E402


def candidate_of(turn: dict, raw_dir: Path, qid: str, rep: int):
    """The candidate the scorer saw for one turn, rebuilt from runs-raw."""
    execution = turn["exec"]
    if execution.get("status") == "refused":
        return REFUSAL
    if execution.get("error_class") == R.NO_QUERY:
        return ExecError("no query code block in the response")
    path = raw_dir / f"{qid}_r{rep}_t{turn['turn']}.exec.json"
    data = path.read_bytes()
    if R.sha256(data) != execution.get("exec_raw_sha256"):
        raise ValueError(f"{path}: sha256 does not match the source log")
    payload = json.loads(data)
    if payload["error"] is not None:
        return ExecError(payload["error"] or "execution error")
    return payload["rows"]


def rescore_line(rec: dict, q: Question, raw_dir: Path, run_id: str, commit: str,
                 allow_changed: bool = False, eval_tag: str | None = None) -> dict:
    changed = "question_sha256" in rec and rec["question_sha256"] != R.sha256(q.text)
    if changed and not allow_changed:
        raise ValueError(f"{rec['qid']}: the question text changed since run {rec['run_id']}; "
                         "its answers cannot be re-scored against the current question")
    turns = rec["turns"]
    first = candidate_of(turns[0], raw_dir, rec["qid"], rec["rep"])
    last = candidate_of(turns[-1], raw_dir, rec["qid"], rec["rep"])
    last_exec = turns[-1]["exec"]
    out = {
        **rec,
        "run_id": run_id,
        "eval_tag": eval_tag,
        "eval_commit": commit,
        "first": R.score_question(first, q)["outcome"],
        "final": R.final_score(last, q, last_exec.get("error_class"), last_exec.get("limit")),
        "cost_cny": 0.0,
        "rescored_from": {"run_id": rec["run_id"], "eval_tag": rec.get("eval_tag"), "eval_commit": rec["eval_commit"],
                          "first": rec["first"], "final": rec["final"],
                          "rescored_at": datetime.now(R.BEIJING).isoformat(timespec="seconds"),
                          "harness_commit": R.harness_commit()},
    }
    if changed:
        out["question_changed"] = True         # answered an older wording; report apart
    return out


def rescore(source: str, cell: str, run_id: str, runs_root: Path | None = None, raw_root: Path | None = None,
            questions: dict[str, Question] | None = None, commit: str | None = None,
            allow_changed: bool = False, eval_tag: str | None = None) -> Path:
    """``eval_tag``: the tag the bank was verified against (recorded in every line), or None."""
    src = R.log_path(source, cell, runs_root)
    dst = R.log_path(run_id, cell, runs_root)
    if dst.exists():
        raise SystemExit(f"{dst} exists; logs are append-only, choose a new run id")
    lang = R.CELLS[cell].lang
    questions = questions or {q.qid: q for q in load_questions(lang=lang)}
    commit = commit or eval_commit()
    raw_dir = (raw_root or R.raw_root()) / source / cell
    lines = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = [rescore_line(rec, questions[rec["qid"]], raw_dir, run_id, commit, allow_changed, eval_tag)
           for rec in lines if rec.get("status") == "done"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("x", encoding="utf-8") as fh:
        for rec in out:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return dst


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="run id to re-score")
    ap.add_argument("--cell", required=True)
    ap.add_argument("--run-id", required=True, help="new run id (a new directory under runs/)")
    ap.add_argument("--eval-tag", help="refuse to start unless the bank is exactly this tag's content")
    ap.add_argument("--allow-changed-question", action="store_true",
                    help="score lines whose question text changed since the source run "
                         "(marked question_changed); off by default")
    args = ap.parse_args(argv)
    if args.eval_tag:
        try:
            print(f"question bank: {args.eval_tag} = {verify_eval_tag(args.eval_tag)[:7]}")
        except EvalVersionError as exc:
            print(f"refusing to start: {exc}", file=sys.stderr)
            return 2
    path = rescore(args.source, args.cell, args.run_id, allow_changed=args.allow_changed_question,
                   eval_tag=args.eval_tag)
    for rec in map(json.loads, path.read_text(encoding="utf-8").splitlines()):
        mark = "  (question changed)" if rec.get("question_changed") else ""
        print(f"{rec['qid']} r{rec['rep']}: {rec['rescored_from']['final']['outcome']} -> {rec['final']['outcome']}{mark}")
    print(json.dumps(R.summarize(path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
