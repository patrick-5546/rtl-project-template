"""Python functional coverage mirroring ``counter_cg`` in ``rtl/top_abv.sv``.

Keep these definitions in sync with the SystemVerilog covergroup.  When
coverpoints or bins change in one, update the other to match.

Uses *cocotb-coverage* so that covergroup data is collected even on simulators
that cannot collect SV covergroups (e.g. Verilator, Questa Starter).
"""

from typing import Any

from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_section

# WIDTH = 8 constants matching top_abv.sv MaxCount = {WIDTH{1'b1}} = 255
_MAX_COUNT = 255

counter_cg = coverage_section(
    CoverPoint(
        "top.counter_cg.cp_count",
        xf=lambda count_o, en_i, rst_ni: count_o,
        bins=["low", "mid", "high", "max"],
        rel=lambda val, b: (
            (b == "low" and 0 <= val <= _MAX_COUNT // 4)
            or (b == "mid" and _MAX_COUNT // 4 < val <= _MAX_COUNT * 3 // 4)
            or (b == "high" and _MAX_COUNT * 3 // 4 < val <= _MAX_COUNT - 1)
            or (b == "max" and val == _MAX_COUNT)
        ),
    ),
    CoverPoint(
        "top.counter_cg.cp_en",
        xf=lambda count_o, en_i, rst_ni: en_i,
        bins=[0, 1],
        bins_labels=["disabled", "enabled"],
    ),
    CoverPoint(
        "top.counter_cg.cp_rst",
        xf=lambda count_o, en_i, rst_ni: rst_ni,
        bins=[0, 1],
        bins_labels=["active", "inactive"],
    ),
    CoverCross(
        "top.counter_cg.cx_en_count",
        items=["top.counter_cg.cp_en", "top.counter_cg.cp_count"],
    ),
)


@counter_cg
def _sample_counter(count_o: int, en_i: int, rst_ni: int) -> None:
    """Sample all coverpoints.  Call once per clock cycle."""


def sample_from_dut(dut: Any) -> None:
    """Read DUT signals and sample coverage."""
    _sample_counter(
        dut.count_o.value.to_unsigned(),
        int(dut.en_i.value),
        int(dut.rst_ni.value),
    )
