# Workflows

How to run the tests, add RTL and tests, and use named configurations,
assertions, coverage and waveforms. `make help` lists every target and variable.

## Running tests

`make test` runs the cocotb tests, through pytest, of every DUT that has a
`tests/test_<module>.py` harness, in each of its HDL configurations. Select one
DUT with `DUT=<module>`, one of its configurations with `CONFIG=<name>`
(`make configs` lists them), one cocotb test with `TEST=<name>`, or the tests
whose names match a regex with `TEST_FILTER=<regex>`. The run fails unless every
selected configuration ran. `make coverage` selects the same way, while the
commands that open one waveform or coverage report (`waves`, `open-waves`,
`open-coverage`, `open-coverage-html`) need `DUT` when there are several DUTs,
and `CONFIG` when the DUT has several configurations. `SIM=questa` or `SIM=vcs`
selects another simulator for the test, coverage and waveform targets.

`SV_SOURCES_FILE` names the filelists to compile, `rtl/sources.vf` by default;
give several, space-separated, to compile more RTL (e.g.
`make test SV_SOURCES_FILE='rtl/sources.vf rtl/extra.vf'`).

Questa and VCS rebuild on every run unless `REBUILD=0`, which reuses the last
build while its simulator, defines, parameters, build arguments and waveform
tracing are unchanged, and otherwise rebuilds and says why. It does not check
the RTL itself, so rebuild after editing it. Verilator always rebuilds
incrementally.

## Adding RTL

- Put new RTL in `rtl/` and list it in `rtl/sources.vf`, the filelist that the
  simulators and the Verilator and slang linters compile. List the project's own
  files in `rtl/verible.vf` too: Verible lints and formats only the files that it
  names, so it never reformats files from other people, such as vendor IP. Each
  list's header describes its entries.
- Give each module a specification in `docs/design/<module>.md`, like
  `docs/design/top.md`, and update it with the RTL.
- Name inputs `_i`, outputs `_o` and active-low reset inputs `_ni`. Prefer
  explicit port directions, `logic` signals, and parameterized widths where they
  keep a module reusable.
- A module needs no `` `timescale ``: the flow builds and lints one without it at
  `1ns/1ps`, on every simulator. But a file's `` `timescale `` also applies to
  the files after it in `rtl/sources.vf`, so list those that declare one last.

## Writing tests

A module's tests go in `tests/test_<module>.py`, where `<module>` is the RTL top
module that the flow builds for them. The file's pytest function
`test_<module>`, its harness, builds the module and runs the file's cocotb tests
once per HDL configuration (see `tests/test_top.py`):

```python
@pytest.mark.parametrize(("config", "parameters"), config_params(Path(__file__).stem))
def test_top(config: str, parameters: dict[str, object]) -> None:
    build_and_test(test_module=Path(__file__).stem, config=config, parameters=parameters)
```

The flow runs each selected DUT and configuration by its pytest node ID,
`tests/test_<module>.py::test_<module>[<config>]`, so keep the harness's name. A
bare `uv run pytest` runs every harness in every configuration.

Keep tests deterministic and focused on behavior visible at the module's ports,
and use current cocotb APIs: `unit="ns"`, not the deprecated `units="ns"`.

With Verilator, a test can reach the top level's ports only. cocotb would build
with `--public-flat-rw`, which lets tests read and write every signal but stops
Verilator from optimizing the design, so the flow turns it off: a large design
then simulates and builds several times faster. To read an internal signal,
add `/*verilator public_flat_rd*/` to its declaration (`public_flat_rw` to also
write it), or a line such as `public_flat_rd -module "fifo" -var "count"` to
`rtl/verilator.vlt`. Other simulators ignore the comment. Waveforms and
coverage include every signal either way.

To split a module's tests across files, put them in `test_<module>__<variant>.py`
files that hold only `@cocotb.test()` functions, and have the harness in
`test_<module>.py` pass their sorted names (e.g. from
`glob("test_<module>__*.py")`) as `test_module`: they then build once and share
one summary. These filename variants only group tests; they have nothing to do
with the named HDL configurations.

## Named HDL configurations

`tests/cocotb_configs.py` maps each DUT's configuration names to top-level
parameter values. It must stay import-safe: the flow reads it without a
simulator.

```python
HDL_CONFIGS = {
    "top": {
        "width4": {"WIDTH": 4},
        "width8": {"WIDTH": 8},
    },
}
```

`config_params` turns a DUT's entry into its harness's parameters; a DUT without
one has a single configuration, `default`, with no overrides. A test reads the
value that its build used with `active_parameter("WIDTH", 8)`: the runner
exports the configuration as `COCOTB_CONFIG` and each parameter as
`COCOTB_PARAM_<name>`.

## Assertions

`rtl/top.sv` `` `include ``s `rtl/top_abv.sv`, its SVA assertions, cover
properties and covergroup, under `` `ifdef ABV ``: `ABV=1` enables them, and
`make coverage` always does. Such a file is not a compilation unit: list it in
`rtl/verible.vf` only, and follow the conventions in its header.

## Coverage

`make coverage` runs the tests with coverage and assertions enabled, then reports
each selected configuration's coverage. With Verilator, that is a summary per
coverage type, LCOV data, and an annotated copy of the sources, which marks each
unhit point with `%00`; `make open-coverage-html CONFIG=<name>` writes and opens
LCOV's HTML report for one configuration, and `COVERAGE_HTML=1` makes
`make coverage` write it for each. With `SIM=questa` or `SIM=vcs`,
`make coverage` writes the simulator's own reports, and `make open-coverage`
opens one in the simulator's coverage GUI. `HTML_VIEWER` sets the program that
opens HTML reports (e.g. `wslview`, from wslu, on WSL).

The reports fail on missing data or tool errors, but no simulator's report fails
on a coverage hole. [Tools](tools.md#coverage) compares what each simulator
collects.

## Waveforms

`make waves` runs the tests with waveform dumping, then opens the waveform in the
simulator's viewer; `make open-waves` opens the last one again. Each viewer
loads its layout from `waves/<DUT>.*` when it exists (see
[Tools](tools.md#waveform-viewers); `make help` lists the variables that select
another). With Verilator, the wave targets also open GTKWave's RTLBrowse window,
which annotates the source with the waveform's values; `NO_RTLBROWSE=1` skips
it.

## Build directories

Each DUT, simulator, configuration and instrumentation builds in its own
directory, so switching between them does not rebuild the others:

```text
build/<dut>/<sim>/<config>/normal/
build/<dut>/<sim>/<config>/waves/
build/<dut>/<sim>/<config>/coverage/
build/<dut>/<sim>/<config>/waves-coverage/
```

`<config>` is `default` for a DUT without named configurations. Each directory
also holds its run's waveform, coverage data and reports, which the run deletes
first, so a build that fails leaves no older ones behind. A waveform or coverage
database can also come from a `WAVES=1 HDL_COVERAGE=1` run, in
`waves-coverage/`: `open-waves`, `open-coverage` and `open-coverage-html` then
use the newer of the two and say which, unless `HDL_COVERAGE` (for a waveform)
or `WAVES` (for coverage) selects one. `make waves` and `make coverage` always
open what their own run made.

`BUILD_DIR=<path>` moves the root of this tree. `make clean` removes `build/`,
but not a moved root.
