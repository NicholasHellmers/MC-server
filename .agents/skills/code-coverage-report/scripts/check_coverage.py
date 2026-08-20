#!/usr/bin/env python3
"""Coverage inspection script for evaluating pytest-cov output.

Parses coverage.json and highlights uncovered lines, branch misses,
and overall coverage percentage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_coverage_data(json_path: Path | str = "coverage.json") -> dict[str, Any]:
    """Load coverage data from a JSON report file."""
    path = Path(json_path)
    if not path.is_file():
        raise FileNotFoundError(f"Coverage file not found at: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def analyze_coverage(coverage_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze coverage summary and per-file uncovered lines.

    Returns a structured analysis with total percent, missing lines,
    and missing branch information.
    """
    totals = coverage_data.get("totals", {})
    percent_covered = totals.get("percent_covered", 0.0)
    files = coverage_data.get("files", {})

    uncovered_files: dict[str, dict[str, Any]] = {}
    for filename, file_info in files.items():
        missing_lines = file_info.get("missing_lines", [])
        missing_branches = file_info.get("missing_branches", [])
        summary = file_info.get("summary", {})
        file_pct = summary.get("percent_covered", 100.0)

        if missing_lines or missing_branches or file_pct < 100.0:
            uncovered_files[filename] = {
                "percent_covered": file_pct,
                "missing_lines": missing_lines,
                "missing_branches": missing_branches,
            }

    return {
        "percent_covered": percent_covered,
        "is_100_percent": percent_covered >= 100.0 and len(uncovered_files) == 0,
        "uncovered_files": uncovered_files,
    }


def format_coverage_report(analysis: dict[str, Any]) -> str:
    """Format analysis into a human-readable and model-consumable string."""
    pct = analysis["percent_covered"]
    if analysis["is_100_percent"]:
        return f"SUCCESS: 100% code coverage achieved across all files! (Total: {pct:.2f}%)"

    lines = [
        f"WARNING: Total Code Coverage is {pct:.2f}% (Target: 100.0%).",
        "The following files have uncovered lines or branches:",
    ]
    for filename, details in analysis["uncovered_files"].items():
        file_pct = details["percent_covered"]
        missing_lines = details["missing_lines"]
        missing_branches = details["missing_branches"]
        lines.append(f"\n- File: {filename} ({file_pct:.2f}%)")
        if missing_lines:
            lines.append(f"  Missing Lines: {missing_lines}")
        if missing_branches:
            lines.append(f"  Missing Branches: {missing_branches}")

    return "\n".join(lines)


def main() -> int:
    """CLI entrypoint for coverage verification."""
    json_file = sys.argv[1] if len(sys.argv) > 1 else "coverage.json"
    try:
        data = load_coverage_data(json_file)
        analysis = analyze_coverage(data)
        print(format_coverage_report(analysis))
        return 0 if analysis["is_100_percent"] else 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
