# Copilot instructions for this repository

This is a small FPGA project template using SystemVerilog RTL, cocotb tests,
Verilator simulation, Surfer waveform viewing, uv-managed Python tools, Ruff,
ty, markdownlint-cli2, pytest, and Verible. GTKWave and ModelSim are optional
alternative flows.

## Repository layout

- `rtl/`: SystemVerilog source files. The current top-level module is
  `rtl/top.sv`.
- `tests/`: pytest-launched cocotb tests. The current test entrypoint is
  `tests/test_top.py`.
- `pyproject.toml`: Python dependencies and configuration for uv, pytest, Ruff,
  and ty.
- `.pre-commit-config.yaml`: local hooks that reuse the repository lint and
  type-check targets.
- `.markdownlint-cli2.yaml`: Markdown linting and autofix configuration.
- `.python-version`: uv Python pin. This template uses Python 3.13 because the
  current cocotb release does not support Python 3.14.
- `Makefile`: canonical local commands for formatting, linting, type checking,
  simulation, waveform viewing, and cleanup.
- `build/`: generated simulation artifacts and waveforms. Verilator artifacts
  live under `build/verilator/`; ModelSim artifacts live under `build/modelsim/`.
  Do not commit files from this directory.
- `waves/`: reusable Surfer state files such as `waves/top.surf.ron`; these may
  be committed when they capture useful signal/layout views. Reusable GTKWave
  save files such as `waves/top.gtkw` and ModelSim command files such as
  `waves/top.do` may also be committed.
- `.surfer/config.toml`: repo-local Surfer configuration. Keep it minimal; it
  currently sets cursor snapping and transition value display.

## Preferred commands

Use the existing Makefile targets instead of inventing new one-off commands:

- `make format`: format Python, Markdown, and SystemVerilog.
- `make lint`: run Ruff, ty, Markdown, Verible lint/format checks, and Verilator
  lint-only.
- `make test`: run pytest/cocotb tests with Verilator.
- `make waves`: run tests and open the Verilator waveform in Surfer.
- `make pre-commit-run`: run all configured pre-commit hooks manually.
- `make help`: show common debug workflow examples.
- `make clean`: remove generated local artifacts.

Python tools are installed and run through uv. Prefer `uv run ...` or the
Makefile targets over assuming tools like `ruff`, `ty`, or `pytest` are
globally installed. Python package versions are locked by `uv.lock`; external
tool versions are documented only as a verified environment in `README.md`.
GTKWave and ModelSim are optional alternative
flows documented in `README.md` and the task-specific prompt files.

## SystemVerilog conventions

- Put RTL modules under `rtl/`.
- Use SystemVerilog syntax and keep files compatible with Verible and Verilator.
- Prefer explicit port directions and `logic` signals.
- Use `_i` for inputs, `_o` for outputs, and `_ni` for active-low reset inputs.
- Prefer parameterized widths when it keeps modules reusable without adding
  unnecessary complexity.
- Format with `make sv-format` or `make format`.
- If adding RTL files that need standard checks, update `SV_SOURCES` in the
  `Makefile`.

## cocotb and Python conventions

- Put cocotb tests under `tests/` and launch them through pytest.
- Use Verilator as the default simulator via `SIM=verilator`.
- Keep tests deterministic and focused on externally visible RTL behavior.
- Generate waveforms when useful for debugging, and keep reusable viewer state
  under `waves/`.
- Use modern cocotb APIs, such as `unit="ns"` instead of deprecated
  `units="ns"`.
- Keep Python compatible with `.python-version` and `pyproject.toml`.
- Format and check Python with Ruff and ty through the Makefile targets.

## Validation expectations

After RTL, test, or tooling changes, run the relevant subset of:

- `make format`
- `make lint`
- `make test`
- `make pre-commit-run`

For Markdown-only documentation or prompt changes, a build is not required, but
verify that referenced paths and Makefile targets are accurate.

Do not add new tools, generated artifacts, or broad helper files unless they are
necessary for the requested change.
