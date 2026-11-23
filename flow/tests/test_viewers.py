import json
from pathlib import Path
from unittest.mock import patch

import pytest

from flow.viewers import GtkwaveProfile, VerdiProfile


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


def test_gtkwave_opens_rtlbrowse_with_the_stems_of_the_duts_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = tmp_path / "build"
    json_dir = build_dir / "rtlbrowse"
    json_dir.mkdir(parents=True)
    (build_dir / "dump.fst").touch()
    files = {"g": {"filename": "rtl/top.sv", "realpath": "/project/rtl/top.sv"}}
    (json_dir / "Vtop.tree.meta.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    top = {"type": "MODULE", "name": "top", "addr": "(F)", "loc": "g,6:8,6:11"}
    (json_dir / "Vtop.tree.json").write_text(json.dumps({"modulesp": [top]}), encoding="utf-8")
    monkeypatch.delenv("NO_RTLBROWSE", raising=False)
    monkeypatch.setenv("GTKWAVE_STEMS_TOP", "wrong")
    with patch("flow.viewers.run") as run:
        GtkwaveProfile().open_waves(tmp_path, build_dir, "top", "width4")
    stems = json_dir / "top.stems"
    command = run.call_args.args[0]
    assert command[command.index("-t") + 1] == str(stems)
    assert stems.read_text(encoding="utf-8") == (
        "++ module top file /project/rtl/top.sv lines 6 - 6\n"
    )


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
