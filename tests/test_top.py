import os
import re
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


def test_top_with_verilator() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    test_dir = Path(__file__).resolve().parent
    build_dir = project_dir / "build" / "sim"
    pythonpath = os.pathsep.join(filter(None, [str(test_dir), os.environ.get("PYTHONPATH", "")]))
    selected_test = os.environ.get("TEST") or None
    test_filter = os.environ.get("TEST_FILTER") or None
    rebuild = env_flag("REBUILD", default=True)
    if selected_test and test_filter:
        raise ValueError("Set either TEST or TEST_FILTER, not both.")
    if selected_test:
        test_filter = rf"(^|.*\.){re.escape(selected_test)}$"

    runner = get_runner(os.environ.get("SIM", "verilator"))
    runner.build(
        sources=[project_dir / "rtl" / "top.sv"],
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
        waves=True,
        extra_env={"PYTHONPATH": pythonpath},
    )
