from pathlib import Path
from typing import Any

import cocotb
import pytest
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer

from flow.runner import active_parameter, build_and_test, config_params

_WIDTH = active_parameter("WIDTH", 8)
_MAX_COUNT = (1 << _WIDTH) - 1
_MID_COUNT = _MAX_COUNT // 2
_HIGH_COUNT = _MAX_COUNT - 1


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
@cocotb.parametrize(target_count=[_MID_COUNT, _HIGH_COUNT, _MAX_COUNT])
async def enable_low_holds_at_count(dut: Any, target_count: int) -> None:
    """Drop enable after reaching a count bin and verify the value holds.

    The targets land in the mid, high, and max bins of ``counter_cg`` for the
    active WIDTH configuration; cocotb generates one test per value.
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
    await tick(dut, _MAX_COUNT)
    assert dut.count_o.value.to_unsigned() == _MAX_COUNT

    await tick(dut)
    assert dut.count_o.value.to_unsigned() == 0


@pytest.mark.parametrize(("config", "parameters"), config_params(Path(__file__).stem))
def test_top(config: str, parameters: dict[str, object]) -> None:
    build_and_test(test_module=Path(__file__).stem, config=config, parameters=parameters)
