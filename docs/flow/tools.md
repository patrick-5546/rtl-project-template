# Tools

The external tools that the flow runs, how the simulators and viewers compare,
and the versions this template was verified with.

## Installation

Install the tools that you plan to use and put them on `PATH`:

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| mise | Installs uv, Verible and LCOV | [Getting started](https://mise.jdx.dev/getting-started.html) | [Documentation](https://mise.jdx.dev/) |
| uv | Python package manager | mise | [Documentation](https://docs.astral.sh/uv/) |
| Verilator | Simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| slang | Strict SystemVerilog frontend (`slang`) and style/synthesis linter (`slang-tidy`) | [Build instructions](https://sv-lang.com/building.html) | [Documentation](https://sv-lang.com/) |
| Verible | SystemVerilog formatting and linting | mise | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | mise | [Man pages](https://github.com/linux-test-project/lcov/tree/master/man) |
| GTKWave | Waveform viewer | [Build instructions](https://gtkwave.github.io/gtkwave/install/unix_linux.html#building-and-installing-gtkwave-from-source) | [Documentation](https://gtkwave.github.io/gtkwave/) |

With mise [activated](https://mise.jdx.dev/getting-started.html#activate-mise)
in your shell, run these in the checkout to install its tools at the versions
that CI uses:

```sh
mise trust
mise install
```

They are then on `PATH` anywhere in the checkout; without activating mise, run
a target through it, as in `mise exec -- make test`. uv installs Python and the
locked Python packages, including the Python and Markdown linters, when a target
first runs; `uv sync` does that alone, e.g. for an editor.

- uv must be 0.9.17 or newer, the first release that reads the relative
  `exclude-newer` in `pyproject.toml`. The local Python version is pinned to
  `3.14` in `.python-version`, the newest that the locked cocotb release
  supports; move to Python 3.15 once a cocotb release ships wheels for it.
- LCOV's `lcov` and `genhtml` need the Perl modules Capture::Tiny, DateTime,
  Devel::StackTrace and TimeDate, which mise does not install: on Debian and
  Ubuntu, `libcapture-tiny-perl`, `libdatetime-perl`,
  `libdevel-stacktrace-perl` and `libtimedate-perl`.
- GTKWave's RTLBrowse window needs `json2stems`, which comes with GTKWave
  3.3.125 or newer: Ubuntu 26.04's package has it, but Ubuntu 24.04's and
  Debian 13's are older. Without it, skip RTLBrowse with `NO_RTLBROWSE=1`.
  GTKWave 4 has no release yet, only pre-alpha builds from source, so the flow
  targets GTKWave 3.

The flow runs each tool that it finds on `PATH`, or that its executable variable
names (`make help` lists them), however it was installed. `make doctor` shows
which it finds and its version. A version older than the flow needs is an error,
as is a missing tool that `make test` needs; the version that CI uses is
"verified", and any other "untested". It checks versions only: after installing
or updating a tool, run the flow with it.

## Simulators

| Tool | Model | Used here for |
| --- | --- | --- |
| Verilator | Cycle-based | Tests, lint, and coverage |
| Questa | Event-based | Vendor-style simulation and coverage |
| VCS | Event-based | Vendor-style simulation and coverage |

Verilator is an open-source, cycle-based simulator that is fast,
script-friendly, and easy to run in CI. The flow needs version 5.054 or newer:
5.050 added SV covergroups, and 5.052 and 5.054 fixed several of their bugs.

Questa (`SIM=questa`) is a commercial, event-based simulator with broad
SystemVerilog support and native interactive debug. Override its executable with
`VSIM`, not `MODELSIM`: Questa reads `MODELSIM` as the path of a
`modelsim.ini`.

VCS (`SIM=vcs`) is a commercial, event-based simulator with full SystemVerilog
support. It reports coverage through `urg`, and Verdi is both its waveform
viewer and its coverage GUI, so `vcs` and `verdi` must be on `PATH`.

## Coverage

| Metric | Verilator | Questa | VCS |
| --- | --- | --- | --- |
| Line / statement | ✅ | ✅ | ✅ |
| Branch / condition / expression | ✅ | ✅ | ✅ |
| Toggle | ✅ | ✅ | ✅ |
| FSM | ✅ | ✅ | ✅ |
| `cover property` | ✅ (aka user) | ✅ (aka directive) | ✅ |
| `assert property` | — | ✅ | ✅ |
| Covergroups (SV) | ✅ | ❌ (needs license) | ✅ |

The free Questa Starter Edition does not collect SV covergroups: that needs a
paid `svverification` license. Verilator compiles its own `verilated_std.sv`
for covergroups, and `rtl/verilator.vlt` keeps it out of the coverage
reports.

## Waveform viewers

| Viewer | Simulator | Format | Layout | Source browse | Driver trace |
| --- | --- | --- | --- | --- | --- |
| GTKWave | Verilator | FST | `waves/<DUT>.gtkw` | Yes (RTLBrowse) | Somewhat |
| Questa | Questa | WLF | `waves/<DUT>.do` | Yes | Yes (double-click a signal) |
| Verdi | VCS | FSDB | `waves/<DUT>.rc` | Yes | Yes (from VCS's `simv.daidir`) |

## Verified environment

The open-source tools were verified with these versions on Ubuntu 26.04 and in
CI on Ubuntu 24.04: `mise.toml` and the `env` of `.github/workflows/ci.yml` pin
them, and `uv.lock` the Python packages. Questa, VCS and Verdi were verified
with these versions elsewhere, before later changes to their profiles, and not
since: CI cannot run them, and the flow's unit tests check only the commands
that it gives them.

| Tool | Verified version |
| --- | --- |
| GTKWave | 3.3.126 |
| LCOV | 2.6 |
| mise | 2026.11.1 |
| Questa | 2025.1 |
| slang | 12.1 |
| uv | 0.13.7 |
| VCS | W-2024.09-SP2-7 |
| Verdi | W-2024.09-SP2-7 |
| Verible | v0.0-4298-g085eef05 |
| Verilator | 5.054 |
