from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI = _REPO_ROOT / "scripts" / "nexus_cli.py"


def _run_cli(
    cwd: Path, db: Path, *args: str, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NEXUS_LLM_PROVIDER"] = "stub"
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(_REPO_ROOT), env.get("PYTHONPATH", ""))))
    return subprocess.run(
        [sys.executable, str(_CLI), "--db", str(db), *args],
        cwd=cwd,
        env=env,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _event_count(db: Path, event_type: str) -> int:
    with closing(sqlite3.connect(db)) as conn:
        return int(
            conn.execute("SELECT COUNT(*) FROM events WHERE type = ?", (event_type,)).fetchone()[0]
        )


def test_cli_pause_discover_resume_and_replay_in_fresh_processes(tmp_path: Path) -> None:
    db = tmp_path / "nexus.sqlite"
    submitted = _run_cli(tmp_path, db, "--once", "commit changes to this repository")
    assert submitted.returncode == 0, submitted.stderr
    assert "status: paused" in submitted.stdout
    assert "approval left pending" in submitted.stdout
    session = re.search(r"session: (cli-[a-f0-9]+)", submitted.stdout)
    assert session is not None
    identity = session.group(1)
    artifact_dir = tmp_path / ".nexus_llm_artifacts"
    assert not artifact_dir.exists() or not tuple(artifact_dir.iterdir())
    assert _event_count(db, "runtime.artifact_emitted") == 0

    pending = _run_cli(tmp_path, db, "--pending")
    assert pending.returncode == 0, pending.stderr
    assert identity in pending.stdout

    resumed = _run_cli(tmp_path, db, "--resume", identity, input_text="y\n")
    assert resumed.returncode == 0, resumed.stderr
    assert "pipeline status: completed" in resumed.stdout
    assert "[stub reasoning over" in resumed.stdout
    assert artifact_dir.exists()
    answers = tuple(artifact_dir.glob("*-response.md"))
    assert len(answers) == 1 and answers[0].read_text(encoding="utf-8").strip()
    artifacts_emitted = _event_count(db, "runtime.artifact_emitted")
    dispatches = _event_count(db, "runtime.started")
    responses_recorded = _event_count(db, "interaction.response_recorded")
    assert artifacts_emitted == 2
    assert dispatches == 1
    assert responses_recorded == 3

    replay = _run_cli(tmp_path, db, "--resume", identity)
    assert replay.returncode == 0, replay.stderr
    assert "status: completed" in replay.stdout
    assert "[stub reasoning over" in replay.stdout
    assert _event_count(db, "runtime.artifact_emitted") == artifacts_emitted
    assert _event_count(db, "runtime.started") == dispatches
    assert _event_count(db, "interaction.response_recorded") == responses_recorded


def test_cli_denial_keeps_artifact_absent(tmp_path: Path) -> None:
    db = tmp_path / "denied.sqlite"
    submitted = _run_cli(tmp_path, db, "--once", "commit changes to this repository")
    assert submitted.returncode == 0, submitted.stderr
    session = re.search(r"session: (cli-[a-f0-9]+)", submitted.stdout)
    assert session is not None

    denied = _run_cli(tmp_path, db, "--resume", session.group(1), input_text="n\n")
    assert denied.returncode == 0, denied.stderr
    assert "will never execute" in denied.stdout
    assert _event_count(db, "runtime.artifact_emitted") == 0
    assert _event_count(db, "runtime.started") == 0
    artifact_dir = tmp_path / ".nexus_llm_artifacts"
    assert not artifact_dir.exists() or not tuple(artifact_dir.iterdir())


def test_cli_plan_inspect_then_resume_in_fresh_processes(tmp_path: Path) -> None:
    db = tmp_path / "plan.sqlite"
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "README.md").write_text("# Small repository\n", encoding="utf-8")
    (repository / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")

    planned = _run_cli(
        tmp_path,
        db,
        "--plan",
        "Update the CLI: first implement a --version option, then add a focused test for it.",
        "--repository-root",
        str(repository),
    )
    assert planned.returncode == 0, planned.stderr
    assert "plan paused before actuation" in planned.stdout
    assert "source refs:" in planned.stdout
    assert "assumptions:" in planned.stdout
    assert planned.stdout.count("  work item ") == 2
    assert "dependency:" in planned.stdout
    session = re.search(r"session: (cli-[a-f0-9]+)", planned.stdout)
    assert session is not None
    identity = session.group(1)
    assert _event_count(db, "runtime.started") == 0
    assert _event_count(db, "runtime.artifact_emitted") == 0

    resumed = _run_cli(tmp_path, db, "--resume", identity)
    assert resumed.returncode == 0, resumed.stderr
    assert "status: completed" in resumed.stdout
    dispatches = _event_count(db, "runtime.started")
    artifacts = _event_count(db, "runtime.artifact_emitted")
    assert dispatches == 2

    replay = _run_cli(tmp_path, db, "--resume", identity)
    assert replay.returncode == 0, replay.stderr
    assert "status: completed" in replay.stdout
    assert _event_count(db, "runtime.started") == dispatches
    assert _event_count(db, "runtime.artifact_emitted") == artifacts


def test_cli_ambiguous_plan_requests_clarification_without_resume_instruction(
    tmp_path: Path,
) -> None:
    db = tmp_path / "ambiguous.sqlite"
    repository = tmp_path / "repo"
    repository.mkdir()
    planned = _run_cli(
        tmp_path,
        db,
        "--plan",
        "Fix the CLI.",
        "--repository-root",
        str(repository),
    )
    assert planned.returncode == 0, planned.stderr
    assert "nexus needs clarification:" in planned.stdout
    assert "clarification required before a plan can be resumed" in planned.stdout
    assert "plan paused before actuation" not in planned.stdout
    assert "run --resume" not in planned.stdout
    assert _event_count(db, "runtime.started") == 0
