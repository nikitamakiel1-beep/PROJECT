#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.venture_brain.pre_client_readiness import audit_pre_client_readiness  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit pre-client website and CRM readiness.")
    parser.add_argument("--crm-snapshot", type=Path)
    parser.add_argument("--activation-evidence", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "pre-client-readiness.json")
    args = parser.parse_args()

    crm_snapshot = json.loads(args.crm_snapshot.read_text(encoding="utf-8")) if args.crm_snapshot else None
    activation = json.loads(args.activation_evidence.read_text(encoding="utf-8")) if args.activation_evidence else None
    report = audit_pre_client_readiness(ROOT, crm_snapshot=crm_snapshot, activation_evidence=activation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": report["states"]["source_ready"],
        "source_completion_pct": report["source_completion_pct"],
        "states": report["states"],
        "output": str(args.output),
        "report_sha256": report["report_sha256"],
    }, indent=2))
    if not report["states"]["source_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
