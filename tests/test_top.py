import os
import re
import shlex
from pathlib import Path
from typing import Any

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer
from cocotb_tools.runner import get_runner


def env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def project_path_from_env(name: str, project_dir: Path, default: Path) -> Path:
    value = os.environ.get(name)
    path = Path(value) if value else default
    return path if path.is_absolute() else project_dir / path


def project_paths_from_list_file(name: str, project_dir: Path, default: Path) -> list[Path]:
    list_file = project_path_from_env(name, project_dir, default)
    paths: list[Path] = []
    for line in list_file.read_text().splitlines():
        entry = line.split("#", maxsplit=1)[0].strip()
        if not entry:
            continue
        path = Path(entry)
        paths.append(path if path.is_absolute() else project_dir / path)
    return paths


async def start_counter(dut: Any) -> None:
    cocotb.start_soon(Clock(dut.clk_i, 10, unit="ns").start())
    dut.en_i.value = 0
    dut.rst_ni.value = 0
    await ClockCycles(dut.clk_i, 2)
    assert dut.count_o.value.to_unsigned() == 0
    dut.rst_ni.value = 1
    await tick(dut)
    assert dut.count_o.value.to_unsigned() == 0


async def tick(dut: Any, cycles: int = 1) -> None:
    for _ in range(cycles):
        await RisingEdge(dut.clk_i)
        await Timer(1, unit="ns")


@cocotb.test()
async def reset_clears_counter(dut: Any) -> None:
    await start_counter(dut)

    dut.en_i.value = 1
    await tick(dut, 5)
    assert dut.count_o.value.to_unsigned() == 5

    dut.rst_ni.value = 0
    await Timer(1, unit="ns")
    assert dut.count_o.value.to_unsigned() == 5

    await tick(dut)
    assert dut.count_o.value.to_unsigned() == 0


@cocotb.test()
async def enable_high_counts(dut: Any) -> None:
    await start_counter(dut)

    dut.en_i.value = 1
    for expected_count in range(1, 6):
        await tick(dut)
        assert dut.count_o.value.to_unsigned() == expected_count


@cocotb.test()
async def enable_low_holds_count(dut: Any) -> None:
    await start_counter(dut)

    dut.en_i.value = 1
    await tick(dut, 3)
    assert dut.count_o.value.to_unsigned() == 3

    dut.en_i.value = 0
    await tick(dut, 4)
    assert dut.count_o.value.to_unsigned() == 3


@cocotb.test()
async def counter_wraps(dut: Any) -> None:
    await start_counter(dut)

    dut.en_i.value = 1
    await tick(dut, 255)
    assert dut.count_o.value.to_unsigned() == 255

    await tick(dut)
    assert dut.count_o.value.to_unsigned() == 0


def test_top_with_simulator() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    test_dir = Path(__file__).resolve().parent
    simulator = os.environ.get("SIM", "verilator")
    build_dir = project_path_from_env("BUILD_DIR", project_dir, project_dir / "build" / simulator)
    modelsim_wave = project_path_from_env(
        "MODELSIM_WAVE",
        project_dir,
        project_dir / "build" / "modelsim" / "vsim.wlf",
    )
    modelsim_do = project_path_from_env(
        "MODELSIM_DO",
        project_dir,
        project_dir / "waves" / "top.do",
    )
    pythonpath = os.pathsep.join(filter(None, [str(test_dir), os.environ.get("PYTHONPATH", "")]))
    selected_test = os.environ.get("TEST") or None
    test_filter = os.environ.get("TEST_FILTER") or None
    rebuild = env_flag("REBUILD", default=True)
    abv = env_flag("ABV", default=False)
    hdl_coverage = env_flag("HDL_COVERAGE", default=False)
    modelsim_gui = env_flag("MODELSIM_GUI", default=False)
    coverage_dat = project_path_from_env(
        "COVERAGE_DAT",
        project_dir,
        build_dir / "coverage.dat",
    )
    sv_sources = project_paths_from_list_file(
        "SV_SOURCES_FILE",
        project_dir,
        project_dir / "rtl" / "sources.vf",
    )
    abv_sources = project_paths_from_list_file(
        "ABV_SOURCES_FILE",
        project_dir,
        project_dir / "rtl" / "abv_sources.vf",
    )
    if selected_test and test_filter:
        raise ValueError("Set either TEST or TEST_FILTER, not both.")
    if selected_test:
        test_filter = rf"(^|.*\.){re.escape(selected_test)}$"
    if hdl_coverage and simulator != "verilator":
        raise ValueError("HDL_COVERAGE=1 is supported for the Verilator flow.")
    if modelsim_gui and simulator != "questa":
        raise ValueError("MODELSIM_GUI=1 is supported for the ModelSim/Questa flow.")

    sources = [*sv_sources]
    defines: dict[str, object] = {}
    if abv:
        sources.extend(abv_sources)
        defines["ABV"] = 1

    build_args: list[str] = []
    plusargs: list[str] = []
    pre_cmd: list[str] | None = None
    test_args: list[str] = []
    if hdl_coverage:
        coverage_dat.parent.mkdir(parents=True, exist_ok=True)
        build_args.append("--coverage")
        plusargs.append(f"+verilator+coverage+file+{coverage_dat}")
    if simulator == "questa":
        modelsim_wave.parent.mkdir(parents=True, exist_ok=True)
        test_args = [
            *shlex.split(os.environ.get("MODELSIM_ARGS", "")),
            "-wlf",
            str(modelsim_wave),
            "-nowlfdeleteonquit",
        ]
        if modelsim_gui:
            gui_commands = ["log -recursive /*", "run -all"]
            if modelsim_do.is_file():
                gui_commands.append(f"source {{{modelsim_do.as_posix()}}}")
            pre_cmd = ["; ".join(gui_commands)]

    runner = get_runner(simulator)
    runner.build(
        sources=sources,
        defines=defines,
        build_args=build_args,
        hdl_toplevel="top",
        build_dir=build_dir,
        always=rebuild,
        waves=True,
    )
    runner.test(
        hdl_toplevel="top",
        test_module=Path(__file__).stem,
        test_filter=test_filter,
        build_dir=build_dir,
        waves=not modelsim_gui,
        gui=modelsim_gui,
        extra_env={"PYTHONPATH": pythonpath},
        test_args=test_args,
        plusargs=plusargs,
        pre_cmd=pre_cmd,
    )
