from pathlib import Path
from typing import Any

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

from flow.runner import build_and_test, env_flag

_ABV = env_flag("ABV", default=False)

if _ABV:
    from cocotb_coverage.coverage import coverage_db
    from coverage_top import sample_from_dut


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
        if _ABV:
            sample_from_dut(dut)  # pyright: ignore[reportPossiblyUnboundVariable] - guarded by _ABV


@cocotb.test()
async def reset_clears_counter(dut: Any) -> None:
    """Verify that asserting reset clears the counter to zero."""
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
    """Verify that the counter increments on each clock when enabled."""
    await start_counter(dut)

    dut.en_i.value = 1
    for expected_count in range(1, 6):
        await tick(dut)
        assert dut.count_o.value.to_unsigned() == expected_count


@cocotb.test()
async def enable_low_holds_count(dut: Any) -> None:
    """Verify that the counter holds its value when enable is deasserted."""
    await start_counter(dut)

    dut.en_i.value = 1
    await tick(dut, 3)
    assert dut.count_o.value.to_unsigned() == 3

    dut.en_i.value = 0
    await tick(dut, 4)
    assert dut.count_o.value.to_unsigned() == 3


@cocotb.test()
@cocotb.parametrize(target_count=[100, 200, 255])
async def enable_low_holds_at_count(dut: Any, target_count: int) -> None:
    """Drop enable after reaching a count bin and verify the value holds.

    The targets land in the mid (100), high (200), and max (255) bins of
    ``counter_cg`` for the default ``WIDTH=8``; cocotb generates one test per
    value (``..._100``/``..._200``/``..._255``) within a single build.
    """
    await start_counter(dut)

    dut.en_i.value = 1
    await tick(dut, target_count)
    assert dut.count_o.value.to_unsigned() == target_count

    dut.en_i.value = 0
    await tick(dut)
    assert dut.count_o.value.to_unsigned() == target_count


@cocotb.test()
async def counter_wraps(dut: Any) -> None:
    """Verify that the counter wraps from max value back to zero."""
    await start_counter(dut)

    dut.en_i.value = 1
    await tick(dut, 255)
    assert dut.count_o.value.to_unsigned() == 255

    await tick(dut)
    assert dut.count_o.value.to_unsigned() == 0


@cocotb.test(skip=not _ABV)
async def check_coverage(dut: Any) -> None:
    """Assert that all coverage bins were hit by preceding tests."""
    coverage_db.report_coverage(cocotb.log.info, bins=True)  # pyright: ignore[reportPossiblyUnboundVariable] - guarded by _ABV
    coverage_db.export_to_xml(filename="cocotb_coverage.xml")  # pyright: ignore[reportPossiblyUnboundVariable] - guarded by _ABV

    missed: list[str] = []
    for path in coverage_db:  # pyright: ignore[reportPossiblyUnboundVariable] - guarded by _ABV
        node = coverage_db[path]  # pyright: ignore[reportPossiblyUnboundVariable] - guarded by _ABV
        if not hasattr(node, "detailed_coverage"):
            continue
        for bin_name, hits in node.detailed_coverage.items():
            if isinstance(hits, int) and hits == 0:
                missed.append(f"{path}.{bin_name}")
    if missed:
        raise AssertionError("Coverage holes — bins never hit:\n  " + "\n  ".join(missed))


def test_top() -> None:
    build_and_test(test_module=Path(__file__).stem)
