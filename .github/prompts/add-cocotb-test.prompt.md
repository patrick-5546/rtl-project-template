# Add or update cocotb tests

Use this prompt when creating or changing cocotb tests for the SystemVerilog RTL.

## Goal

Add pytest-launched cocotb coverage for the requested RTL behavior using
Verilator as the default simulator.

## Instructions

1. Inspect `rtl/`, existing tests under `tests/`, and `pyproject.toml`.
2. Keep tests in `tests/` and ensure they are runnable through pytest.
3. Use `cocotb_tools.runner.get_runner` for simulator build/test integration
   unless the project already has a better local helper.
4. Default to `SIM=verilator` and avoid simulator-specific assumptions unless
   documented.
5. Test externally visible behavior rather than implementation details.
6. Keep tests deterministic:
   - Start clocks consistently.
   - Apply reset before checking normal behavior.
   - Wait for stable signal values after clock edges.
7. Prefer modern cocotb APIs, such as `unit="ns"` for time units.
8. Preserve waveform generation when it helps debugging. Verilator writes
   `build/verilator/dump.vcd`; ModelSim writes `build/modelsim/vsim.wlf`.
9. Prefer cocotb runner selection via `TEST` or `TEST_FILTER` over pytest `-k`,
   because pytest only sees the outer wrapper test.
10. Use optional ModelSim coverage only when relevant; this project invokes it
    through `make test-modelsim`, which uses cocotb's `SIM=questa` runner.

## Validation

Run the relevant commands after editing:

```sh
make py-format
make py-lint
make py-type
make test
```

For targeted debug runs, use:

```sh
make test TEST=<cocotb_test_name>
make test TEST_FILTER='<regex>'
make test TEST=<cocotb_test_name> REBUILD=0
```

If Python dependencies or tool settings changed, also run:

```sh
uv sync
```
