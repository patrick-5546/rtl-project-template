import re
import shlex
from importlib.resources import files
from pathlib import Path

import pytest

from flow import doctor
from flow.doctor import GROUPS, Tool, check, ci_pins, mise_pins, numbers, report
from flow.simulators import VerilatorProfile

VERILATOR = Tool(
    "verilator",
    "VERILATOR",
    pin="VERILATOR_VERSION",
    minimum=VerilatorProfile.minimum_version,
    minimum_for="the flow",
)
VERIBLE = Tool("verible-verilog-format", mise="github:chipsalliance/verible", exact=True)
GENHTML = Tool("genhtml", "GENHTML", mise="github:linux-test-project/lcov")
PINS = {
    "VERILATOR_VERSION": "5.054",
    "github:chipsalliance/verible": "0.0-4298-g085eef05",
    "github:linux-test-project/lcov": "2.6",
}
# What genhtml prints without its Perl modules: a version in it is not genhtml's.
PERL_ERROR = "Can't locate DateTime.pm in @INC (@INC entries checked: /usr/lib/perl/5.40.1)"


@pytest.fixture
def bin_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty directory that is all of ``PATH``, with no tool variables set."""
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", str(directory))
    for group in GROUPS:
        for tool in group.tools:
            if tool.variable:
                monkeypatch.delenv(tool.variable, raising=False)
    return directory


def fake_tool(directory: Path, name: str, output: str = "", status: int = 0) -> Path:
    """Write executable *directory*/*name*, which prints *output* and exits with *status*."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        f"#!/bin/sh\nprintf '%s\\n' {shlex.quote(output)}\nexit {status}\n", encoding="utf-8"
    )
    path.chmod(0o755)
    return path


def test_ci_pins_reads_literal_versions(tmp_path: Path) -> None:
    workflow = tmp_path / "ci.yml"
    workflow.write_text(
        "env:\n"
        '  UV_LOCKED: "1"\n'
        "  VERILATOR_VERSION: v5.054\n"
        '  SLANG_VERSION: "v12.1"\n'
        "jobs:\n"
        "  rtl:\n"
        "    env:\n"
        "      VERILATOR_VERSION: ${{ env.VERILATOR_VERSION }}\n",
        encoding="utf-8",
    )
    assert ci_pins(workflow) == {"VERILATOR_VERSION": "5.054", "SLANG_VERSION": "12.1"}
    assert ci_pins(tmp_path / "missing.yml") == {}


def test_mise_pins_reads_versions(tmp_path: Path) -> None:
    config = tmp_path / "mise.toml"
    config.write_text(
        "[tools]\n"
        'uv = "0.13.7"\n'
        '"github:chipsalliance/verible" = "v0.0-4298-g085eef05"\n'
        '"github:linux-test-project/lcov" = { version = "2.6", filter_bins = ["genhtml"] }\n'
        'node = "lts"\n',
        encoding="utf-8",
    )
    assert mise_pins(config) == {
        "uv": "0.13.7",
        "github:chipsalliance/verible": "0.0-4298-g085eef05",
        "github:linux-test-project/lcov": "2.6",
    }
    assert mise_pins(tmp_path / "missing.toml") == {}


def test_every_pin_is_pinned() -> None:
    tools = [tool for group in GROUPS for tool in group.tools]
    assert {tool.pin for tool in tools if tool.pin} <= ci_pins().keys()
    assert {tool.mise for tool in tools if tool.mise} <= mise_pins().keys()


def test_verilator_minimum_covers_cocotbs() -> None:
    makefile = files("cocotb_tools").joinpath("makefiles/simulators/Makefile.verilator")
    match = re.search(r"^VLT_MIN := (\S+)$", makefile.read_text(encoding="utf-8"), re.MULTILINE)
    assert match is not None
    assert numbers(VerilatorProfile.minimum_version) >= numbers(match.group(1))


@pytest.mark.parametrize(
    ("release", "pin"),
    [("2.6-0", "2.6"), ("12.1.0+89a2c9fe9", "12.1")],
)
def test_release_versions_match_their_pins(release: str, pin: str) -> None:
    assert numbers(release) == numbers(pin)


def test_versions_compare_numerically() -> None:
    assert numbers("2.6-11.g1ad5aed") != numbers("2.6")
    assert numbers("5.055") > numbers("5.048") > numbers("5.036")
    assert numbers("6.000") > numbers("5.048")


@pytest.mark.parametrize(
    ("tool", "output", "status", "expected"),
    [
        (VERILATOR, "Verilator 5.054 2026-11-01 rev v5.054", 0, ("verified", "5.054", "")),
        (
            VERILATOR,
            "Verilator 5.055 devel rev v5.054-69-ge10a6237c",
            0,
            ("untested", "5.055", "CI verifies 5.054"),
        ),
        (
            VERILATOR,
            "Verilator 5.020 2024-01-01 rev (Debian 5.020-1)",
            0,
            ("error", "5.020", "the flow needs 5.054 or newer"),
        ),
        (
            VERIBLE,
            "Version\tv0.0-4298-g085eef05\nCommit-Timestamp\t2026-10-29T12:47:31Z",
            0,
            ("verified", "0.0-4298-g085eef05", ""),
        ),
        (
            VERIBLE,
            "Version\tv0.0-4053-g1a2b3c4",
            0,
            ("warning", "0.0-4053-g1a2b3c4", "CI uses 0.0-4298-g085eef05; formatting can differ"),
        ),
        (GENHTML, "genhtml: LCOV version 2.6-0", 0, ("verified", "2.6-0", "")),
        (GENHTML, PERL_ERROR, 2, ("warning", "", f"genhtml --version failed: {PERL_ERROR}")),
        (
            Tool("gtkwave"),
            "GTKWave Analyzer v3.3.126 (w)1999-2025 BSI",
            0,
            ("ok", "3.3.126", ""),
        ),
    ],
)
def test_check_status(
    bin_dir: Path, tool: Tool, output: str, status: int, expected: tuple[str, str, str]
) -> None:
    path = fake_tool(bin_dir, tool.name, output, status)
    result = check(tool, PINS, required=False)
    assert (result.status, result.version, result.detail) == expected
    assert result.path == str(path)


def test_missing_tool_is_an_error_only_when_required(
    bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert check(VERILATOR, PINS, required=False).status == "missing"
    monkeypatch.setenv("VERILATOR", str(bin_dir / "custom" / "verilator"))
    result = check(VERILATOR, PINS, required=True)
    assert (result.status, result.detail) == (
        "error",
        f"not found: VERILATOR={bin_dir / 'custom' / 'verilator'}",
    )


def test_missing_tool_that_mise_installs_suggests_mise_install(
    bin_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = check(GENHTML, PINS, required=False)
    assert (result.status, result.detail) == ("missing", "not found; run `mise install`")
    monkeypatch.setenv("GENHTML", str(bin_dir / "custom" / "genhtml"))
    result = check(GENHTML, PINS, required=False)
    assert result.detail == f"not found: GENHTML={bin_dir / 'custom' / 'genhtml'}"


def test_tools_are_located_as_the_flow_runs_them(
    bin_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_tool(bin_dir, "verilator", "Verilator 5.054")
    verilator = fake_tool(tmp_path / "custom", "verilator", "Verilator 5.054")
    monkeypatch.setenv("VERILATOR", str(verilator))
    assert doctor.locate(VERILATOR) == str(verilator)


def test_report_fails_only_on_errors(
    bin_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_tool(bin_dir, "uv", "uv 0.13.7 (x86_64-unknown-linux-gnu)")
    fake_tool(bin_dir, "verilator", "Verilator 5.055 devel rev v5.054-69-ge10a6237c")
    workflow = tmp_path / "ci.yml"
    workflow.write_text("env:\n  VERILATOR_VERSION: v5.054\n", encoding="utf-8")
    assert report(workflow) == 1
    assert "1 error." in capsys.readouterr().out
    fake_tool(bin_dir, "make", "GNU Make 4.4.1")
    assert report(workflow) == 0
    output = capsys.readouterr().out
    assert "missing   vsim" in output
    assert "error" not in output
