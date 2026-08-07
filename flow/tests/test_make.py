import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


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
