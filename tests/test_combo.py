"""T30 mechanical filtering and frozen system-message regression."""
import copy
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness import cells, run_direct
from render import combo, context
from render.common import REPO, dump_yaml


def test_filter_is_lossless():
    raw = combo.SOURCE.read_bytes()
    result = combo.filtered(raw)
    assert combo.TARGET.read_bytes() == result
    before, after = yaml.safe_load(raw), yaml.safe_load(result)
    expected = copy.deepcopy(before)
    for section in ("semantics", "examples"):
        expected[section] = [x for x in before[section] if x["id"] not in combo.EXCLUDED]
    expected["rewrites"] = [x for i, x in enumerate(before["rewrites"], 1) if f"R{i}" not in combo.EXCLUDED]
    assert after == expected
    original_spans = combo.item_spans(raw)
    # Rewrite IDs are positional; compare their complete byte slices in order.
    for section in ("semantics", "examples", "rewrites"):
        prefix = {"semantics": "S", "examples": "E", "rewrites": "R"}[section]
        retained = [raw[a:b] for ident, (a, b) in original_spans.items()
                    if ident.startswith(prefix) and ident not in combo.EXCLUDED]
        actual = [result[a:b] for ident, (a, b) in combo.item_spans(result).items() if ident.startswith(prefix)]
        assert retained == actual


def test_frozen_systems_and_combo(tmp_path, monkeypatch):
    old_source = subprocess.run(["git", "show", "3e577498358c0ff97c137f5801666b9922bb2122:render/context.py"], cwd=REPO,
                                capture_output=True, text=True, check=True).stdout
    ns = {"__name__": "render._before_combo", "__package__": "render"}
    exec(compile(old_source, "before-combo", "exec"), ns)
    monkeypatch.setattr(run_direct, "CONTEXTS", tmp_path)
    for name, cell in (("SQL-L1plus", cells.L1PLUS_CELLS["SQL-L1plus"]),
                       ("SQL-L1-tuned", cells.CELLS["SQL-L1-tuned-instr"])):
        path = tmp_path / f"{name}.yaml"
        path.write_text(dump_yaml(ns["render_cell"](name)), encoding="utf-8")
        old = run_direct.system_for(cell)
        path.write_text(dump_yaml(context.render_cell(name)), encoding="utf-8")
        assert run_direct.system_for(cell) == old
    rendered = context.render_cell("SQL-L1plus-tuned-instr")
    tuning = rendered.pop("tuning")
    assert rendered == context.render_cell("SQL-L1plus")
    assert len(tuning["examples"]) == 5
    assert len(tuning["semantics"]) == 17
    assert len(tuning["rewrites"]) == 6
    cell = cells.COMBO_CELLS["SQL-L1plus-tuned-instr"]
    assert cell.instructions == "SQL-L1" and cell.skip_judge and cell.card == "T30"
    assert not cells.COMBO_CELLS.keys() & cells.CELLS.keys()
