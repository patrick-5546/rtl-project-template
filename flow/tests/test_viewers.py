import os
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from flow.viewers import GtkwaveProfile, VerdiProfile


def rtlbrowse_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A waves build directory with the Verilator tree that json2stems reads."""
    monkeypatch.delenv("NO_RTLBROWSE", raising=False)
    monkeypatch.delenv("JSON2STEMS", raising=False)
    build_dir = tmp_path / "build"
    json_dir = build_dir / "rtlbrowse"
    json_dir.mkdir(parents=True)
    (build_dir / "dump.fst").touch()
    (json_dir / "Vtop.tree.json").touch()
    (json_dir / "Vtop.tree.meta.json").touch()
    return build_dir


def json2stems_writing(stems: str) -> Callable[..., None]:
    """A stand-in for ``run`` whose json2stems writes *stems*, its last argument."""

    def fake_run(cmd: list[str], *, cwd: Path) -> None:
        del cwd
        if cmd[-1].endswith(".stems"):
            Path(cmd[-1]).write_text(stems, encoding="utf-8")

    return fake_run


def test_gtkwave_command_without_rtlbrowse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    wave = build_dir / "dump.fst"
    wave.touch()
    monkeypatch.setenv("NO_RTLBROWSE", "1")
    with patch("flow.viewers.run") as run:
        GtkwaveProfile().open_waves(tmp_path, build_dir, "top", "width4")
    command = run.call_args.args[0]
    assert command[-1] == str(wave)
    assert "-t" not in command


def test_gtkwave_rtlbrowse_top_is_derived_from_dut(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = rtlbrowse_build(tmp_path, monkeypatch)
    json_dir = build_dir / "rtlbrowse"
    monkeypatch.setenv("GTKWAVE_STEMS_TOP", "wrong")
    with (
        patch("flow.viewers.shutil.which", return_value="/usr/bin/json2stems"),
        patch("flow.viewers.run", side_effect=json2stems_writing("")) as run,
    ):
        GtkwaveProfile().open_waves(tmp_path, build_dir, "top", "width4")
    assert run.call_args_list[0].args[0][1:4] == [
        str(json_dir / "Vtop.tree.meta.json"),
        str(json_dir / "Vtop.tree.json"),
        str(json_dir / "top.stems"),
    ]


def test_gtkwave_stems_leave_out_verilator_builtin_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = rtlbrowse_build(tmp_path, monkeypatch)
    top = "++ module top file /project/rtl/top.sv lines 9 - 9\n"
    stems = (
        "++ module $unit file <built-in> lines 0 - 0\n"
        f"{top}"
        "++ module __Vconstpool file <built-in> lines 0 - 0\n"
    )
    with (
        patch("flow.viewers.shutil.which", return_value="/usr/bin/json2stems"),
        patch("flow.viewers.run", side_effect=json2stems_writing(stems)),
    ):
        GtkwaveProfile().open_waves(tmp_path, build_dir, "top", "width8")
    assert (build_dir / "rtlbrowse" / "top.stems").read_text(encoding="utf-8") == top


def test_gtkwave_override_starts_its_own_rtlbrowse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "dump.fst").touch()
    gtkwave = tmp_path / "gtkwave4" / "bin" / "gtkwave"
    monkeypatch.setenv("GTKWAVE", str(gtkwave))
    monkeypatch.setenv("NO_RTLBROWSE", "1")
    monkeypatch.setenv("PATH", "/usr/bin")
    paths: list[str] = []

    def record_path(cmd: list[str], *, cwd: Path) -> None:
        del cmd, cwd
        paths.append(os.environ["PATH"])

    with patch("flow.viewers.run", side_effect=record_path):
        GtkwaveProfile().open_waves(tmp_path, build_dir, "top", "width4")
    assert paths == [f"{gtkwave.parent.resolve()}{os.pathsep}/usr/bin"]


def test_gtkwave_explains_a_missing_json2stems(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = tmp_path / "build"
    json_dir = build_dir / "rtlbrowse"
    json_dir.mkdir(parents=True)
    (build_dir / "dump.fst").touch()
    (json_dir / "Vtop.tree.json").touch()
    (json_dir / "Vtop.tree.meta.json").touch()
    monkeypatch.setenv("JSON2STEMS", str(tmp_path / "no-json2stems"))
    with (
        patch("flow.viewers.run") as run,
        pytest.raises(SystemExit, match="NO_RTLBROWSE=1"),
    ):
        GtkwaveProfile().open_waves(tmp_path, build_dir, "top", "width4")
    run.assert_not_called()


def test_verdi_debug_database_is_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "dump.fsdb").touch()
    monkeypatch.setenv("VCS_DAIDIR", "wrong.daidir")
    with patch("flow.viewers.run") as run:
        VerdiProfile().open_waves(tmp_path, build_dir, "top", "width4")
    command = run.call_args.args[0]
    assert command[command.index("-dbdir") + 1] == str(build_dir / "simv.daidir")


def test_missing_wave_hint_retains_config(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="CONFIG=width4"):
        GtkwaveProfile().open_waves(tmp_path, tmp_path / "missing", "top", "width4")
