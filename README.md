# FPGA Project Template

A small FPGA project template using SystemVerilog, cocotb, Verilator, ModelSim,
Surfer, GTKWave, uv, Ruff, ty, markdownlint-cli2, pytest, and Verible.

## Contents

- `rtl/top.sv`: a parameterized counter/LED-style top module.
- `rtl/top_abv.sv`: optional assertion-based verification examples for
  `rtl/top.sv`.
- `rtl/sources.vf` and `rtl/abv_sources.vf`: source lists consumed by the
  Makefile and cocotb runner.
- `tests/test_top.py`: cocotb tests launched by pytest with Verilator or
  ModelSim.
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `.pre-commit-config.yaml`: local hooks that reuse the repository's lint and
  type-check targets.
- `.markdownlint-cli2.yaml`: Markdown linting and autofix configuration.
- `.surfer/config.toml`: repo-local Surfer configuration.
- `Makefile`: common commands for formatting, linting, type checking,
  simulation, and waveform viewing.
- `waves/top.surf.ron`: reusable Surfer signal list and layout state.
- `waves/top.gtkw`: reusable GTKWave save file.
- `waves/top.do`: reusable ModelSim wave layout.

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
| `make test-modelsim` | Run the same regression with ModelSim |
| `make coverage` | Run Verilator full coverage and generate reports |
| `make waves` | Run tests, then open a fresh waveform in Surfer |
| `make waves-gtkwave` | Run tests, then open a fresh waveform in GTKWave |
| `make waves-modelsim` | Run tests in a live ModelSim GUI |
| `make open-waves` | Open the existing waveform without rerunning tests |

**Quality:**

| Command | Purpose |
| --- | --- |
| `make format` | Format Python, Markdown, and SystemVerilog |
| `make lint` | Run Ruff, ty, Markdown, Verible, and Verilator checks |
| `make help` | Show debug workflow examples |
| `make clean` | Remove generated local artifacts |

The pre-commit hooks call the existing Makefile lint and type-check targets.
They do not run simulation or waveform viewers; use `make test` and the
optional-flow targets for those. See the
[pre-commit documentation](https://pre-commit.com/) for hook usage details.

## Tool installation and Python notes

Install the default external command-line tools before using the main
Verilator/Surfer workflow. Python packages are managed by uv, but Verilator,
Surfer, Verible, and markdownlint-cli2 need to be available on `PATH`. The local
Python version is pinned to `3.13` in `.python-version` because the current
cocotb release does not support Python 3.14.

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| Verilator | Default simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| Verible | SystemVerilog formatting and linting | [Releases](https://github.com/chipsalliance/verible/releases) | [Documentation](https://chipsalliance.github.io/verible/) |
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

Run the ModelSim/Questa flow with the ABV checker included:

```sh
make test-modelsim ABV=1
```

## Coverage

Only the Verilator coverage flow is set up in this template; ModelSim/Questa
coverage requires a paid verification-feature license.

The ABV file includes `cover property` examples. Verilator records these as
user functional coverage points when coverage is enabled.

Run full Verilator coverage, including line, toggle, FSM, and user coverage:

```sh
make coverage
make open-coverage-html
```

`make open-coverage-html` generates an HTML report and opens it in the default
browser. Override the viewer when needed:

```sh
make open-coverage-html HTML_VIEWER=firefox
```

You can also run the simulator with coverage instrumentation without generating
reports:

```sh
make test ABV=1 HDL_COVERAGE=1
```

`make coverage` keeps ABV enabled, so assertions and `cover property` checks run.
Verilator records `cover property` points as user coverage; it does not emit
separate assertion coverage for `assert property` checks.

SystemVerilog covergroups/coverpoints are not included. Verilator 5.048 parses
but ignores covergroup syntax.

## Optional tools

The sections below cover optional simulators and viewers.

### Tool comparison

**Simulators:**

| Tool | Model | ABV | Coverage | Used here for |
| --- | --- | --- | --- | --- |
| Verilator | Cycle-based | Limited | Yes | Default tests, lint, and coverage |
| ModelSim/Questa | Event-based | Paid license | Paid license | Optional vendor-style simulation |

**Waveform viewers:**

| Tool | Inputs | Source browse | Driver trace |
| --- | --- | --- | --- |
| Surfer | VCD, FST, GHW | No | No |
| GTKWave | VCD, FST, GHW | Yes (RTL browser) | No |
| ModelSim/Questa | WLF | Yes | Paid license |

Verilator is the default simulator because it is open-source,
script-friendly, fast, and easy to run in CI. It handles the assertion and
`cover property` examples in this template, but its SystemVerilog
verification-feature support is not complete.

ModelSim/Questa is a commercial simulator with broad SystemVerilog support
and native interactive debug. The free Intel FPGA Starter Edition does not
include the verification features needed for this template's ABV examples,
and is 32-bit so cocotb needs a matching 32-bit Python environment.

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

### ModelSim usage

ModelSim is optional. The Makefile uses cocotb's `questa` runner internally and
keeps ModelSim artifacts separate from Verilator artifacts under
`build/modelsim/`. Install notes are available in these
[Ubuntu ModelSim notes](https://github.com/qsz746/How-to-install-Modelsim-on-ubuntu-22.04/blob/main/README.md);
local documentation for this install is under
`$HOME/intelFPGA/20.1/modelsim_ase/docs`.

Run the same regression with ModelSim:

```sh
make test-modelsim
```

Target-specific ModelSim runs use the same test selection variables:
`TEST`, `TEST_FILTER`, `REBUILD`, and `ABV`.

ModelSim uses its native WLF waveform format. Use `make waves-modelsim` for a
live GUI simulation with source-linked debug. Use `make open-waves-modelsim`
to inspect an existing WLF without rerunning simulation. Driver tracing
(double-clicking a signal to find its RTL driver) requires the Extended
Dataflow license.

Reusable ModelSim wave layouts can be saved as a `.do` file such as
`waves/top.do`. If that file exists, `make waves-modelsim` sources it in the
live GUI after `run -all`, and `make open-waves-modelsim` loads it when opening
an existing WLF. Override the WLF or `.do` path if needed:

```sh
make waves-modelsim MODELSIM_DO=waves/other.do
make open-waves-modelsim MODELSIM_WAVE=build/modelsim/other.wlf MODELSIM_DO=waves/other.do
```

The ModelSim flow defaults to `MODELSIM_ARGS=-voptargs=+acc` for better GUI and
waveform debug visibility. Override ModelSim arguments when needed, or set
`MODELSIM_ARGS=` to run without extra debug access:

```sh
make test-modelsim MODELSIM_ARGS="-voptargs=+acc -64"
make test-modelsim MODELSIM_ARGS=
```

`make open-waves-modelsim` opens an already-generated WLF, so `+acc` cannot add
debug visibility that was not preserved when the WLF was created. For best source
navigation, prefer `make waves-modelsim`.

#### 32-bit ModelSim setup

ModelSim Starter Edition installs are often 32-bit-only. In that
case the simulator, Python interpreter, and cocotb VPI libraries must all be
32-bit. A 32-bit ModelSim runtime cannot load the 64-bit cocotb libraries from
the default uv environment.

The ModelSim target defaults to the legacy 32-bit architecture settings from
cocotb/cocotb#396:

```make
MODELSIM_ARCH ?= i686
MODELSIM_BITS ?= 32
```

The default uv environment in this template is 64-bit, so a 32-bit ModelSim flow
needs a separate 32-bit Python environment with `pytest` and `cocotb` installed
and cocotb's ModelSim libraries built for that environment. If
`.venv-modelsim32/bin/python` exists, `make test-modelsim` uses it automatically.
Point the target at another environment with `MODELSIM_PYTEST`:

```sh
make test-modelsim MODELSIM_PYTEST="/path/to/32-bit/python -m pytest -s"
```

After building a 32-bit Python with pyenv, uv can create the local ModelSim venv
from that external interpreter:

```sh
uv venv --no-managed-python --python "$PYENV_ROOT/versions/3.13.13/bin/python" .venv-modelsim32
uv pip install --python .venv-modelsim32/bin/python pytest cocotb
make test-modelsim MODELSIM_PYTEST=".venv-modelsim32/bin/python -m pytest -s"
```

Confirm the venv and cocotb ModelSim library are 32-bit:

```sh
file .venv-modelsim32/bin/python
file .venv-modelsim32/lib/python3.13/site-packages/cocotb/libs/libcocotbvpi_modelsim.so
```

For a 64-bit Questa/ModelSim installation, use the normal uv environment and
pass `-64` if your installation requires it:

```sh
make test-modelsim MODELSIM_ARGS="-64"
```

## Verified environment

This template was verified on Ubuntu 22.04 with these tool versions:

Python package versions, including cocotb, pre-commit, pytest, Ruff, and ty, are
locked by uv in `uv.lock`.

| Tool | Verified version |
| --- | --- |
| GTKWave | 3.3.127 |
| markdownlint-cli2 | 0.22.1 |
| ModelSim Intel FPGA Starter Edition | 2020.1 |
| Surfer | 0.7.0 |
| uv | 0.11.8 |
| Verible | v0.0-4053-g89d4d98a |
| Verilator | 5.048 |
