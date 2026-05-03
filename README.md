# FPGA Project Template

A small FPGA project template using SystemVerilog, cocotb, Verilator, Surfer, uv,
Ruff, ty, pytest, and Verible.

## Contents

- `rtl/top.sv`: a parameterized counter/LED-style top module.
- `tests/test_top.py`: cocotb tests launched by pytest with Verilator.
- `pyproject.toml`: uv-managed Python dependencies and tool configuration.
- `Makefile`: common commands for formatting, linting, type checking, simulation,
  and waveform viewing.

## Quick start

```sh
make sync
make test
make lint
```

The test target runs cocotb through pytest with Verilator as the simulator.

## Common commands

```sh
make format          # Format Python and SystemVerilog
make lint            # Run Ruff, ty, Verible, and Verilator lint-only
make test            # Run cocotb tests with pytest and Verilator
make waves           # Run tests, then open the generated waveform in Surfer
make waves-gtkwave   # Run tests, then open the generated waveform in GTKWave
make clean           # Remove generated local artifacts
```

The default waveform path is `build/sim/dump.vcd`. Generated waveform files are
ignored by Git and should stay under `build/`.

Reusable Surfer state, such as the saved signal list and layout, should be saved
as `waves/top.surf.ron`. That file can be committed so reopening Surfer shows
the same signals. If `waves/top.surf.ron` exists, `make waves` loads it
automatically:

```sh
make waves
```

Override either path if needed:

```sh
make waves WAVE=build/sim/other.vcd STATE=waves/other.surf.ron
```

The repo-local Surfer config in `.surfer/config.toml` sets
`transition_value = "Both"` so placing the cursor exactly on a transition shows
both the previous and next values. The saved Surfer state also stores that
transition display preference. The config sets `snap_distance = 20` so cursor
clicks near signal transitions snap to the transition more reliably. Surfer snaps
against the waveform row under the mouse pointer, not just the currently
selected signal, so click near the transition on that signal's waveform row.

GTKWave is also supported:

```sh
make waves-gtkwave
```

Reusable GTKWave signal/layout state should be saved as `waves/top.gtkw`. If
that file exists, `make waves-gtkwave` loads it automatically. Override either
path if needed:

```sh
make waves-gtkwave WAVE=build/sim/other.vcd GTKWAVE_SAVE=waves/other.gtkw
```

## Tooling notes

The template assumes `uv`, `verilator`, `verible-verilog-lint`,
`verible-verilog-format`, `surfer`, and `gtkwave` are available on `PATH`.
Python tools are installed and invoked through uv. The local Python version is
pinned to `3.13` in `.python-version` because the current cocotb release does
not support Python 3.14.
