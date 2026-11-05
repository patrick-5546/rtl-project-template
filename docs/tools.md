# Tools

The external tools that the flow runs, how the simulators and viewers compare,
and the versions this template was verified with.

## Installation

Install the external command-line tools for the simulators and viewers you plan
to use. uv installs Python and the locked Python packages, including the Python
and Markdown linters, but Verilator, GTKWave, Verible, slang, and LCOV
need to be available on `PATH`. The local Python version is pinned to `3.14` in
`.python-version`, the newest that the locked cocotb release supports; move to
Python 3.15 once a cocotb release ships wheels for it.

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| Verilator | Simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| slang | Strict SystemVerilog frontend (`slang`) and style/synthesis linter (`slang-tidy`) | [Build instructions](https://sv-lang.com/building.html) | [Documentation](https://sv-lang.com/) |
| Verible | SystemVerilog formatting and linting | [Releases](https://github.com/chipsalliance/verible/releases) | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | [Releases](https://github.com/linux-test-project/lcov/releases) | [Man pages](https://github.com/linux-test-project/lcov/tree/master/man) |
| GTKWave | Waveform viewer | [Build from source](https://gtkwave.github.io/gtkwave/install/unix_linux.html#building-and-installing-gtkwave-from-source) | [Documentation](https://gtkwave.github.io/gtkwave/) |
| uv | Python package manager | [Standalone installer](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer) | [Documentation](https://docs.astral.sh/uv/) |

## Simulators

| Tool | Model | Used here for |
| --- | --- | --- |
| Verilator | Cycle-based | Tests, lint, and coverage |
| Questa | Event-based | Vendor-style simulation |
| VCS | Event-based | Vendor-style simulation and coverage |

Verilator is an open-source, cycle-based simulator that is fast,
script-friendly, and easy to run in CI. Its coverage requires version 5.048 or
newer.

Questa is a commercial, event-based simulator with broad SystemVerilog support
and native interactive debug. The free Altera Starter Edition does not include
the verification features needed for collecting coverage on cover groups (aka
directives). Waveforms use the native WLF format with source-linked debug and
load a reusable `.do` layout (`waves/<DUT>.do`) when present; local install docs
are under `$HOME/altera_lite/25.1std/questa_fse/docs`. Select it with
`SIM=questa`. Override its executable with `VSIM`, not `MODELSIM`: Questa reads
`MODELSIM` as the path of a `modelsim.ini`.

VCS is a commercial, event-based simulator with full SystemVerilog support.
Unlike the Questa Starter Edition it collects SV covergroups, reports coverage
through `urg`, and supports source-linked debug in Verdi. It records waveforms
in Verdi's native FSDB format and loads a reusable restore file
(`waves/<DUT>.rc`) when present; waveform viewing and the coverage GUI both use
Verdi, so `vcs` and `verdi` must be on `PATH`. Select it with `SIM=vcs`.

## Coverage

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

The Questa Starter Edition does not collect SystemVerilog covergroup data (that
requires a paid `svverification` license), and the flow excludes covergroups on
Verilator by defining `NO_COVERGROUPS`: Verilator 5.050 and newer collect them,
but their runtime adds Verilator's own `verilated_std.sv` to the coverage report,
and older versions ignore them. The cocotb-coverage mirror covers this gap on
both simulators; VCS collects SV covergroups natively.

## Waveform viewers

| Tool | Simulator | Inputs | Source browse | Driver trace |
| --- | --- | --- | --- | --- |
| GTKWave | Verilator | VCD, FST, GHW | Yes | Somewhat |
| Questa | Questa | WLF | Yes | Yes |
| Verdi | VCS | FSDB | Yes | Yes |

GTKWave reads Verilator's FST output and can view and annotate source with
values from the waveform through its RTLBrowse window.

Verdi is the waveform viewer and coverage browser for the VCS flow.

## Verified environment

This template was verified on Ubuntu 22.04 with these tool versions:

Python package versions are locked by uv in `uv.lock`.

| Tool | Verified version |
| --- | --- |
| GTKWave | 3.3.127 |
| LCOV | 2.4 |
| Questa | 2025.1 |
| slang | 10.0.0 |
| uv | 0.11.8 |
| VCS | W-2024.09-SP2-7 |
| Verdi | W-2024.09-SP2-7 |
| Verible | v0.0-4053-g89d4d98a |
| Verilator | 5.048 |
