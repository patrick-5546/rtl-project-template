from pathlib import Path
from unittest.mock import patch

import pytest

from flow.runner import RunConfig
from flow.simulators import QuestaProfile, VcsProfile, VerilatorProfile


def config(
    tmp_path: Path,
    *,
    waves: bool = False,
    coverage: bool = False,
    cm_hier: Path | None = None,
) -> RunConfig:
    return RunConfig(
        hdl_coverage=coverage,
        gui=False,
        waves=waves,
        coverage_dat=tmp_path / "coverage.dat",
        wave_path=tmp_path / "wave",
        questa_do=tmp_path / "top.do",
        questa_args=[],
        cm_hier=cm_hier,
        build_dir=tmp_path,
        hdl_toplevel="top",
        sources_files=[tmp_path / "sources.vf"],
    )


@pytest.mark.parametrize(
    ("waves", "coverage"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_verilator_configure_modes(
    tmp_path: Path,
    waves: bool,
    coverage: bool,
) -> None:
    profile = VerilatorProfile()
    with patch.object(profile, "require_coverage_version"):
        args = profile.configure(config(tmp_path, waves=waves, coverage=coverage))
    assert "--timing" in args.build_args
    assert ("--trace-fst" in args.build_args) is waves
    assert ("--coverage" in args.build_args) is coverage
    assert bool(args.plusargs) is coverage


def test_questa_preserves_filelist_macros_and_timescale(tmp_path: Path) -> None:
    args = QuestaProfile().configure(config(tmp_path, waves=True, coverage=True))
    assert args.build_args[2:5] == ["-mfcu", "-timescale", "1ns/1ps"]
    assert "-voptargs=+acc" in args.test_args
    assert "-coverage" in args.test_args


def test_vcs_coverage_filters_constants_and_honors_cm_hier(tmp_path: Path) -> None:
    cm_hier = tmp_path / "top_cm_hier.cfg"
    cm_hier.touch()
    args = VcsProfile().configure(config(tmp_path, coverage=True, cm_hier=cm_hier))
    assert "-cm_noconst" in args.build_args
    assert "-cm_seqnoconst" in args.build_args
    assert args.build_args[-2:] == ["-cm_hier", str(cm_hier)]


def test_profile_wave_paths_are_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WAVE", "wrong.fst")
    monkeypatch.setenv("QUESTA_WAVE", "wrong.wlf")
    monkeypatch.setenv("VCS_WAVE", "wrong.fsdb")
    build_dir = tmp_path / "build"
    assert VerilatorProfile().wave_path(build_dir) == build_dir / "dump.fst"
    assert QuestaProfile().wave_path(build_dir) == build_dir / "vsim.wlf"
    assert VcsProfile().wave_path(build_dir) == build_dir / "dump.fsdb"


def test_verilator_html_report_has_no_percentage_gate(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "coverage.info").touch()
    with (
        patch("flow.simulators.run") as run,
        patch("flow.simulators.open_html"),
    ):
        VerilatorProfile().open_coverage_html(
            tmp_path,
            build_dir,
            dut="top",
            config="width4",
        )
    command = run.call_args.args[0]
    assert "--fail-under-lines" not in command
    assert "--fail-under-branches" not in command
