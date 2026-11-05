# Workflows

How to run the regression, add RTL and tests, and use named configurations,
assertions, coverage and waveforms. `make help` lists every target and override
variable; this guide explains how they fit together.

## Running tests

The simulation flow is cocotb through pytest. Pass the simulator as `SIM=<sim>`
to test, coverage, and waveform targets; the waveform targets open that
simulator's viewer.

`make test` runs every named configuration for one DUT.
List them with `make configs` and select one with `make test CONFIG=<config>`.
`make test-all` runs every `tests/test_*.py` across all DUTs and verifies that
each configured or unconfigured DUT case executed; pass `DUT=<module>` to
select a DUT for test, wave, and coverage commands.

Select individual tests by exact name (`TEST=`) or regex (`TEST_FILTER=`), and
reuse an existing simulator build with `REBUILD=0` for faster debug loops. Point
`SV_SOURCES_FILE` at one or more space-separated `.vf` filelists to compile
additional RTL (e.g. `make test SV_SOURCES_FILE='rtl/sources.vf rtl/extra.vf'`);
each filelist is handed to the simulator with its own `-f`.

## Adding RTL

- New RTL goes in `rtl/` and must be listed in `rtl/sources.vf` (its header
  documents the entry syntax). Add it to `rtl/verible.vf` too, so Verible lints
  and formats it: that list is standalone.
- Use `_i` for inputs, `_o` for outputs, and `_ni` for active-low reset inputs.
- Prefer explicit port directions and `logic` signals, and parameterized widths
  where they keep a module reusable.

## Writing tests

- A module's tests go in `tests/test_<module>.py`, where `<module>` is the RTL
  top module: the flow derives the top level from the filename, so tests pass no
  `hdl_toplevel`. The file's pytest entry point calls `build_and_test` from
  `flow.runner` with `test_module=Path(__file__).stem`; see `tests/test_top.py`.
- Keep tests deterministic and focused on behavior visible at the module's
  ports.
- Use current cocotb APIs: `unit="ns"`, not the deprecated `units="ns"`.

To split a module's tests across files, put them in `test_<module>__<variant>.py`
files that hold only `@cocotb.test()` functions, with no pytest entry point. A
`test_<module>.py` aggregator globs them (`glob("test_<module>__*.py")`) and
passes the sorted stems to `build_and_test`, so they build once and share a
single end-of-test summary. Filename variants group cocotb modules; named
configurations select HDL parameter values and are independent of that naming
convention.

## Named HDL configurations

An import-safe `tests/cocotb_configs.py` manifest maps each DUT and
configuration name to its top-level parameter values:

```python
HDL_CONFIGS = {
    "top": {
        "width4": {"WIDTH": 4},
        "width8": {"WIDTH": 8},
    },
}
```

The pytest harness parameterizes the same mapping and passes each pair to
`build_and_test(..., config=config, parameters=parameters)`. Cocotb test
constants can read the active elaboration with `active_parameter("WIDTH", 8)`.
The runner exports the configuration as `COCOTB_CONFIG` and each parameter as
`COCOTB_PARAM_<name>`.

## Build directories

Configuration and instrumentation modes use separate build directories:

```text
build/<dut>/<sim>/<config>/normal/
build/<dut>/<sim>/<config>/waves/
build/<dut>/<sim>/<config>/coverage/
build/<dut>/<sim>/<config>/waves-coverage/
```

This prevents `REBUILD=0` from reusing an executable built with incompatible
parameters, waveform tracing, or coverage instrumentation. The combined
`WAVES=1 HDL_COVERAGE=1` mode uses `waves-coverage`; pass the other mode flag
when reopening it (`open-waves HDL_COVERAGE=1` or
`open-coverage-html WAVES=1`). Each directory also holds the run's waveform,
coverage data and reports. Keep generated files under `build/`; Git ignores it.

## Assertion-based verification

`rtl/top_abv.sv` holds optional SVA assertions and a covergroup for
`rtl/top.sv`, `` `include ``d under `` `ifdef ABV `` (see its header for the
structure). ABV files are bare SVA, not compilation units: follow the pattern in
`rtl/top_abv.sv` and list them in `rtl/verible.vf` only. A Python covergroup
mirror in `tests/coverage_top.py` (cocotb-coverage) provides the same functional
coverage on simulators that do not collect SV covergroups. Enable assertions
with `ABV=1`.

## Coverage

`make coverage CONFIG=<name>` runs Verilator with line, toggle, FSM, and
`cover property` coverage, enables `ABV` automatically, and writes LCOV data.
`make coverage-all` runs the same unified DUT/configuration regression as
`test-all`, then generates a report for every isolated coverage database;
`make open-coverage-html CONFIG=<name>` generates and opens the HTML report.
The same `coverage SIM=<sim>` pattern works for Questa and VCS. `open-coverage`
opens a simulator's native GUI coverage viewer where one exists (Questa, and
VCS via Verdi); Verilator has none, so use `open-coverage-html` for it. Set
`HTML_VIEWER` to choose the program that opens HTML reports (e.g. `wslview` on
WSL, which needs wslu). Coverage report commands fail on missing artifacts or
tool errors, but do not enforce percentage thresholds. See
[Tools](tools.md#coverage) for what each simulator collects.

SV covergroups (e.g. in `rtl/top_abv.sv`) and their Python mirrors in
`tests/coverage_*.py` must stay in sync: when adding, removing, or modifying
coverpoints or bins in one, update the other to match. cocotb-coverage does not
support keyword arguments in sampling function calls, so always pass positional
arguments.

## Waveforms

`make waves` runs the tests with waveform dumping and opens the simulator's
viewer; `make open-waves` reopens the last waveform. Each viewer loads a
reusable layout from `waves/<DUT>.*` when present, and `make help` lists the
variables that select another layout:

- Verilator: GTKWave (`waves/<DUT>.gtkw`) reads its FST. The wave targets
  prepare GTKWave's RTLBrowse window, which links signals back to their source
  and annotates it with values from the waveform; skip that with
  `NO_RTLBROWSE=1`.
- Questa (`waves/<DUT>.do`) opens its native WLF with source-linked debug:
  double-click a signal to find its RTL driver.
- VCS: Verdi (`waves/<DUT>.rc`) opens the FSDB that VCS dumps, with the
  `simv.daidir` knowledge database for source-linked debug.
