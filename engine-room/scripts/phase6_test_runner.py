"""Fixed, allow-listed fixture test runner for the Phase 6 disposable workspaces."""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

import pytest


def main() -> int:
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    no_report = "--no-report" in sys.argv[1:]
    report = Path("reports/phase6-junit.xml")
    if not no_report:
        report.parent.mkdir(parents=True, exist_ok=True)
    arguments = ["-q", "-p", "no:cacheprovider", "tests/test_repair.py"]
    if not no_report:
        arguments.append(f"--junitxml={report.as_posix()}")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = pytest.main(arguments)
    if report.exists() and not no_report:
        sys.stdout.write(report.read_text(encoding="utf-8"))
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
