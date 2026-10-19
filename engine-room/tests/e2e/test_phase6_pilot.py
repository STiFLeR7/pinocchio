from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "scripts" / "phase6_pilot.py"


def test_phase6_rehearsal_runs_all_frozen_cases_and_keeps_human_gate_open(tmp_path: Path) -> None:
    report_path = tmp_path / "phase6-rehearsal.json"
    result = subprocess.run(
        [sys.executable, str(PILOT), "rehearse", "--output", str(report_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["evidence_kind"] == "automated_rehearsal"
    assert report["human_pilot"] is False
    assert report["release_gate_complete"] is False
    assert report["release_gate_status"] == "rehearsal_only"
    assert [case["actual_node_verdicts"] for case in report["cases"]] == [
        ["passed", "passed"],
        ["passed", "passed"],
        ["passed", "passed"],
        ["failed", "failed"],
        ["passed", "requires_review"],
    ]
    assert report["checks"]["all_expected_verdicts"] is True
    assert report["checks"]["zero_unauthorized_actions"] is True
    assert report["checks"]["zero_false_passed"] is True
    assert report["checks"]["five_complete_lineages"] is True
    assert report["checks"]["plan_conditions_frozen_before_approval"] is True
    assert report["checks"]["zero_action_starts_before_approval"] is True
    assert report["checks"]["exactly_two_action_starts_each"] is True
    assert report["checks"]["replay_no_new_events"] is True
    assert report["checks"]["replay_no_duplicate_work_or_verdicts"] is True
    assert report["backup_restore"]["artifact_hashes_valid"] is True
    assert report["backup_restore"]["rollback_pair_preserved"] is True
    assert report["human_assessments"] == {"useful": 0, "not_useful": 0, "missing": 5}
    assert all(case["action_starts"] == 2 for case in report["cases"])
    assert all(case["lineage_complete"] for case in report["cases"])
    assert all(case["plan_review"]["proposed_diff"] for case in report["cases"])

    text = report_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in text
    assert re.search(r"[A-Z]:\\", text) is None
    assert "SIMULATED_REHEARSAL_OPERATOR" in text
