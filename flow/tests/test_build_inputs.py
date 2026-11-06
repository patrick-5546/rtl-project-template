import re
from pathlib import Path

import pytest

from flow.build_inputs import filelist_dependencies


def test_filelist_dependencies_follow_variables_filelists_and_includes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rtl = tmp_path / "rtl"
    include = tmp_path / "include"
    rtl.mkdir()
    include.mkdir()
    header = include / "defs.svh"
    nested_header = include / "widths.svh"
    source = rtl / "top.sv"
    nested = rtl / "nested.vf"
    root = rtl / "sources.vf"
    header.write_text('`include "widths.svh"\n')
    nested_header.write_text("`define WIDTH 32\n")
    source.write_text('`include "defs.svh"\nmodule top; endmodule\n')
    nested.write_text("${PROJECT_ROOT}/rtl/top.sv\n")
    root.write_text("+incdir+${PROJECT_ROOT}/include\n-f nested.vf // ignored.sv\n")
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    assert filelist_dependencies([root], tmp_path) == sorted(
        [header, nested_header, nested, root, source]
    )


@pytest.mark.parametrize(
    ("nested_option", "library_option"),
    [("-f nested.vf", "-y cells"), ("-Fnested.vf", "-ycells")],
)
def test_filelist_dependencies_follow_library_options(
    tmp_path: Path, nested_option: str, library_option: str
) -> None:
    sources = [tmp_path / name for name in ("head.sv", "nested.sv", "library.sv")]
    for source in sources:
        source.touch()
    cells = tmp_path / "cells"
    cells.mkdir()
    cell = cells / "cell.sv"
    cell.touch()
    nested = tmp_path / "nested.vf"
    nested.write_text("nested.sv\n")
    root = tmp_path / "sources.vf"
    root.write_text(f"head.sv {nested_option} -v library.sv {library_option}\n")

    assert filelist_dependencies([root], tmp_path) == sorted([root, nested, *sources, cells, cell])


def test_filelist_dependencies_reject_an_option_without_a_path(tmp_path: Path) -> None:
    root = tmp_path / "sources.vf"
    root.write_text("# Filelist\n-f\n")

    with pytest.raises(ValueError, match=re.escape(f"{root}:2: -f requires a path")):
        filelist_dependencies([root], tmp_path)
