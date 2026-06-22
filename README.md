# FPGA Project Template

## Contents

- `rtl/top.sv`: a parameterized counter top module.
- `rtl/top_abv.sv`: assertion-based verification examples for `rtl/top.sv`.
- `rtl/sources.vf`: source list.
- `tests/test_top.py`: cocotb tests for `rtl/top.sv`, launched by pytest.
- `tests/coverage_top.py`: Python functional coverage mirroring the SV
  covergroup in `rtl/top_abv.sv`, using cocotb-coverage.
- `flow/`: the build/run/view flow that the Makefile dispatches to:
  `runner.py` (cocotb `build_and_test()`), `simulators.py` and `viewers.py`
  (per-tool profiles), and `cli.py` (the
  command-line entry point the Makefile calls). See
  [Adding a simulator or viewer](#adding-a-simulator-or-viewer).
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `.markdownlint-cli2.yaml`: Markdown linting and autofix configuration.
- `.surfer/config.toml`: Surfer configuration.
- `Makefile`: common commands for formatting, linting, type checking,
  simulation, and waveform viewing.
- `waves/`: reusable per-viewer wave layouts.

Generated simulator artifacts are ignored by Git and should stay under `build/`.

## Quick start

```sh
make sync   # install/update the uv-managed Python environment
make test   # run the full cocotb regression
make lint   # run all lint and type checks
```

The simulation flow is cocotb through pytest. The same handful of targets work
for every tool: pass the simulator as `SIM=<sim>` to `test`, `coverage`,
`open-coverage`, and `open-coverage-html`, and the waveform viewer as
`VIEWER=<viewer>` to `waves` and `open-waves`. Select individual tests by exact
name or regex, and reuse an existing simulator build for faster debug loops
instead of rebuilding. Run `make help` for the full command reference: every
target and override variable, plus the available simulators and viewers, is
documented there.

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
`rtl/top.sv`. It is a bare-SVA fragment that `top.sv` `` `include ``s under
`` `ifdef ABV ``; its header comment explains how it is structured and why it
is a `+verible+` entry in `rtl/sources.vf` rather than a compilation source. A
Python covergroup mirror in `tests/coverage_top.py` (cocotb-coverage) provides
the same functional coverage on simulators that cannot collect SV covergroups,
and must be kept in sync with it.

Enable assertions with `ABV=1` (see `make help`).

## Coverage

`make coverage` runs Verilator with line, toggle, FSM, and `cover property`
coverage, enables `ABV` automatically, and writes an LCOV HTML report; the same
`coverage SIM=<sim>` pattern works for Questa and VCS. See `make help` for the
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

- `flow/simulators.py` defines a `SimulatorProfile` per simulator: its build
  directory and coverage-artifact defaults, the cocotb runner build/test
  arguments, and the `coverage`, `open-coverage`, and `open-coverage-html`
  behavior.
- `flow/viewers.py` defines a `ViewerProfile` per viewer: the `wave_sim` whose
  format it reads, whether it is a live-GUI flow, and the `waves` and
  `open-waves` behavior.
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
a reusable `.do` layout (`waves/top.do`) when present; local install docs are
under `$HOME/altera_lite/25.1std/questa_fse/docs`. Select it with `SIM=questa`
or `VIEWER=questa` (see `make help` for the `QUESTA_WAVE` and `QUESTA_DO`
overrides).

VCS is a commercial, event-based simulator with full SystemVerilog support.
Unlike the Questa Starter Edition it collects SV covergroups,
reports coverage through `urg`, and supports source-linked debug in Verdi. It
records waveforms in Verdi's native FSDB format and loads a reusable restore
file (`waves/top.rc`) when present; waveform viewing and the coverage GUI both
use Verdi, so `vcs` and `verdi` must be on `PATH`. Select it with `SIM=vcs` or
`VIEWER=verdi` (see `make help` for the `VCS_WAVE`, `VERDI_RC`, and `WAVES=0`
overrides).

GTKWave reads Verilator's VCD output and can view and annotate source with
values from the waveform through its RTLBrowse window; the wave targets prepare
that RTL-browser support so signals link back to source, and load a reusable
layout (`waves/top.gtkw`) when present. See `make help` for the `WAVE` and
`GTKWAVE_SAVE` overrides.

Surfer is a fast, modern waveform viewer that reads the same Verilator VCD as
GTKWave; it is still early in development and has fewer features.
`make waves VIEWER=surfer` loads a reusable layout (`waves/top.surf.ron`) when
present (see `make help` for the `WAVE` and `STATE` overrides).

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
| Surfer | 0.7.0 |
| uv | 0.11.8 |
| VCS | W-2024.09-SP2-7 |
| Verdi | W-2024.09-SP2-7 |
| Verible | v0.0-4053-g89d4d98a |
| Verilator | 5.048 |
