# FPGA Project Template

A small FPGA project template using SystemVerilog, cocotb, Verilator, ModelSim,
Surfer, GTKWave, uv, Ruff, ty, pytest, and Verible.

## Contents

- `rtl/top.sv`: a parameterized counter/LED-style top module.
- `tests/test_top.py`: cocotb tests launched by pytest with Verilator or ModelSim.
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `Makefile`: common commands for formatting, linting, type checking, simulation,
  and waveform viewing.

Generated simulator artifacts are ignored by Git and should stay under `build/`.
Reusable waveform viewer state lives under `waves/` and may be committed when it
captures a useful signal list or layout.

| Flow | Generated waveform | Saved view file |
| --- | --- | --- |
| Verilator + Surfer | `build/verilator/dump.vcd` | `waves/top.surf.ron` |
| Verilator + GTKWave | `build/verilator/dump.vcd` | `waves/top.gtkw` |
| ModelSim | `build/modelsim/vsim.wlf` | `waves/top.do` |

## Quick start

```sh
make sync
make test
make lint
```

The default simulation flow is cocotb through pytest with Verilator.

| Command | Purpose |
| --- | --- |
| `make sync` | Install/update the uv-managed Python environment |
| `make test` | Run the full cocotb regression with Verilator |
| `make waves` | Run tests, then open a fresh waveform in Surfer |
| `make open-waves` | Open the existing Surfer waveform without rerunning tests |
| `make format` | Format Python and SystemVerilog |
| `make lint` | Run Ruff, ty, Verible, and Verilator lint-only |
| `make help` | Show debug workflow examples |
| `make clean` | Remove generated local artifacts |

## Tool installation and Python notes

Install the default external command-line tools before using the main
Verilator/Surfer workflow. Python packages are managed by uv, but Verilator,
Surfer, and Verible need to be available on `PATH`. The local Python version is
pinned to `3.13` in `.python-version` because the current cocotb release does
not support Python 3.14.

| Tool | Purpose | Install | Documentation |
| --- | --- | --- | --- |
| Verilator | Default simulator and RTL lint-only flow | [Build instructions](https://verilator.org/guide/latest/install.html#detailed-build-instructions) | [User guide](https://verilator.org/guide/latest/) |
| Verible | SystemVerilog formatting and linting | [Releases](https://github.com/chipsalliance/verible/releases) | [Documentation](https://chipsalliance.github.io/verible/) |
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

The repo-local Surfer config in `.surfer/config.toml` sets
`transition_value = "Both"` so placing the cursor exactly on a transition shows
both the previous and next values. The saved Surfer state also stores that
transition display preference. The config sets `snap_distance = 20` so cursor
clicks near signal transitions snap to the transition more reliably. Surfer snaps
against the waveform row under the mouse pointer, not just the currently
selected signal, so click near the transition on that signal's waveform row.

## Alternative tool flows

The default workflow is Verilator simulation plus Surfer waveform viewing. These
targets provide alternate viewers or simulators when needed.

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

```sh
make test-modelsim TEST=enable_high_counts
make test-modelsim TEST_FILTER='enable_.*'
make test-modelsim TEST=enable_high_counts REBUILD=0
```

ModelSim uses its native WLF waveform format:

```sh
make waves-modelsim
make waves-modelsim TEST=enable_high_counts
make open-waves-modelsim
```

Reusable ModelSim wave layouts can be saved as a `.do` file such as
`waves/top.do`. If that file exists, `make waves-modelsim` and
`make open-waves-modelsim` load it automatically. Override the WLF or `.do` path
if needed:

```sh
make open-waves-modelsim MODELSIM_WAVE=build/modelsim/other.wlf MODELSIM_DO=waves/other.do
```

Override ModelSim arguments when needed:

```sh
make test-modelsim MODELSIM_ARGS="-64 -permit_unmatched_virtual_intf"
```

### 32-bit Intel/Altera ModelSim setup

Intel/Altera ModelSim Starter Edition installs are often 32-bit-only. In that
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

Python package versions, including cocotb, pytest, Ruff, and ty, are locked by
uv in `uv.lock`.

| Tool | Verified version |
| --- | --- |
| GTKWave | 3.3.127 |
| ModelSim Intel FPGA Starter Edition | 2020.1 |
| Surfer | 0.7.0 |
| uv | 0.11.8 |
| Verible | `v0.0-4053-g89d4d98a` |
| Verilator | 5.048 |
