# Copilot instructions for this repository

This is a small FPGA project template. See `README.md` for setup, commands,
and tool details. Run `make help` for a quick reference.

## Conventions

### SystemVerilog

- Use `_i` for inputs, `_o` for outputs, and `_ni` for active-low reset inputs.
- Prefer explicit port directions and `logic` signals.
- Prefer parameterized widths when it keeps modules reusable.
- New RTL files go in `rtl/` and must be added to `rtl/sources.vf`.
- For each implication-style (`|->` / `|=>`) `assert property`, also add a
  `cover property` for the bare antecedent (matching any `disable iff` clause)
  so vacuous passes show up as a coverage hole instead of silently passing.

### cocotb and Python

- Use modern cocotb APIs: `unit="ns"`, not deprecated `units="ns"`.
- Keep tests deterministic and focused on externally visible RTL behavior.
- Use Verilator as the default simulator. Questa uses cocotb's `SIM=questa`
  runner internally.
- New test files go in `tests/` as `test_<module>.py`. Import `build_and_test`
  from `runner` and add a one-line pytest entry point:
  `build_and_test(hdl_toplevel="<module>", test_module=Path(__file__).stem)`.

### Coverage

- SV covergroups in ABV files (e.g. `rtl/top_abv.sv`) and their Python mirrors
  in `tests/coverage_*.py` must stay in sync. When adding, removing, or
  modifying coverpoints or bins in one, update the other to match.
- Python covergroups use `cocotb-coverage` (`coverage_section` / `CoverPoint` /
  `CoverCross` decorators) and work on all simulators. SV covergroups only
  work on simulators with full verification support.
- `cocotb-coverage` does not support keyword arguments in sampling function
  calls; always use positional arguments.

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
- Check whether documentation (`README.md`, `make help`, docstrings,
  comments) needs updating when making a change, and update it if so.
