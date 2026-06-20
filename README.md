# FPGA Project Template

A FPGA project template using SystemVerilog, cocotb, Verilator, Questa,
GTKWave, Surfer, uv, Ruff, ty, basedpyright, markdownlint-cli2, pytest, and
Verible.

## Contents

- `rtl/top.sv`: a parameterized counter top module.
- `rtl/top_abv.sv`: assertion-based verification examples for `rtl/top.sv`.
- `rtl/sources.vf`: source list consumed by the Makefile and cocotb runner.
- `tests/runner.py`: shared cocotb test runner; provides `build_and_test()` so
  each test file only specifies its DUT.
- `tests/test_top.py`: cocotb tests for `rtl/top.sv`, launched by pytest with
  Verilator or Questa.
- `tests/coverage_top.py`: Python functional coverage mirroring the SV
  covergroup in `rtl/top_abv.sv`, using cocotb-coverage.
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `.markdownlint-cli2.yaml`: Markdown linting and autofix configuration.
- `.surfer/config.toml`: repo-local Surfer configuration.
- `Makefile`: common commands for formatting, linting, type checking,
  simulation, and waveform viewing.
- `waves/top.surf.ron`: reusable Surfer signal list and layout state.
- `waves/top.gtkw`: reusable GTKWave save file.
- `waves/top.do`: reusable Questa wave layout.

Generated simulator artifacts are ignored by Git and should stay under `build/`.

## Quick start

```sh
make sync   # install/update the uv-managed Python environment
make test   # run the full cocotb regression with Verilator
make lint   # run all lint and type checks
```

The default simulation flow is cocotb through pytest with Verilator. Run
`make help` for the full command reference: every target and override variable
is documented there.

## Tool installation and Python notes

Install the default external command-line tools before using the main
Verilator/GTKWave workflow. Python packages are managed by uv, but Verilator,
GTKWave, Verible, slang, LCOV, and markdownlint-cli2 need to be available on
`PATH`. The local Python version is pinned to `3.13` in `.python-version`
because the current cocotb release does not support Python 3.14.

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| Verilator | Default simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| slang | Strict SystemVerilog frontend (`slang`) and style/synthesis linter (`slang-tidy`) | [Build instructions](https://sv-lang.com/building.html) | [Documentation](https://sv-lang.com/) |
| Verible | SystemVerilog formatting and linting | [Releases](https://github.com/chipsalliance/verible/releases) | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | [Releases](https://github.com/linux-test-project/lcov/releases) | [Man pages](https://github.com/linux-test-project/lcov/tree/master/man) |
| markdownlint-cli2 | Markdown linting/autofix | [Install](https://github.com/DavidAnson/markdownlint-cli2#install) | [Documentation](https://github.com/DavidAnson/markdownlint-cli2) |
| GTKWave | Default waveform viewer | [Build from source](https://gtkwave.github.io/gtkwave/install/unix_linux.html#building-and-installing-gtkwave-from-source) | [Documentation](https://gtkwave.github.io/gtkwave/) |
| uv | Python package manager | [Standalone installer](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer) | [Documentation](https://docs.astral.sh/uv/) |

## Default workflow: Verilator and GTKWave

The default simulation flow is cocotb through pytest with Verilator; waveforms
open in GTKWave. Select individual tests by exact name or regex, and reuse an
existing simulator build for faster debug loops instead of rebuilding. The wave
targets also prepare GTKWave's RTL-browser support, so signals link back to
source, and load a reusable signal/layout file (`waves/top.gtkw`) when present.

See `make help` for the `test`, `waves`, and `open-waves` targets and their
`TEST`, `TEST_FILTER`, `REBUILD`, `WAVE`, and `GTKWAVE_SAVE` overrides.

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
`coverage-<sim>` pattern works for Questa. See `make help` for the coverage and
`open-coverage-*` targets and the `HTML_VIEWER` override (e.g. `wslview` on WSL,
which needs wslu).

Neither simulator collects SystemVerilog covergroup data — Verilator parses but
ignores the syntax, and the Questa Starter Edition requires a paid
`svverification` license — so the cocotb-coverage mirror covers this gap on all
simulators. See the [tool comparison](#tool-comparison) for the full breakdown.

## Optional tools

The sections below cover optional simulators and viewers.

### Tool comparison

**Simulators:**

| Tool | Model | Used here for |
| --- | --- | --- |
| Verilator | Cycle-based | Default tests, lint, and coverage |
| Questa | Event-based | Optional vendor-style simulation |

**Coverage breakdown:**

| Metric | Verilator | Questa |
| --- | --- | --- |
| Line / statement | ✅ | ✅ |
| Branch / condition / expression | — | ✅ |
| Toggle | ✅ | ✅ |
| FSM | ✅ | ✅ |
| `cover property` | ✅ (aka user) | ✅ (aka directive) |
| `assert property` | — | ✅ |
| Covergroups (SV) | ❌ (excluded) | ❌ (needs license) |
| Covergroups (cocotb-coverage) | ✅ | ✅ |

**Waveform viewers:**

| Tool | Inputs | Source browse | Driver trace |
| --- | --- | --- | --- |
| GTKWave | VCD, FST, GHW | Yes | Somewhat |
| Surfer | VCD, FST, GHW | No | No |
| Questa | WLF | Yes | Yes |

Verilator is the default simulator because it is open-source,
script-friendly, fast, and easy to run in CI.

Questa is a commercial simulator with broad SystemVerilog support
and native interactive debug. The free Altera Starter Edition does not
include the verification features needed for collecting coverage
on cover groups (aka directives).

GTKWave is the default waveform viewer. Source code can be viewed and
annotated with values from the waveform using the RTLBrowse window.

Surfer is a fast, modern waveform viewer. It is still early in its
development cycle and does not have many features.

### Surfer

Surfer is an optional, modern waveform viewer that reads the same Verilator VCD
as GTKWave. Install it from the
[Surfer install guide](https://docs.surfer-project.org/book/#installing-a-specific-version);
the [user guide](https://docs.surfer-project.org/book/) documents the controls.
`make waves-surfer` loads a reusable layout (`waves/top.surf.ron`) when present.
See `make help` for the Surfer targets and their `WAVE` and `STATE` overrides.

### Questa

Questa is optional. The Makefile drives cocotb's `questa` runner internally and
keeps Questa artifacts under `build/questa/`, separate from Verilator's. It uses
the native WLF format with source-linked debug (double-click a signal to find
its RTL driver), and loads a reusable `.do` layout (`waves/top.do`) when
present. Local install docs are in `$HOME/altera_lite/25.1std/questa_fse/docs`.

See `make help` for the `test-questa`, `waves-questa`, and `open-waves-questa`
targets and their `TEST`, `TEST_FILTER`, `REBUILD`, `ABV`, `QUESTA_WAVE`, and
`QUESTA_DO` overrides.

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
| Verible | v0.0-4053-g89d4d98a |
| Verilator | 5.048 |
