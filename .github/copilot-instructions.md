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
- Use Verilator as the default simulator. Questa uses cocotb's `SIM=questa`
  runner internally.
- New test files go in `tests/` as `test_<module>.py`. Import `build_and_test`
  from `runner` and add a one-line pytest entry point:
  `build_and_test(hdl_toplevel="<module>", test_module=Path(__file__).stem)`.

## Gotchas

- Python is pinned to 3.13 (`.python-version`) because cocotb does not support
  3.14.
- Python tools run through uv. Use `uv run ...` or Makefile targets, not bare
  `ruff`/`ty`/`pytest`.
- Override the Questa GUI executable with `VSIM`, not `MODELSIM`; Questa
  treats `MODELSIM` as a `modelsim.ini` environment variable.
- Default values for environment variables (e.g. `SIM`, `BUILD_DIR`, `REBUILD`)
  exist in both the `Makefile` and `tests/runner.py`. Keep them in sync when
  changing a default.
- Do not commit files from `build/` or add new tools unless necessary for the
  requested change.
