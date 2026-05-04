# FPGA Project Template

A small FPGA project template using SystemVerilog, cocotb, Verilator, Questa,
Surfer, GTKWave, uv, Ruff, ty, markdownlint-cli2, pytest, and Verible.

## Contents

- `rtl/top.sv`: a parameterized counter/LED-style top module.
- `rtl/top_abv.sv`: optional assertion-based verification examples for
  `rtl/top.sv`.
- `rtl/sources.vf` and `rtl/abv_sources.vf`: source lists consumed by the
  Makefile and cocotb runner.
- `tests/test_top.py`: cocotb tests launched by pytest with Verilator or Questa.
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `.pre-commit-config.yaml`: local hooks that reuse the repository's lint and
  type-check targets.
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
make sync
make pre-commit-install
make test
make lint
```

The default simulation flow is cocotb through pytest with Verilator.

**Setup:**

| Command | Purpose |
| --- | --- |
| `make sync` | Install/update the uv-managed Python environment |
| `make pre-commit-install` | Install the Git pre-commit hook |
| `make pre-commit-run` | Run all pre-commit hooks manually |

**Workflow:**

| Command | Purpose |
| --- | --- |
| `make test` | Run the full cocotb regression with Verilator |
| `make test-questa` | Run the same regression with Questa |
| `make coverage` | Run Verilator full coverage and generate reports |
| `make coverage-questa` | Run Questa coverage and print UCDB report |
| `make waves` | Run tests, then open a fresh waveform in Surfer |
| `make waves-gtkwave` | Run tests, then open a fresh waveform in GTKWave |
| `make waves-questa` | Run tests in a live Questa GUI |
| `make open-waves` | Open the existing waveform without rerunning tests |

**Quality:**

| Command | Purpose |
| --- | --- |
| `make format` | Format Python, Markdown, and SystemVerilog |
| `make lint` | Run Ruff, ty, Markdown, Verible, and Verilator checks |
| `make help` | Show available Makefile targets |
| `make clean` | Remove generated local artifacts |

The pre-commit hooks call the existing Makefile lint and type-check targets.
They do not run simulation or waveform viewers; use `make test` and the
optional-flow targets for those. See the
[pre-commit documentation](https://pre-commit.com/) for hook usage details.

## Tool installation and Python notes

Install the default external command-line tools before using the main
Verilator/Surfer workflow. Python packages are managed by uv, but Verilator,
Surfer, Verible, LCOV, and markdownlint-cli2 need to be available on `PATH`. The
local Python version is pinned to `3.13` in `.python-version` because the current
cocotb release does not support Python 3.14.

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| Verilator | Default simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| Verible | SystemVerilog formatting and linting | [Releases](https://github.com/chipsalliance/verible/releases) | [Documentation](https://chipsalliance.github.io/verible/) |
| LCOV | Coverage HTML report generation | [Releases](https://github.com/linux-test-project/lcov/releases) | [Man pages](https://github.com/linux-test-project/lcov/tree/master/man) |
| markdownlint-cli2 | Markdown linting/autofix | [Install](https://github.com/DavidAnson/markdownlint-cli2#install) | [Documentation](https://github.com/DavidAnson/markdownlint-cli2) |
| Surfer | Default waveform viewer | [Install guide](https://docs.surfer-project.org/book/#installing-a-specific-version) | [User guide](https://docs.surfer-project.org/book/) |
| uv | Python package manager | [Standalone installer](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer) | [Documentation](https://docs.astral.sh/uv/) |

## Default workflow: Verilator and Surfer

Run the full Verilator regression:

```sh
make test
```

Select one test by exact name or regular expression:

```sh
make test TEST=enable_high_counts
make test TEST_FILTER='enable_.*'
```

By default, tests rebuild the simulator before running. For faster debug loops
after a successful build, reuse the existing simulator build:

```sh
make test TEST=enable_high_counts REBUILD=0
```

Use run-then-open targets when you want a fresh waveform:

```sh
make waves TEST=enable_high_counts
```

Use open-only targets when you just want to inspect the existing waveform:

```sh
make open-waves
```

Override either path if needed:

```sh
make waves WAVE=build/verilator/other.vcd STATE=waves/other.surf.ron
```

## Assertion-based verification examples

The optional ABV examples live in `rtl/top_abv.sv`. That file is a standalone
checker module that `rtl/top.sv` instantiates only when the `ABV` define is
enabled, so the default RTL behavior remains unchanged. The checker includes SVA
assertions for reset, enable-low hold, and enable-high increment behavior.

Run the default Verilator regression with assertions enabled:

```sh
make test ABV=1
```

Run lint checks, including the ABV source:

```sh
make lint
```

Run the Questa flow with the ABV checker included:

```sh
make test-questa ABV=1
```

## Coverage

Run full coverage (line, toggle, FSM, and `cover property` user coverage):

```sh
make coverage
make open-coverage-html
```

`make coverage` enables ABV automatically so assertions and `cover property`
checks are included. Override the HTML viewer when needed:

```sh
make open-coverage-html HTML_VIEWER=firefox
```

You can also run with coverage instrumentation without generating reports:

```sh
make test ABV=1 HDL_COVERAGE=1
```

The same `make coverage-<sim>` pattern works for Questa. Both simulators
generate HTML reports; Questa can also open coverage interactively in its GUI
(`make open-coverage-questa`).

Neither simulator supports SystemVerilog covergroups — Verilator parses but
ignores the syntax, and the Questa Starter Edition requires a paid
`svverification` license. See the [tool comparison](#tool-comparison) for a
full coverage breakdown.

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
| Covergroups | ❌ (ignored) | ❌ (needs license) |

**Waveform viewers:**

| Tool | Inputs | Source browse | Driver trace |
| --- | --- | --- | --- |
| Surfer | VCD, FST, GHW | No | No |
| GTKWave | VCD, FST, GHW | Yes | Somewhat |
| Questa | WLF | Yes | Yes |

Verilator is the default simulator because it is open-source,
script-friendly, fast, and easy to run in CI.

Questa is a commercial simulator with broad SystemVerilog support
and native interactive debug. The free Altera Starter Edition does not
include the verification features needed for collecting coverage
on cover groups (aka directives).

Surfer is a fast, modern waveform viewer. It is still early in its
development cycle and does not have many features.

GTKWave is a more comprehensive waveform viewer. Source code can
be viewed and annotated with values from the waveform using the
RTLBrowse window.

### GTKWave

GTKWave is optional and can view the same Verilator VCD used by Surfer. Install
it from the [GTKWave homepage](https://gtkwave.sourceforge.net/); its
[manual](https://gtkwave.sourceforge.net/gtkwave.pdf) documents save files and
viewer controls.

```sh
make waves-gtkwave
make waves-gtkwave TEST=enable_high_counts
make open-waves-gtkwave
```

The GTKWave targets also prepare GTKWave's RTL browser support, so source
browsing is available when using GTKWave's source-navigation menu actions.

Reusable GTKWave signal/layout state should be saved as `waves/top.gtkw`. If
that file exists, `make waves-gtkwave` loads it automatically. Override either
path if needed:

```sh
make waves-gtkwave WAVE=build/verilator/other.vcd GTKWAVE_SAVE=waves/other.gtkw
```

### Questa usage

Questa is optional. The Makefile uses cocotb's `questa` runner internally and
keeps Questa artifacts separate from Verilator artifacts under
`build/questa/`. Local documentation for this install is in
`$HOME/altera_lite/25.1std/questa_fse/docs`.

Run the same regression with Questa:

```sh
make test-questa
```

Target-specific Questa runs use the same test selection variables:
`TEST`, `TEST_FILTER`, `REBUILD`, and `ABV`.

Questa uses its native WLF waveform format. Use `make waves-questa` for a
live GUI simulation with source-linked debug
(double-clicking a signal to find its RTL driver). Use `make open-waves-questa`
to inspect an existing WLF without rerunning simulation.

Reusable Questa wave layouts can be saved as a `.do` file such as
`waves/top.do`. If that file exists, `make waves-questa` sources it in the
live GUI after `run -all`, and `make open-waves-questa` loads it when opening
an existing WLF. Override the WLF or `.do` path if needed:

```sh
make waves-questa QUESTA_DO=waves/other.do
make open-waves-questa QUESTA_WAVE=build/questa/other.wlf QUESTA_DO=waves/other.do
```

## Verified environment

This template was verified on Ubuntu 22.04 with these tool versions:

Python package versions, including cocotb, pre-commit, pytest, Ruff, and ty, are
locked by uv in `uv.lock`.

| Tool | Verified version |
| --- | --- |
| GTKWave | 3.3.127 |
| LCOV | 2.4 |
| markdownlint-cli2 | 0.22.1 |
| Questa | 2025.1 |
| Surfer | 0.7.0 |
| uv | 0.11.8 |
| Verible | v0.0-4053-g89d4d98a |
| Verilator | 5.048 |
