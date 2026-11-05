import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from flow import doctor

REPO_ROOT = Path(__file__).resolve().parents[2]


def phony_targets() -> list[str]:
    """The targets that the Makefile's ``.PHONY`` declaration lists."""
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8").replace("\\\n", " ")
    match = re.search(r"^\.PHONY:(.*)$", text, re.MULTILINE)
    assert match is not None
    return match.group(1).split()


def help_names() -> set[str]:
    """The names that ``make help``'s entries document, not its headings or descriptions.

    An entry is an indented line: its names, then optionally two spaces and a
    capitalized description. ``lint-<py|sv>`` stands for ``lint-py`` and ``lint-sv``.
    """
    output = subprocess.run(
        ["make", "--no-print-directory", "help"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    def spell_out(match: re.Match[str]) -> str:
        prefix, alternatives, suffix = match.groups()
        return " ".join(f"{prefix}{word}{suffix}" for word in alternatives.split("|"))

    names: set[str] = set()
    for line in output.splitlines():
        if line.startswith("  "):
            entry = re.split(r"\s{2,}(?=[A-Z][a-z])", line.strip(), maxsplit=1)[0]
            names.update(re.findall(r"[\w-]+", re.sub(r"(\S*?)<([\w|-]+)>(\S*)", spell_out, entry)))
    return names


def test_help_lists_every_target_and_variable() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    flags = re.findall(r"^(ENABLE_\w+) \?=", makefile, re.MULTILINE)
    executables = [
        tool.variable for group in doctor.GROUPS for tool in group.tools if tool.variable
    ]
    assert sorted({*phony_targets(), *flags, *executables} - help_names()) == []


def test_make_variables_are_defined() -> None:
    result = subprocess.run(
        ["make", "--dry-run", "--warn-undefined-variables", *phony_targets()],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "undefined variable" not in result.stderr


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
    ("contents", "message"),
    [(None, "does not resolve to a file"), ("# no files\n\n", "lists no files")],
)
def test_verible_list_must_name_files(
    tmp_path: Path,
    contents: str | None,
    message: str,
) -> None:
    verible_list = tmp_path / "verible.vf"
    if contents is not None:
        verible_list.write_text(contents, encoding="utf-8")
    result = subprocess.run(
        ["make", "--dry-run", f"SV_VERIBLE_FILE={verible_list}", "lint-sv-verible"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert message in result.stderr


def test_waves_opens_the_viewer_after_a_failed_test(tmp_path: Path) -> None:
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
            "waves",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "COMMAND_LOG": str(command_log)},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert command_log.read_text().splitlines() == ["validate-config", "test", "open-waves"]


@pytest.mark.parametrize(
    ("test_status", "report_status", "expected_error"),
    [(7, 9, 7), (0, 9, 9), (0, 0, None)],
)
def test_coverage_reports_after_a_failed_test_and_keeps_its_status(
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
            "DUT=all",
            "coverage",
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
    assert command_log.read_text().splitlines() == ["test", "report-coverage"]
