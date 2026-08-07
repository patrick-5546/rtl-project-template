from pathlib import Path
from unittest.mock import patch

import pytest

from flow.viewers import GtkwaveProfile, SurferProfile


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


def test_surfer_uses_explicit_state_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "dump.fst").touch()
    state = tmp_path / "layout.ron"
    state.touch()
    monkeypatch.setenv("SURFER_STATE", str(state))
    with patch("flow.viewers.run") as run:
        SurferProfile().open_waves(tmp_path, build_dir, "top", "width8")
    assert run.call_args.args[0][1:3] == ["--state-file", str(state)]


def test_missing_wave_hint_retains_config(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="CONFIG=width4"):
        SurferProfile().open_waves(tmp_path, tmp_path / "missing", "top", "width4")
