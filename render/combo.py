"""T30: remove preregistered item IDs without serializing retained YAML."""
from __future__ import annotations

import yaml

from render.common import SEMANTIC

EXCLUDED = frozenset({"E01", "E02", "E03", "E05", "E07", "E08", "E09", "E10", "E13", "S11", "S14", "R6"})
SOURCE = SEMANTIC / "tuning/SQL-L1.yaml"
TARGET = SEMANTIC / "tuning/SQL-L1.combo.yaml"


def item_spans(raw: bytes) -> dict[str, tuple[int, int]]:
    text = raw.decode("utf-8")
    root = yaml.compose(text)
    spans = {}
    for key, sequence in root.value:
        if key.value not in {"semantics", "rewrites", "examples"}:
            continue
        for index, item in enumerate(sequence.value, 1):
            fields = {k.value: v.value for k, v in item.value}
            ident = f"R{index}" if key.value == "rewrites" else fields["id"]
            # Include the sequence dash and its indentation, preserving everything else.
            start = text.rfind("\n", 0, item.start_mark.index) + 1
            end = item.end_mark.index
            line_start = text.rfind("\n", 0, end) + 1
            if not text[line_start:end].strip():
                end = line_start
            spans[ident] = (len(text[:start].encode("utf-8")), len(text[:end].encode("utf-8")))
    return spans


def filtered(raw: bytes) -> bytes:
    spans = item_spans(raw)
    if not EXCLUDED <= spans.keys():
        raise ValueError("Missing preregistered tuning IDs")
    for start, end in sorted((spans[i] for i in EXCLUDED), reverse=True):
        raw = raw[:start] + raw[end:]
    yaml.safe_load(raw)
    return raw


def main() -> None:
    TARGET.write_bytes(filtered(SOURCE.read_bytes()))


if __name__ == "__main__":
    main()
