# Tools

The external tools that the flow runs, how the simulators and viewers compare,
and the versions this template was verified with.

## Installation

Install the external command-line tools for the simulators and viewers you plan
to use. uv installs Python and the locked Python packages, including the Python
and Markdown linters, but Verilator, GTKWave, Verible, slang, and LCOV
need to be available on `PATH`. The local Python version is pinned to `3.14` in
`.python-version`, the newest that the locked cocotb release supports; move to
Python 3.15 once a cocotb release ships wheels for it. uv must be 0.9.17 or
newer, the first release that reads the relative `exclude-newer` in
`pyproject.toml`.

`make doctor` shows where the flow finds each tool, honoring the executable
variables that `make help` lists, and the tool's version. A version older than
the flow or cocotb needs is an error, as is a missing tool that `make test`
needs; a version that CI pins is "verified", and any other "untested". It checks
versions only: after installing or updating a tool, run the flow with it.

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| Verilator | Simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| slang | Strict SystemVerilog frontend (`slang`) and style/synthesis linter (`slang-tidy`) | [Build instructions](https://sv-lang.com/building.html) | [Documentation](https://sv-lang.com/) |
| Verible | SystemVerilog formatting and linting | [Releases](https://github.com/chipsalliance/verible/releases) | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | [Releases](https://github.com/linux-test-project/lcov/releases) | [Man pages](https://github.com/linux-test-project/lcov/tree/master/man) |
| GTKWave | Waveform viewer | Distribution package, or [GTKWave 3 source](https://github.com/gtkwave/gtkwave/tree/lts/gtkwave3-gtk3) | [Documentation](https://gtkwave.github.io/gtkwave/) |
| uv | Python package manager | [Standalone installer](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer) | [Documentation](https://docs.astral.sh/uv/) |

LCOV's `lcov` and `genhtml` need the Perl modules Capture::Tiny, DateTime,
Devel::StackTrace and TimeDate: on Debian and Ubuntu, `libcapture-tiny-perl`,
`libdatetime-perl`, `libdevel-stacktrace-perl` and `libtimedate-perl`.

## Simulators

| Tool | Model | Used here for |
| --- | --- | --- |
| Verilator | Cycle-based | Tests, lint, and coverage |
| Questa | Event-based | Vendor-style simulation |
| VCS | Event-based | Vendor-style simulation and coverage |

Verilator is an open-source, cycle-based simulator that is fast,
script-friendly, and easy to run in CI. cocotb needs version 5.036 or newer, and
the flow's coverage 5.048 or newer.

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
values from the waveform through its RTLBrowse window. RTLBrowse needs
`json2stems`, which comes with GTKWave 3.3.125 or newer: Ubuntu 26.04's package
has it, but Ubuntu 24.04's and Debian 13's are older. Without it, skip RTLBrowse
with `NO_RTLBROWSE=1`. GTKWave 4 has no release yet, only pre-alpha builds from
source, so the flow targets GTKWave 3.

Verdi is the waveform viewer and coverage browser for the VCS flow.

## Verified environment

This template was verified with these tool versions, on Ubuntu 26.04 and in CI
on Ubuntu 24.04. CI pins the open-source ones in `.github/workflows/ci.yml`, and
uv locks the Python packages in `uv.lock`.

| Tool | Verified version |
| --- | --- |
| GTKWave | 3.3.126 |
| LCOV | 2.6 |
| Questa | 2025.1 |
| slang | 12.1 |
| uv | 0.13.7 |
| VCS | W-2024.09-SP2-7 |
| Verdi | W-2024.09-SP2-7 |
| Verible | v0.0-4298-g085eef05 |
| Verilator | 5.054 |
