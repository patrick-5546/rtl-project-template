# Verify Repository

Run a full verification of this repository: execute every testable function,
audit all documentation for consistency, and suggest cleanup opportunities.

## Phase 1 — Environment setup

Run `make sync` to install/update the Python environment.

## Phase 2 — Lint checks

Run each lint target individually, then the aggregate `make lint`:

- `make py-format-check py-lint py-type`
- `make md-lint`
- `make sv-format-check sv-lint verilator-lint`
- `make lint`

## Phase 3 — Simulation tests (Verilator)

Run the full Verilator regression and all test-selection variants:

- `make test` — all cocotb tests
- `make test ABV=1` — with SVA assertions enabled
- `make test TEST=enable_high_counts` — single-test selection
- `make test TEST_FILTER='enable_.*'` — regex-based filtering
- `make test REBUILD=0` — reuse existing build artifacts

## Phase 4 — Simulation tests (Questa)

Run the Questa regression (block these if Questa is not installed):

- `make test-questa`
- `make test-questa ABV=1`

## Phase 5 — Coverage

- `make coverage` — Verilator full coverage with LCOV HTML report
- `make coverage-questa` — Questa coverage with UCDB and HTML reports

## Phase 6 — Consistency audit

### Code and config

- Cross-check default values for all environment variables (`SIM`,
  `BUILD_DIR`, `REBUILD`, `ABV`, `HDL_COVERAGE`, `NO_COVERGROUPS`,
  `QUESTA_GUI`, `QUESTA_WAVE`, `QUESTA_DO`, `SV_SOURCES_FILE`,
  `COVERAGE_DAT`) between the Makefile and
  `tests/runner.py`.
- Verify every prek hook calls a valid Makefile target and that all
  lint sub-targets are covered.
- Verify `rtl/sources.vf` lists files that exist,
  and every `.sv` file in `rtl/` appears in it.
- Confirm `.gitignore` covers `build/`, `work/`, and transient files.
- Verify SV covergroups in ABV files and their Python mirrors in
  `tests/coverage_*.py` are in sync: same coverpoints, same bins, same
  cross-coverage. Check that bin ranges match (e.g. the SV `MaxCount/4`
  splits correspond to the Python `_MAX_COUNT // 4` splits).

### Documentation cross-checks

- **README vs Makefile**: every target in README exists; every `make help`
  target is documented; variable names, defaults, and descriptions match.
- **README vs source code**: Contents listing, RTL behavior descriptions,
  directory structure, and command examples are accurate.
- **README vs CI**: `ci.yml` targets, tool versions, and cache keys match
  the README "Verified environment" table.
- **copilot-instructions.md vs code**: signal naming conventions, cocotb API
  usage, test file patterns, Python version pin, env-var sync gotcha, and
  `VSIM`/`MODELSIM` guidance are all current.
- **pyproject.toml vs README**: description, Python version, dependencies,
  pytest config, and ruff config are consistent.
- **Inline comments**: spot-check docstrings and comments in `runner.py`,
  `test_top.py`, `top.sv`, and `top_abv.sv` for accuracy.

## Phase 7 — Cleanup suggestions

Suggest (but do not apply without approval) removals for:

- Dead code, unused imports, or unreachable branches.
- Deprecated APIs (cocotb, pytest, GitHub Actions versions).
- Redundant or unreachable Makefile targets.
- Files not referenced by any target, workflow, or source list.
- Unused Python dependencies in `pyproject.toml`.
- Stale or unnecessary configuration.

## Notes

- Run lint and test targets sequentially to avoid build-directory conflicts.
- If Questa is not installed, mark Questa tasks as blocked and continue.
- Fix any inconsistencies found; propose cleanup removals for approval.
