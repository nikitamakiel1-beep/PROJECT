"""Stable public API for Stage 010r synthetic reconciliation."""
from __future__ import annotations

from . import reconciliation as _runtime

# Quarantine receipts contain several reference IDs; this explicitly selects the
# deterministic receipt identity rather than relying on generic ID inference.
_runtime.ID_FIELDS["Quarantines"] = "Quarantine ID"

SyntheticReconciliationError = _runtime.SyntheticReconciliationError
apply_mutation_plan = _runtime.apply_mutation_plan
build_mutation_plan = _runtime.build_mutation_plan
build_snapshot = _runtime.build_snapshot
compare_reconciliation_bundles = _runtime.compare_reconciliation_bundles
compare_snapshots = _runtime.compare_snapshots
export_reconciliation_bundle = _runtime.export_reconciliation_bundle
invert_mutation_plan = _runtime.invert_mutation_plan
load_reconciliation_bundle = _runtime.load_reconciliation_bundle
render_diff_markdown = _runtime.render_diff_markdown
snapshot_from_batch_result = _runtime.snapshot_from_batch_result
validate_snapshot = _runtime.validate_snapshot
verify_rollback = _runtime.verify_rollback

__all__ = [
    "SyntheticReconciliationError",
    "apply_mutation_plan",
    "build_mutation_plan",
    "build_snapshot",
    "compare_reconciliation_bundles",
    "compare_snapshots",
    "export_reconciliation_bundle",
    "invert_mutation_plan",
    "load_reconciliation_bundle",
    "render_diff_markdown",
    "snapshot_from_batch_result",
    "validate_snapshot",
    "verify_rollback",
]
