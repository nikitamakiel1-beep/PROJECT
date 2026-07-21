#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence.neural_crm.bridge import NeuralProviderBridge  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run governed neural CRM shadow inference on a PII-free provider package.")
    parser.add_argument("input", nargs="?", help="JSON package path; omit or use '-' for stdin")
    parser.add_argument("--output", help="Optional output JSON path; stdout when omitted")
    args = parser.parse_args()

    if not args.input or args.input == "-":
        package = json.load(sys.stdin)
    else:
        package = json.loads(Path(args.input).read_text(encoding="utf-8"))

    decision = NeuralProviderBridge().infer(package)
    rendered = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
