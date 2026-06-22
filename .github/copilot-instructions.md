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
- New test files go in `tests/` as `test_<module>.py`. Import `build_and_test`
  from `flow.runner` and add a one-line pytest entry point:
  `build_and_test(hdl_toplevel="<module>", test_module=Path(__file__).stem)`.

### Coverage

- SV covergroups (e.g. in `rtl/top_abv.sv`) and their Python mirrors in
  `tests/coverage_*.py` must stay in sync. When adding, removing, or modifying
  coverpoints or bins in one, update the other to match.
- `cocotb-coverage` does not support keyword arguments in sampling function
  calls; always use positional arguments.

## Gotchas

- Run Python tools through uv (`uv run ...`) or the Makefile targets, never bare
  `ruff`/`ty`/`pytest`.
- Override the Questa GUI executable with `VSIM`, not `MODELSIM`; Questa treats
  `MODELSIM` as a `modelsim.ini` environment variable.
- Build/test configuration is read from environment variables: shared defaults
  (e.g. `SIM`, `REBUILD`, `ABV`) come from `flow/runner.py`'s `build_and_test`,
  and simulator-specific defaults (build dir, coverage-artifact path, build/test
  args) from the matching `SimulatorProfile` in `flow/simulators.py`. The
  `Makefile` only selects `SIM`/`VIEWER` and forwards command-line overrides
  through the environment.
- Do not commit files from `build/`, and do not add new tools unless necessary
  for the requested change.
- When you change behavior, check whether the README, `make help`, source
  headers, or docstrings need updating too.
