# Workflows

How to run the regression, add RTL and tests, and use named configurations,
assertions, coverage and waveforms. `make help` lists every target and override
variable; this guide explains how they fit together.

## Running tests

The simulation flow is cocotb through pytest. Pass the simulator as `SIM=<sim>`
to test, coverage, and waveform targets; the waveform targets open that
simulator's viewer.

`make test` runs every HDL configuration of one DUT, `top` unless
`DUT=<module>` selects another. `DUT=all` selects every DUT that has a
`tests/test_<module>.py` harness, and `CONFIG=<config>` one configuration; list
them with `make configs` (or `make configs DUT=all`). The run fails unless every
selected configuration ran. `coverage` selects the same way, while the commands
that open one waveform or coverage report (`waves`, `open-waves`,
`open-coverage`, `open-coverage-html`) need `CONFIG` when the DUT has several
configurations.

Select individual tests by exact name (`TEST=`) or regex (`TEST_FILTER=`). For
faster debug loops, `REBUILD=0` lets Questa compile incrementally and VCS reuse
its last build, as long as the build's inputs -- simulator, defines such as
`ABV`, parameters, build arguments and waveform tracing -- are the ones that
build was made from; otherwise the flow rebuilds and says why. It does not track
RTL edits, so rebuild after them. Verilator always runs its own incremental
build, so `REBUILD` does not change it.

Point `SV_SOURCES_FILE` at one or more space-separated `.vf` filelists to compile
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
  `hdl_toplevel`. The file's pytest entry point, its harness, runs the cocotb
  tests once per HDL configuration (see `tests/test_top.py`):

  ```python
  @pytest.mark.parametrize(("config", "parameters"), config_params(Path(__file__).stem))
  def test_top(config: str, parameters: dict[str, object]) -> None:
      build_and_test(test_module=Path(__file__).stem, config=config, parameters=parameters)
  ```

  Name the harness `test_<module>`: the flow runs each selected DUT and
  configuration by its pytest node ID, `tests/test_<module>.py::test_<module>[<config>]`.
  A bare `uv run pytest` runs every harness in every configuration.
- Keep tests deterministic and focused on behavior visible at the module's
  ports.
- Use current cocotb APIs: `unit="ns"`, not the deprecated `units="ns"`.

To split a module's tests across files, put them in `test_<module>__<variant>.py`
files that hold only `@cocotb.test()` functions, with no pytest entry point. A
`test_<module>.py` aggregator's harness globs them (`glob("test_<module>__*.py")`)
and passes the sorted stems as `test_module`, so they build once and share a
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

`config_params` turns a DUT's entry into its harness's parameters, and a DUT
without one gets a single configuration, `default`, with no overrides. Cocotb
test constants can read the active elaboration with `active_parameter("WIDTH", 8)`.
The runner exports the configuration as `COCOTB_CONFIG` and each parameter as
`COCOTB_PARAM_<name>`.

## Build directories

Configuration and instrumentation modes use separate build directories, where
`<config>` is `default` for a DUT without named configurations:

```text
build/<dut>/<sim>/<config>/normal/
build/<dut>/<sim>/<config>/waves/
build/<dut>/<sim>/<config>/coverage/
build/<dut>/<sim>/<config>/waves-coverage/
```

Each configuration and instrumentation thus keeps its own build, so switching
between them does not rebuild the others. Each directory also
holds its run's waveform, coverage data and reports; a run deletes those first,
so one whose build fails leaves no older ones to open or report. The combined
`WAVES=1 HDL_COVERAGE=1` mode uses `waves-coverage`, so a waveform or coverage
database exists in two modes: `open-waves`, `open-coverage` and
`open-coverage-html` use the newer one and say which, unless `HDL_COVERAGE`
(for a waveform) or `WAVES` (for coverage) selects one.
`make coverage` and `make waves` always open what their own run made.

`BUILD_DIR=<path>` moves the `build/` root, keeping the layout below it. Keep
generated files there; Git ignores `build/`, and `make clean` removes it but not
a relocated `BUILD_DIR`.

## Assertion-based verification

`rtl/top_abv.sv` holds optional SVA assertions and a covergroup for
`rtl/top.sv`, `` `include ``d under `` `ifdef ABV `` (see its header for the
structure). ABV files are bare SVA, not compilation units: follow the pattern in
`rtl/top_abv.sv` and list them in `rtl/verible.vf` only. A Python covergroup
mirror in `tests/coverage_top.py` (cocotb-coverage) provides the same functional
coverage on simulators that do not collect SV covergroups. Enable assertions
with `ABV=1`.

## Coverage

`make coverage` runs the regression with Verilator's line, toggle, FSM, and
`cover property` coverage, enables `ABV` automatically, and writes LCOV data and
an annotated report for each selected configuration (`DUT=all` for every DUT);
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
