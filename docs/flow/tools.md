# Tools

The external tools that the flow runs, how the simulators and viewers compare,
and the versions this template was verified with.

## Installation

`mise install`, as in the [quick start](../../README.md#quick-start), installs
these tools at the versions that `mise.toml` pins and CI uses:

| Tool | Purpose | Documentation |
| --- | --- | --- |
| GNU Make | Runs the flow's targets | [Documentation](https://www.gnu.org/software/make/manual/) |
| uv | Python package manager | [Documentation](https://docs.astral.sh/uv/) |
| OSS CAD Suite | Builds of Verilator, slang and GTKWave, among other open-source EDA tools | [Documentation](https://github.com/YosysHQ/oss-cad-suite-build) |
| Verilator | Simulator and RTL lint-only flow | [Documentation](https://verilator.org/guide/latest/) |
| slang | Strict SystemVerilog frontend (`slang`) and style/synthesis linter (`slang-tidy`) | [Documentation](https://sv-lang.com/) |
| Verible | SystemVerilog formatting and linting | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | [Documentation](https://github.com/linux-test-project/lcov/tree/master/docs/man) |
| GTKWave | Waveform viewer | [Documentation](https://gtkwave.github.io/gtkwave/) |

With mise [activated](https://mise.jdx.dev/getting-started.html#activate-mise)
in your shell, they are on `PATH` anywhere in the checkout; otherwise, run a
target through mise, as in `mise exec -- make test`. uv installs Python and the
locked Python packages, including the Python and Markdown linters, when a target
first runs; `uv sync` does that alone, e.g. for an editor.

mise does not install what Verilator and LCOV need from the system:

- Verilator builds each model with `g++`: on Ubuntu, `build-essential`; on
  macOS, Xcode's Command Line Tools (`xcode-select --install`). Its FST
  waveforms (`WAVES=1`) also need lz4's and zlib's libraries and headers: on
  Ubuntu, `liblz4-dev` and `zlib1g-dev`; on macOS, `brew install lz4`, since
  macOS has zlib.
- LCOV's `lcov` and `genhtml` need the Perl modules Capture::Tiny, DateTime,
  Devel::StackTrace and TimeDate: on Ubuntu, `libcapture-tiny-perl`,
  `libdatetime-perl`, `libdevel-stacktrace-perl` and `libtimedate-perl`.
  macOS's own Perl has them.

OSS CAD Suite is a 0.5 to 0.7 GB download, and about 2 GB once installed. Its
Verilator is a development snapshot from Verilator's master branch, and its
GTKWave is GTKWave 4, which has no release yet and prints harmless GTK warnings
and critical messages.

Without mise, install the tools as you like: the flow runs each one that it
finds on `PATH`, or that its executable variable names (`make help` lists
them). GNU Make must be 4.0 or newer: the Makefile rejects the 3.81 that macOS
ships as `/usr/bin/make`. uv must be 0.9.17 or newer, the first release that
reads the relative `exclude-newer` in `pyproject.toml`.

`make doctor` lists the tools that it finds, with their versions: "verified" is
the version that `mise.toml` pins, "untested" another, "ok" one that `mise.toml`
does not pin, as for OSS CAD Suite's tools, and "error" one older than the flow
needs.

## Simulators

| Tool | Model | Used here for |
| --- | --- | --- |
| Verilator | Cycle-based | Tests, lint, and coverage |
| Questa | Event-based | Vendor-style simulation and coverage |
| VCS | Event-based | Vendor-style simulation and coverage |

Verilator is open source, fast, and easy to run in CI. The flow needs version
5.054 or newer: 5.050 added SV covergroups, and 5.052 and 5.054 fixed several of
their bugs.

Questa (`SIM=questa`) and VCS (`SIM=vcs`) are commercial, with broad
SystemVerilog support and interactive debug. Override Questa's executable with
`VSIM`, not `MODELSIM`: Questa reads `MODELSIM` as the path of a `modelsim.ini`.
VCS reports coverage through `urg`, and Verdi is both its waveform viewer and
its coverage GUI.

## Coverage

| Metric | Verilator | Questa | VCS |
| --- | --- | --- | --- |
| Line / statement | ✅ | ✅ | ✅ |
| Branch / condition / expression | ✅ | ✅ | ✅ |
| Toggle | ✅ | ✅ | ✅ |
| FSM | ✅ | ✅ | ✅ |
| `cover property` | ✅ (aka user) | ✅ (aka directive) | ✅ |
| `assert property` | ❌ (checked only) | ✅ | ✅ |
| Covergroups (SV) | ✅ | ❌ (needs license) | ✅ |

The free Questa Starter Edition does not collect SV covergroups: that needs a
paid `svverification` license.

## Waveform viewers

| Viewer | Simulator | Format | Layout | Source browse | Driver trace |
| --- | --- | --- | --- | --- | --- |
| GTKWave | Verilator | FST | `.gtkw` | Separate window (RTLBrowse) | Somewhat |
| Questa | Questa | WLF | `.do` | Yes | Yes (double-click a signal) |
| Verdi | VCS | FSDB | `.rc` | Yes | Yes (from VCS's `simv.daidir`) |

## Verified environment

The open-source tools were verified on macOS 27 and in CI on Ubuntu 24.04 at the
versions that `mise.toml` and `uv.lock` pin; the pinned OSS CAD Suite bundles the
Verilator, slang and GTKWave below. Questa, VCS and Verdi were verified outside
CI, which cannot run them, at the versions below.

| Tool | Verified version |
| --- | --- |
| OSS CAD Suite | 2026-11-16 |
| GTKWave | 4.0.0-prealpha (git e40ba79) |
| slang | 12.1 |
| Verilator | 5.055-devel (git e0ff8e65b) |
| Questa | 2025.1 |
| VCS | W-2024.09-SP2-7 |
| Verdi | W-2024.09-SP2-7 |
