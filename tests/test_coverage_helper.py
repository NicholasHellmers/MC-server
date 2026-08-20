"""Tests for the code coverage analyzer script."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Import directly from script
sys_path_entry = str(Path(__file__).resolve().parent.parent / ".agents" / "skills" / "code-coverage-report" / "scripts")
import sys
if sys_path_entry not in sys.path:
    sys.path.insert(0, sys_path_entry)

from check_coverage import analyze_coverage, format_coverage_report, load_coverage_data, main


def test_load_coverage_data(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_coverage_data(tmp_path / "missing.json")

    valid_json = tmp_path / "coverage.json"
    valid_json.write_text(json.dumps({"totals": {"percent_covered": 100.0}}), encoding="utf-8")
    data = load_coverage_data(valid_json)
    assert data["totals"]["percent_covered"] == 100.0


def test_analyze_coverage():
    # 100% case
    data_100 = {
        "totals": {"percent_covered": 100.0},
        "files": {
            "src/mod.py": {"missing_lines": [], "missing_branches": [], "summary": {"percent_covered": 100.0}}
        },
    }
    res_100 = analyze_coverage(data_100)
    assert res_100["is_100_percent"] is True
    report_100 = format_coverage_report(res_100)
    assert "SUCCESS" in report_100

    # Incomplete coverage case
    data_partial = {
        "totals": {"percent_covered": 95.0},
        "files": {
            "src/mod.py": {"missing_lines": [10, 11], "missing_branches": [[20, 25]], "summary": {"percent_covered": 90.0}}
        },
    }
    res_partial = analyze_coverage(data_partial)
    assert res_partial["is_100_percent"] is False
    report_partial = format_coverage_report(res_partial)
    assert "WARNING" in report_partial
    assert "Missing Lines: [10, 11]" in report_partial


def test_main_cli(tmp_path: Path):
    cov_file = tmp_path / "coverage.json"
    cov_file.write_text(json.dumps({
        "totals": {"percent_covered": 100.0},
        "files": {}
    }), encoding="utf-8")

    with patch("sys.argv", ["check_coverage", str(cov_file)]):
        assert main() == 0

    cov_file_fail = tmp_path / "coverage_fail.json"
    cov_file_fail.write_text(json.dumps({
        "totals": {"percent_covered": 80.0},
        "files": {"src/a.py": {"missing_lines": [1], "missing_branches": [], "summary": {"percent_covered": 80.0}}}
    }), encoding="utf-8")

    with patch("sys.argv", ["check_coverage", str(cov_file_fail)]):
        assert main() == 1

    with patch("sys.argv", ["check_coverage", str(tmp_path / "nonexistent.json")]):
        assert main() == 2
