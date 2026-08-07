# FPGA Project Template

## Contents

- `rtl/top.sv`: a parameterized counter top module.
- `rtl/top_abv.sv`: assertion-based verification examples for `rtl/top.sv`.
- `rtl/sources.vf`: compilation source list (the default `SV_SOURCES_FILE`).
- `rtl/verible.vf`: Verible source list.
- `rtl/verilator_waivers.vlt`: Verilator lint/build waiver file
- `tests/test_top.py`: cocotb tests for `rtl/top.sv`, launched by pytest.
- `tests/cocotb_configs.py`: named HDL parameter configurations for `top`.
- `tests/coverage_top.py`: Python functional coverage mirroring the SV
  covergroup in `rtl/top_abv.sv`, using cocotb-coverage.
- `flow/`: the build/run/view flow that the Makefile dispatches to:
  `runner.py` (cocotb `build_and_test()`), `simulators.py` and `viewers.py`
  (per-tool profiles), and `cli.py` (the
  command-line entry point the Makefile calls). See
  [Adding a simulator or viewer](#adding-a-simulator-or-viewer).
  Its isolated unit tests live in `flow/tests/`.
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `.markdownlint-cli2.yaml`: Markdown linting and autofix configuration.
- `.surfer/config.toml`: Surfer configuration.
- `Makefile`: common commands for formatting, linting, type checking,
  simulation, and waveform viewing.
- `waves/`: reusable per-viewer wave layouts, named `<DUT>.*` (e.g. `top.gtkw`).

Generated simulator artifacts are ignored by Git and should stay under `build/`.

## Quick start

```sh
make sync   # install/update the uv-managed Python environment
make test   # run the full cocotb regression
make lint   # run all lint and type checks
```

The simulation flow is cocotb through pytest. Pass the simulator as `SIM=<sim>`
to test, coverage, and waveform targets. Each simulator has a default viewer;
`VIEWER=<viewer>` may select another viewer compatible with `SIM`.

`make test` runs every named configuration for one DUT.
List them with `make configs` and select one with `make test CONFIG=<config>`.
`make test-all` runs every `tests/test_*.py` across all DUTs and verifies that
each configured or unconfigured DUT case executed; pass `DUT=<module>` to
select a DUT for test, wave, and coverage commands.

To split a module's tests across files, put the tests in
`test_<module>__<variant>.py` files and add a `test_<module>.py` aggregator that
runs them together in a single build and end-of-test summary. Filename variants
group cocotb modules; named configurations select HDL parameter values and are
independent of that naming convention. Select individual tests by exact name or
regex, and reuse an existing simulator build for faster debug loops instead of
rebuilding. Point `SV_SOURCES_FILE` at one or more space-separated `.vf`
filelists to compile additional RTL (e.g.
`make test SV_SOURCES_FILE='rtl/sources.vf rtl/extra.vf'`); each filelist is
handed to the simulator with its own `-f`. Run `make help` for the full command
reference: every target and override variable, plus the available simulators and
viewers, is documented there.

Linters and formatters run per tool as `<lint|format>-<py|sv|md>-<tool>`
targets; skip any tool with its `ENABLE_<TOOL>=0` flag (e.g.
`make lint ENABLE_SLANG=0`). Normal pytest discovery remains confined to the
RTL tests under `tests/`; `make test-flow-py` explicitly runs the separate flow
unit tests under `flow/tests/`.

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
`build_and_test(..., variant=variant, parameters=parameters)`. Cocotb test
constants can read the active elaboration with `active_parameter("WIDTH", 8)`.
The runner exports the configuration as `COCOTB_VARIANT` and each parameter as
`COCOTB_PARAM_<name>`.

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
`open-coverage-html WAVES=1`).

## Tool installation and Python notes

Install the external command-line tools for the simulators and viewers you plan
to use. Python packages are managed by uv, but Verilator, GTKWave, Surfer,
Verible, slang, LCOV, and markdownlint-cli2 need to be available on `PATH`. The
local Python version is pinned to `3.13` in `.python-version` because the
current cocotb release does not support Python 3.14.

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| Verilator | Simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| slang | Strict SystemVerilog frontend (`slang`) and style/synthesis linter (`slang-tidy`) | [Build instructions](https://sv-lang.com/building.html) | [Documentation](https://sv-lang.com/) |
| Verible | SystemVerilog formatting and linting | [Releases](https://github.com/chipsalliance/verible/releases) | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | [Releases](https://github.com/linux-test-project/lcov/releases) | [Man pages](https://github.com/linux-test-project/lcov/tree/master/man) |
| markdownlint-cli2 | Markdown linting/autofix | [Install](https://github.com/DavidAnson/markdownlint-cli2#install) | [Documentation](https://github.com/DavidAnson/markdownlint-cli2) |
| GTKWave | Waveform viewer | [Build from source](https://gtkwave.github.io/gtkwave/install/unix_linux.html#building-and-installing-gtkwave-from-source) | [Documentation](https://gtkwave.github.io/gtkwave/) |
| Surfer | Waveform viewer | [Install guide](https://docs.surfer-project.org/book/#installing-a-specific-version) | [User guide](https://docs.surfer-project.org/book/) |
| uv | Python package manager | [Standalone installer](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer) | [Documentation](https://docs.astral.sh/uv/) |

## Assertion-based verification

`rtl/top_abv.sv` holds optional SVA assertions and a covergroup for
`rtl/top.sv`, `` `include ``d under `` `ifdef ABV `` (see its header for the
structure). A Python covergroup mirror in `tests/coverage_top.py`
(cocotb-coverage) provides the same functional coverage on simulators that
cannot collect SV covergroups. Enable assertions with `ABV=1` (see `make help`).

## Coverage

`make coverage CONFIG=<name>` runs Verilator with line, toggle, FSM, and
`cover property` coverage, enables `ABV` automatically, and writes LCOV data;
`make open-coverage-html CONFIG=<name>` generates and opens the HTML report.
The same `coverage SIM=<sim>` pattern works for Questa and VCS. Verilator
coverage requires version 5.048 or newer. See `make help` for the
`coverage`, `open-coverage`, and `open-coverage-html` targets and the
`HTML_VIEWER` override (e.g. `wslview` on WSL, which needs wslu). `open-coverage`
opens a simulator's native GUI coverage viewer where one exists (Questa, and
VCS via Verdi); Verilator has none, so use `open-coverage-html` for it.

Verilator and Questa do not collect SystemVerilog covergroup data — Verilator
parses but ignores the syntax, and the Questa Starter Edition requires a paid
`svverification` license — so the cocotb-coverage mirror covers this gap on
those simulators. VCS collects SV covergroups natively. See the
[tool comparison](#tool-comparison) for the full breakdown.

## Adding a simulator or viewer

Tool-specific behavior lives in the Python `flow/` package, so the generic
targets (`test`, `waves`, `coverage`, ...) stay the same as the tool set grows:

- `flow/simulators.py` defines a `SimulatorProfile` per simulator: its
  wave/coverage artifact defaults, cocotb runner build/test arguments,
  post-run wave preparation, and coverage behavior.
- `flow/viewers.py` defines a `ViewerProfile` per viewer: the `wave_sim` whose
  format it reads and the `open-waves` behavior.
- `flow/cli.py` is the dispatcher the Makefile calls; it runs the cocotb
  regression through pytest and then drives the selected profile.

To add a simulator, subclass `SimulatorProfile` in `flow/simulators.py` and
register it in the `SIMULATORS` dict. To add a viewer, subclass `ViewerProfile`
in `flow/viewers.py` and register it in `VIEWERS` (declaring its `wave_sim`).
`make help` lists both automatically, and an unknown `SIM`/`VIEWER` is rejected
with the list of available tools.

## Tool comparison

**Simulators:**

| Tool | Model | Used here for |
| --- | --- | --- |
| Verilator | Cycle-based | Tests, lint, and coverage |
| Questa | Event-based | Vendor-style simulation |
| VCS | Event-based | Vendor-style simulation and coverage |

**Coverage breakdown:**

| Metric | Verilator | Questa | VCS |
| --- | --- | --- | --- |
| Line / statement | ✅ | ✅ | ✅ |
| Branch / condition / expression | — | ✅ | ✅ |
| Toggle | ✅ | ✅ | ✅ |
| FSM | ✅ | ✅ | ✅ |
| `cover property` | ✅ (aka user) | ✅ (aka directive) | ✅ |
| `assert property` | — | ✅ | ✅ |
| Covergroups (SV) | ❌ (excluded) | ❌ (needs license) | ✅ |
| Covergroups (cocotb-coverage) | ✅ | ✅ | ✅ |

**Waveform viewers:**

| Tool | Inputs | Source browse | Driver trace |
| --- | --- | --- | --- |
| GTKWave | VCD, FST, GHW | Yes | Somewhat |
| Surfer | VCD, FST, GHW | No | No |
| Questa | WLF | Yes | Yes |
| Verdi | FSDB | Yes | Yes |

Verilator is an open-source, cycle-based simulator that is fast,
script-friendly, and easy to run in CI.

Questa is a commercial, event-based simulator with broad SystemVerilog support
and native interactive debug. The free Altera
Starter Edition does not include the verification features needed for collecting
coverage on cover groups (aka directives). Waveforms use the native WLF format
with source-linked debug (double-click a signal to find its RTL driver) and load
a reusable `.do` layout (`waves/<DUT>.do`) when present; local install docs are
under `$HOME/altera_lite/25.1std/questa_fse/docs`. Select it with `SIM=questa`
(which selects the Questa viewer by default; see `make help` for the
`QUESTA_DO` layout override).

VCS is a commercial, event-based simulator with full SystemVerilog support.
Unlike the Questa Starter Edition it collects SV covergroups,
reports coverage through `urg`, and supports source-linked debug in Verdi. It
records waveforms in Verdi's native FSDB format and loads a reusable restore
file (`waves/<DUT>.rc`) when present; waveform viewing and the coverage GUI both
use Verdi, so `vcs` and `verdi` must be on `PATH`. Select it with `SIM=vcs` or
the compatible `VIEWER=verdi` override (see `make help` for the `VERDI_RC` and
`WAVES=0` overrides).

GTKWave reads Verilator's FST output and can view and annotate source with
values from the waveform through its RTLBrowse window; the wave targets prepare
that RTL-browser support so signals link back to source (skip it with
`NO_RTLBROWSE=1`), and load a reusable layout (`waves/<DUT>.gtkw`) when present.
See `make help` for the `GTKWAVE_SAVE` and `NO_RTLBROWSE` overrides.

Surfer is a fast, modern waveform viewer that reads the same Verilator FST as
GTKWave; it is still early in development and has fewer features.
`make waves VIEWER=surfer` loads a reusable layout (`waves/<DUT>.surf.ron`) when
present (see `make help` for the `SURFER_STATE` override).

Verdi is the waveform viewer and coverage browser for the VCS flow. It reads
the FSDB dumped during simulation and the `simv.daidir` knowledge database for
source-linked debug.

## Verified environment

This template was verified on Ubuntu 22.04 with these tool versions:

Python package versions are locked by uv in `uv.lock`.

| Tool | Verified version |
| --- | --- |
| GTKWave | 3.3.127 |
| LCOV | 2.4 |
| markdownlint-cli2 | 0.22.1 |
| Questa | 2025.1 |
| slang | 10.0.0 |
| Surfer | git: 9828710 (between 0.7.0 and 0.8.0) |
| uv | 0.11.8 |
| VCS | W-2024.09-SP2-7 |
| Verdi | W-2024.09-SP2-7 |
| Verible | v0.0-4053-g89d4d98a |
| Verilator | 5.048 |
