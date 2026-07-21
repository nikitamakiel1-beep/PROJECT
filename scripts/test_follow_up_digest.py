#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "scripts" / "follow_up_digest_harness.js"


def main() -> None:
    completed = subprocess.run(["node", str(HARNESS)], cwd=ROOT, capture_output=True, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.stderr or completed.stdout or "A02 digest harness failed")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"A02 digest harness returned invalid JSON: {exc}") from exc
    tests = result.get("tests", [])
    if result.get("ok") is not True or len(tests) != 6 or any(item.get("result") != "passed" for item in tests):
        raise SystemExit(f"A02 digest validation failed: {result}")
    print("follow-up digest validation passed (6 synthetic cases)")


if __name__ == "__main__":
    main()
