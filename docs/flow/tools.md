# Tools

The external tools that the flow runs, how the simulators and viewers compare,
and the versions this template was verified with.

## Installation

Install the tools that you plan to use and put them on `PATH`:

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| GNU Make | Runs the flow's targets | mise | [Documentation](https://www.gnu.org/software/make/manual/) |
| mise | Installs GNU Make, uv, Verible, LCOV and OSS CAD Suite | [Getting started](https://mise.jdx.dev/getting-started.html) | [Documentation](https://mise.jdx.dev/) |
| uv | Python package manager | mise | [Documentation](https://docs.astral.sh/uv/) |
| OSS CAD Suite | Builds of Verilator, slang and GTKWave, among other open-source EDA tools | mise | [Documentation](https://github.com/YosysHQ/oss-cad-suite-build) |
| Verilator | Simulator and RTL lint-only flow | mise (OSS CAD Suite) | [Documentation](https://verilator.org/guide/latest/) |
| slang | Strict SystemVerilog frontend (`slang`) and style/synthesis linter (`slang-tidy`) | mise (OSS CAD Suite) | [Documentation](https://sv-lang.com/) |
| Verible | SystemVerilog formatting and linting | mise | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | mise | [Documentation](https://github.com/linux-test-project/lcov/tree/master/docs/man) |
| GTKWave | Waveform viewer | mise (OSS CAD Suite) | [Documentation](https://gtkwave.github.io/gtkwave/) |

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

- GNU Make must be 4.0 or newer: the Makefile rejects the 3.81 that macOS
  ships as `/usr/bin/make`.
- uv must be 0.9.17 or newer, the first release that reads the relative
  `exclude-newer` in `pyproject.toml`. The local Python version is pinned to
  `3.14` in `.python-version`, the newest that the locked cocotb release
  supports; move to Python 3.15 once a cocotb release ships wheels for it.
- LCOV's `lcov` and `genhtml` need the Perl modules Capture::Tiny, DateTime,
  Devel::StackTrace and TimeDate, which mise does not install: on Debian and
  Ubuntu, `libcapture-tiny-perl`, `libdatetime-perl`,
  `libdevel-stacktrace-perl` and `libtimedate-perl`.
- Verilator's FST waveforms (`WAVES=1`) need lz4's library and headers, which
  mise does not install either: on Debian and Ubuntu, `liblz4-dev`; on macOS,
  `brew install lz4`. Apple's compiler does not search Homebrew's prefix on
  Apple silicon, so the flow passes Homebrew's lz4 to Verilator itself.
- OSS CAD Suite releases daily, named by date, and `mise.toml` pins one: each
  release is a 0.5 to 0.7 GB download, and about 2 GB once installed. It builds
  Verilator from its master branch, so its Verilator is a development snapshot
  rather than a release; its slang is the one that Yosys pins, which can trail
  slang's releases; and its GTKWave is GTKWave 4, which has no release yet.
  GTKWave 4's RTLBrowse uses GTK 4, which prints libEGL and MESA warnings and
  renders without the GPU when it cannot use one, as under WSL; they are
  harmless.

The flow runs each tool that it finds on `PATH`, or that its executable variable
names (`make help` lists them), however it was installed. `make doctor` shows
which it finds and its version. A version older than the flow needs is an error,
as is a missing tool that `make test` needs. The version that `mise.toml` pins,
which CI uses, is "verified", and any other "untested"; any version of another
tool, such as Verilator or slang, is "ok". It checks versions only: after
installing or updating a tool, run the flow with it.

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

The open-source tools were verified with these versions on macOS 26 and in CI
on Ubuntu 24.04: `mise.toml` pins them, through the OSS CAD Suite release for
Verilator, slang and GTKWave, and `uv.lock` the Python packages; the `env` of
`.github/workflows/ci.yml` pins mise. Questa, VCS and Verdi were verified
with these versions elsewhere, before later changes to their profiles, and not
since: CI cannot run them, and the flow's unit tests check only the commands
that it gives them.

| Tool | Verified version |
| --- | --- |
| GTKWave | 4.0.0-prealpha (git e40ba79) |
| LCOV | 2.6 |
| Make | 4.4.1 |
| mise | 2026.11.1 |
| OSS CAD Suite | 2026-11-16 |
| Questa | 2025.1 |
| slang | 12.1 |
| uv | 0.13.7 |
| VCS | W-2024.09-SP2-7 |
| Verdi | W-2024.09-SP2-7 |
| Verible | v0.0-4298-g085eef05 |
| Verilator | 5.055-devel (git e0ff8e65b) |
