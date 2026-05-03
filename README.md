# FPGA Project Template

A small FPGA project template using SystemVerilog, cocotb, Verilator, ModelSim,
Surfer, GTKWave, uv, Ruff, ty, pytest, and Verible.

## Contents

- `rtl/top.sv`: a parameterized counter/LED-style top module.
- `tests/test_top.py`: cocotb tests launched by pytest with Verilator or ModelSim.
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `Makefile`: common commands for formatting, linting, type checking, simulation,
  and waveform viewing.

## Quick start

```sh
make sync
make test
make lint
```

The test target runs cocotb through pytest with Verilator as the default
simulator.

## Common commands

```sh
make format          # Format Python and SystemVerilog
make lint            # Run Ruff, ty, Verible, and Verilator lint-only
make test            # Run cocotb tests and show the cocotb pass/fail summary
make waves           # Run tests, then open the generated waveform in Surfer
make open-waves      # Open the existing waveform in Surfer without rerunning
make help            # Show debug/test workflow examples
make clean           # Remove generated local artifacts
```

## Debugging tests

Run the full regression:

```sh
make test
```

Run one cocotb test by exact test name:

```sh
make test TEST=enable_high_counts
```

Run a subset with a cocotb test-name regular expression:

```sh
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

Generated simulator artifacts are ignored by Git and should stay under `build/`.
The default Verilator flow writes `build/verilator/dump.vcd` for Surfer.

Reusable Surfer state, such as the saved signal list and layout, should be saved
as `waves/top.surf.ron`. That file can be committed so reopening Surfer shows
the same signals. If `waves/top.surf.ron` exists, `make waves` loads it
automatically:

```sh
make waves
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

GTKWave can view the same Verilator VCD used by Surfer:

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

### ModelSim

ModelSim uses cocotb's `questa` runner internally. The Makefile hides that
detail and keeps ModelSim artifacts separate from Verilator artifacts under
`build/modelsim/`.

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

ModelSim is supported through its native WLF waveform format:

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

Intel/Altera ModelSim Starter Edition installs are often 32-bit-only. In that
case the Python interpreter and cocotb VPI libraries must also be 32-bit. The
ModelSim target defaults to the legacy 32-bit architecture settings from
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

## Tooling notes

The template assumes `uv`, `verilator`, `verible-verilog-lint`,
`verible-verilog-format`, `surfer`, `gtkwave`, `vsim`, `vlib`, and `vlog` are
available on `PATH`. Python tools are installed and invoked through uv. The
local Python version is pinned to `3.13` in `.python-version` because the current
cocotb release does not support Python 3.14.

The ModelSim cocotb flow requires simulator, Python, and cocotb VPI library
bitness to match. A 32-bit Intel/Altera ModelSim runtime cannot load the 64-bit
cocotb libraries from the default uv environment.
