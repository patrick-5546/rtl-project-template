# Copilot instructions for this repository

This is a small FPGA project template. See `README.md` for setup, commands,
and tool details. Run `make help` for a quick reference.

## Conventions

### SystemVerilog

- Use `_i` for inputs, `_o` for outputs, and `_ni` for active-low reset inputs.
- Prefer explicit port directions and `logic` signals.
- Prefer parameterized widths when it keeps modules reusable.
- New RTL files go in `rtl/` and must be added to `rtl/sources.vf`
  (or `rtl/abv_sources.vf` for ABV files).

### cocotb and Python

- Use modern cocotb APIs: `unit="ns"`, not deprecated `units="ns"`.
- Keep tests deterministic and focused on externally visible RTL behavior.
- Use Verilator as the default simulator. ModelSim uses cocotb's `SIM=questa`
  runner internally.

## Gotchas

- Python is pinned to 3.13 (`.python-version`) because cocotb does not support
  3.14.
- Python tools run through uv. Use `uv run ...` or Makefile targets, not bare
  `ruff`/`ty`/`pytest`.
- Override the ModelSim GUI executable with `VSIM`, not `MODELSIM`; ModelSim
  treats `MODELSIM` as a `modelsim.ini` environment variable.
- For 32-bit Intel ModelSim, simulator, Python, and cocotb VPI library bitness
  must all match.
- Do not commit files from `build/` or add new tools unless necessary for the
  requested change.
