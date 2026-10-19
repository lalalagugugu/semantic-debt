"""What of an execution error may reach ``reports/`` (scorer spec v2 §13, 连带).

An ``exec_error`` verdict carries the engine's message as its reason, and that message can
quote the query (SQL fragments, identifiers, literals). Anything written to ``reports/``
keeps only the error class and a hash of the message; the message itself stays in runs-raw.
``runs/`` logs follow their own rule (hard rule 7: the log keeps hashes, runs-raw the rest).
"""

from __future__ import annotations

import hashlib
import re

# Signatures of a raw engine message (ClickHouse / chDB): a report must never contain these.
RAW_ENGINE_MESSAGE = re.compile(r"DB::Exception|\bCode: \d+\.")


def exec_error_ref(message: str, error_class: str | None = None) -> str:
    """``<error class> · sha256:<first 16 hex of the message>``; the class defaults to
    ``execution_failed`` when the log has none."""
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
    return f"{error_class or 'execution_failed'} · sha256:{digest}"


def report_reason(outcome: str, reason: str | None, error_class: str | None = None) -> str | None:
    """A scorer reason as it may appear in a report: redacted for ``exec_error``, as is otherwise."""
    if outcome == "exec_error" and reason is not None:
        return exec_error_ref(reason, error_class)
    return reason
