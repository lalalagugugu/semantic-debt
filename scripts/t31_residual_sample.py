"""Draw the stratified sample of T31 residual attempts for content-correctness review.

Frame: the 2,081 attempts in ``t31-final-review-list-strict.json`` (v2 wrong, with a result,
not credited by the T31 rules), restricted to the runs reported in the midterm report and to
the 98 main-table questions. Strata = reported cell. Each stratum gets at least MIN_PER
attempts; the rest of TOTAL is allocated in proportion to stratum size (largest remainder).

Usage:
    python3 scripts/t31_residual_sample.py <t31-final-review-list-strict.json> <out_dir>

Writes ``t31-residual-sample.csv`` (ids only, no question text) and ``t31-residual-frame.csv``
(frame size per stratum, needed to weight estimates).
"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

SEED = 20261028
TOTAL = 200
MIN_PER = 6

# Reported runs only: pilots (T12, T15 pilot, T16 pilot, T21, T29 pilot) and the superseded
# SQL-L1.5S semantic-v1.2 run are left out. SQL-L2-E is one cell over two run ids.
STRATA = {
    ("20261018-T13-sql-direct-01", "SQL-L0"): "SQL-L0",
    ("20261018-T13-sql-direct-01", "SQL-R"): "SQL-R",
    ("20261018-T13-sql-direct-01", "SQL-L1"): "SQL-L1",
    ("20261018-T13-sql-direct-01", "SQL-L1c"): "SQL-L1c",
    ("20261018-T13-sql-direct-01", "SQL-L1.5W"): "SQL-L1.5W",
    ("20261019-T13-l15s-v14-01", "SQL-L1.5S"): "SQL-L1.5S",
    ("20261019-C13-ladder-02", "SQL-L1-T2"): "SQL-L1-T2",
    ("20261019-C13-ladder-02", "SQL-L1-T3"): "SQL-L1-T3",
    ("20261019-C13-ladder-02", "SQL-L1-T4"): "SQL-L1-T4",
    ("20261019-T15-explorer-01", "SQL-L0-E"): "SQL-L0-E",
    ("20261019-T15-explorer-01", "SQL-L1-E"): "SQL-L1-E",
    ("20261020-T15-explorer-l2e-02", "SQL-L2-E"): "SQL-L2-E",
    ("20261020-T15-explorer-l2e-03", "SQL-L2-E"): "SQL-L2-E",
    ("20261019-T16-full-v14-sql-new-01", "SQL-L2"): "SQL-L2",
    ("20261019-T16-full-v14-json-01", "JSON-L2"): "JSON-L2",
    ("20261025-T14-tuned-01", "SQL-L1-tuned"): "SQL-L1-tuned",
    ("20261025-T14-tuned-01", "SQL-L1-tuned-instr"): "SQL-L1-tuned-instr",
    ("20261025-T22b-l1plus-l3a-03", "SQL-L1plus"): "SQL-L1plus",
    ("20261025-T22b-l1plus-l3a-03", "SQL-L3a"): "SQL-L3a",
    ("20261025-T30-combo-01", "SQL-L1plus-tuned-instr"): "SQL-L1plus-tuned-instr",
}

# decisions/2026-10-16-low-discrimination-criteria.md; excluded from the 98-question main table.
LOW_DISCRIMINATION = {"Q07", "Q17", "Q29", "Q59", "Q68", "Q69", "Q76", "Q79", "Q83", "Q85", "Q99"}


def allocate(sizes: dict[str, int]) -> dict[str, int]:
    alloc = {s: min(MIN_PER, n) for s, n in sizes.items()}
    rest = TOTAL - sum(alloc.values())
    spare = {s: n - alloc[s] for s, n in sizes.items()}
    pool = sum(spare.values())
    quotas = {s: rest * spare[s] / pool for s in sizes}
    for s in sizes:
        alloc[s] += int(quotas[s])
    left = TOTAL - sum(alloc.values())
    for s in sorted(sizes, key=lambda s: (-(quotas[s] - int(quotas[s])), s))[:left]:
        alloc[s] += 1
    return alloc


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = json.loads(src.read_text(encoding="utf-8"))["ready_for_later_authorization"]
    if len(rows) != 2081:
        raise SystemExit(f"expected 2,081 residual attempts, got {len(rows)}")
    frame = defaultdict(list)
    for r in rows:
        stratum = STRATA.get((r["source_run"], r["cell"]))
        if stratum and r["qid"] not in LOW_DISCRIMINATION:
            frame[stratum].append((r["source_run"], r["cell"], r["qid"], r["rep"]))
    sizes = {s: len(v) for s, v in sorted(frame.items())}
    alloc = allocate(sizes)
    rng = random.Random(SEED)
    picked = []
    for s in sorted(frame):
        units = sorted(frame[s], key=lambda u: (u[0], int(u[2][1:]), u[3]))
        picked += [(s, *u) for u in sorted(rng.sample(units, alloc[s]), key=lambda u: (u[0], int(u[2][1:]), u[3]))]
    out.mkdir(parents=True, exist_ok=True)
    with (out / "t31-residual-sample.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["stratum", "source_run", "cell", "qid", "rep"])
        w.writerows(picked)
    with (out / "t31-residual-frame.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["stratum", "frame_attempts", "sampled"])
        w.writerows((s, sizes[s], alloc[s]) for s in sizes)
    print(f"frame {sum(sizes.values())} attempts in {len(sizes)} strata; sampled {len(picked)}")


if __name__ == "__main__":
    main()
