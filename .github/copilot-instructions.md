# Copilot instructions for this repository

Small FPGA project template. The `README.md` is the high-level guide, `make
help` is the command reference, and each source file's header documents its own
implementation. This file only lists conventions and gotchas that aren't
obvious from those sources.

## Conventions

### SystemVerilog

- Use `_i` for inputs, `_o` for outputs, and `_ni` for active-low reset inputs.
- Prefer explicit port directions and `logic` signals.
- Prefer parameterized widths when it keeps modules reusable.
- New RTL goes in `rtl/` and must be listed in `rtl/sources.vf` (that file's
  header documents the entry syntax).
- ABV files are bare SVA `` `include ``d under `` `ifdef ABV ``; follow the
  pattern in `rtl/top_abv.sv` (see its header) and add them as `+verible+`
  entries in `rtl/sources.vf`.
- For each implication-style (`|->` / `|=>`) `assert property`, also add a
  `cover property` for the bare antecedent (matching any `disable iff` clause)
  so vacuous passes show up as a coverage hole instead of silently passing.

### cocotb and Python

- Use modern cocotb APIs: `unit="ns"`, not the deprecated `units="ns"`.
- Keep tests deterministic and focused on externally visible RTL behavior.
- Verilator is the default simulator; Questa runs via cocotb's `SIM=questa`
  runner internally.
- New test files go in `tests/` as `test_<module>.py`. Import `build_and_test`
  from `runner` and add a one-line pytest entry point:
  `build_and_test(hdl_toplevel="<module>", test_module=Path(__file__).stem)`.

### Coverage

- SV covergroups (e.g. in `rtl/top_abv.sv`) and their Python mirrors in
  `tests/coverage_*.py` must stay in sync. When adding, removing, or modifying
  coverpoints or bins in one, update the other to match.
- `cocotb-coverage` does not support keyword arguments in sampling function
  calls; always use positional arguments.

### Simulators and viewers

- The generic Make targets (`test`, `waves`, `open-waves`, `coverage`,
  `open-coverage`, `open-coverage-html`) take the tool as `SIM=<sim>` or
  `VIEWER=<viewer>`; tool-specific recipes live in per-tool include files under
  `mk/sim/<sim>.mk` and `mk/wave/<viewer>.mk`.
- Adding a simulator means adding both `mk/sim/<sim>.mk` and a matching
  `SimulatorProfile` in the `tests/runner.py` registry; adding a viewer means
  adding `mk/wave/<viewer>.mk` (which must declare `WAVE_SIM`). Keep the two
  sides of a simulator in sync.

## Gotchas

- Python is pinned to 3.13 (`.python-version`) because cocotb does not support
  3.14.
- Run Python tools through uv (`uv run ...`) or the Makefile targets, never bare
  `ruff`/`ty`/`pytest`.
- Override the Questa GUI executable with `VSIM`, not `MODELSIM`; Questa treats
  `MODELSIM` as a `modelsim.ini` environment variable.
- Build/test env-var defaults are split: shared ones (e.g. `SIM`, `REBUILD`)
  live in the `Makefile`, simulator-specific ones (e.g. `BUILD_DIR`) in
  `mk/sim/<sim>.mk`, and the matching cocotb build/test args in the
  `tests/runner.py` `SIMULATORS` registry; keep them in sync when changing a
  default.
- Do not commit files from `build/`, and do not add new tools unless necessary
  for the requested change.
- When you change behavior, check whether the README, `make help`, source
  headers, or docstrings need updating too.
