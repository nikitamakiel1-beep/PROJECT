#!/usr/bin/env python3
"""Build the complete synthetic-only website preview artifact."""
from __future__ import annotations

import argparse
from pathlib import Path

from build_web_release import build

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "web-preview")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    info = build(output.resolve(), profile="preview", endpoint="", evidence={})
    print(f"preview build passed: {output} ({info['route_count']} routes)")


if __name__ == "__main__":
    main()
