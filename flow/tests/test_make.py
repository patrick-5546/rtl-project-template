import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from flow import doctor
from flow.simulators import TIMESCALE

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


def test_linters_default_to_the_simulators_timescale() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^SV_TIMESCALE := (\S+)$", makefile, re.MULTILINE)
    assert match is not None
    assert match.group(1) == TIMESCALE


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


def verible_dry_run(project: Path) -> subprocess.CompletedProcess[str]:
    """``make --dry-run lint-sv-verible`` with the Makefile run in Git repository *project*."""
    return subprocess.run(
        [
            "make",
            "--no-print-directory",
            "-C",
            str(project),
            "-f",
            str(REPO_ROOT / "Makefile"),
            "--dry-run",
            f"SV_SOURCES_FILE={REPO_ROOT / 'rtl' / 'sources.vf'}",
            "VERIBLE_LINT=verible-lint",
            "lint-sv-verible",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_verible_checks_the_files_that_git_tracks_or_would_track(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("build/\n", encoding="utf-8")
    for name in ("rtl/a.sv", "rtl/b.svh", "rtl/gone.sv", "rtl/vendor/ip/ip.v", "build/gen.sv"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("module m;\nendmodule\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "rtl/a.sv", "rtl/gone.sv", "rtl/vendor"], cwd=tmp_path, check=True
    )
    (tmp_path / "rtl" / "gone.sv").unlink()
    result = verible_dry_run(tmp_path)
    assert result.returncode == 0, result.stderr
    lint = next(line for line in result.stdout.splitlines() if line.startswith("verible-lint "))
    assert lint.split()[1:] == ["rtl/a.sv", "rtl/b.svh"]


def test_verible_needs_a_file_to_check(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    result = verible_dry_run(tmp_path)
    assert result.returncode != 0
    assert "Verible found no SystemVerilog file" in result.stderr


def test_slang_tools_leave_out_vendor_rtl_also_through_symlinks(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    (vendor / "copied").mkdir(parents=True)
    linked = tmp_path / "elsewhere" / "linked"
    linked.mkdir(parents=True)
    (vendor / "linked").symlink_to(Path("..") / "elsewhere" / "linked")
    result = subprocess.run(
        ["make", "--dry-run", f"SV_VENDOR_DIR={vendor}", "lint-sv-slang", "lint-sv-slang-tidy"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tokens = result.stdout.split()

    def values(option: str) -> set[str]:
        return {tokens[i + 1] for i, token in enumerate(tokens[:-1]) if token == option}

    paths = [path.resolve() for path in (vendor, vendor / "copied", linked)]
    assert values("--suppress-warnings") == {f"{path}/..." for path in paths}
    # Without the trailing slash, slang-tidy would skip the parent directory too.
    assert values("--skip-path") == {f"{path}/" for path in paths}


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
