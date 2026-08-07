import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_project_root_cannot_be_overridden() -> None:
    result = subprocess.run(
        [
            "make",
            "--no-print-directory",
            "--silent",
            "PROJECT_ROOT=/wrong",
            "--eval",
            'print-project-root:;@printf "%s" "$$PROJECT_ROOT"',
            "print-project-root",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == str(REPO_ROOT)


@pytest.mark.parametrize(
    ("target", "postprocess"),
    [("coverage", "report-coverage"), ("waves", "open-waves")],
)
def test_artifact_target_postprocesses_failed_test(
    tmp_path: Path,
    target: str,
    postprocess: str,
) -> None:
    command_log = tmp_path / "commands.txt"
    fake_cli = tmp_path / "fake_cli.py"
    fake_cli.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import sys\n"
        "with Path(os.environ['COMMAND_LOG']).open('a') as stream:\n"
        "    stream.write(sys.argv[1] + '\\n')\n"
        "raise SystemExit(1 if sys.argv[1] == 'test' else 0)\n"
    )
    result = subprocess.run(
        [
            "make",
            "--no-print-directory",
            f"FLOW={sys.executable} {fake_cli}",
            "CONFIG=width4",
            target,
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "COMMAND_LOG": str(command_log)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert command_log.read_text().splitlines() == [
        "validate-config",
        "test",
        postprocess,
    ]


@pytest.mark.parametrize(
    ("test_status", "report_status", "expected_error"),
    [(7, 9, 7), (0, 9, 9), (0, 0, None)],
)
def test_coverage_all_status_and_report_attempts(
    tmp_path: Path,
    test_status: int,
    report_status: int,
    expected_error: int | None,
) -> None:
    command_log = tmp_path / "commands.txt"
    fake_cli = tmp_path / "fake_cli.py"
    fake_cli.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import sys\n"
        "action = sys.argv[1]\n"
        "with Path(os.environ['COMMAND_LOG']).open('a') as stream:\n"
        "    stream.write(action + '\\n')\n"
        "status_name = 'TEST_STATUS' if action == 'test' else 'REPORT_STATUS'\n"
        "raise SystemExit(int(os.environ[status_name]))\n"
    )
    result = subprocess.run(
        [
            "make",
            "--no-print-directory",
            f"FLOW={sys.executable} {fake_cli}",
            "coverage-all",
        ],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "COMMAND_LOG": str(command_log),
            "TEST_STATUS": str(test_status),
            "REPORT_STATUS": str(report_status),
        },
        check=False,
        capture_output=True,
        text=True,
    )
    assert (result.returncode != 0) is (expected_error is not None)
    if expected_error is not None:
        assert f"Error {expected_error}" in result.stderr
    assert command_log.read_text().splitlines() == ["test", "report-coverage-all"]
