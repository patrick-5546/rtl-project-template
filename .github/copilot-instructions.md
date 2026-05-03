# Copilot instructions for this repository

This is a small FPGA project template using SystemVerilog RTL, cocotb tests,
Verilator and ModelSim simulation, Surfer and GTKWave waveform viewing,
uv-managed Python tools, Ruff, ty, pytest, and Verible.

## Repository layout

- `rtl/`: SystemVerilog source files. The current top-level module is
  `rtl/top.sv`.
- `tests/`: pytest-launched cocotb tests. The current test entrypoint is
  `tests/test_top.py`.
- `pyproject.toml`: Python dependencies and configuration for uv, pytest, Ruff,
  and ty.
- `.python-version`: uv Python pin. This template uses Python 3.13 because the
  current cocotb release does not support Python 3.14.
- `Makefile`: canonical local commands for formatting, linting, type checking,
  simulation, waveform viewing, and cleanup.
- `build/`: generated simulation artifacts and waveforms. Verilator artifacts
  live under `build/verilator/`; ModelSim artifacts live under `build/modelsim/`.
  Do not commit files from this directory.
- `waves/`: reusable Surfer state files such as `waves/top.surf.ron`; these may
  be committed when they capture useful signal/layout views. Reusable GTKWave
  save files such as `waves/top.gtkw` may also be committed.
- `.surfer/config.toml`: repo-local Surfer configuration. Keep it minimal; it
  currently sets cursor snapping and transition value display.

## Preferred commands

Use the existing Makefile targets instead of inventing new one-off commands:

- `make format`: format Python and SystemVerilog.
- `make lint`: run Ruff, ty, Verible lint/format checks, and Verilator lint-only.
- `make test`: run pytest/cocotb tests with Verilator.
- `make test TEST=<name>`: run one cocotb test by exact test name.
- `make test TEST_FILTER='<regex>'`: run cocotb tests matching a regular expression.
- `make test REBUILD=0`: reuse an existing simulator build for faster debug loops.
- `make waves`: run tests and open `build/verilator/dump.vcd` in Surfer, loading
  `waves/top.surf.ron` when that state file exists.
- `make waves-gtkwave`: run tests and open `build/verilator/dump.vcd` in GTKWave,
  loading `waves/top.gtkw` when that save file exists.
- `make test-modelsim`: run pytest/cocotb tests with ModelSim using cocotb's
  `SIM=questa` runner. For 32-bit Intel/Altera ModelSim, use a matching 32-bit
  Python/cocotb environment via `MODELSIM_PYTEST`, commonly
  `.venv-modelsim32/bin/python -m pytest -s`.
- `make waves-modelsim`: run ModelSim tests and open `build/modelsim/vsim.wlf`
  with `vsim -view`, loading `waves/top.do` when that file exists.
- `make open-waves`: open an existing waveform in Surfer without rerunning tests.
- `make open-waves-gtkwave`: open an existing waveform in GTKWave without rerunning tests.
- `make open-waves-modelsim`: open an existing ModelSim WLF without rerunning tests.
- `make help`: show common debug workflow examples.
- `make clean`: remove generated local artifacts.

Python tools are installed and run through uv. Prefer `uv run ...` or the
Makefile targets over assuming tools like `ruff`, `ty`, or `pytest` are
globally installed.

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
- Use Verilator as the default simulator via `SIM=verilator`. Use
  `make test-modelsim` for ModelSim; cocotb calls this runner `questa`. The
  ModelSim cocotb flow requires simulator, Python, and cocotb VPI library
  bitness to match. 32-bit Intel/Altera ModelSim needs a matching 32-bit
  Python/cocotb environment, commonly selected with `MODELSIM_PYTEST`.
- Keep tests deterministic and focused on externally visible RTL behavior.
- Prefer cocotb runner selection via `TEST` or `TEST_FILTER` over pytest `-k`,
  because pytest only sees the outer wrapper test.
- Generate waveforms when useful for debugging. Verilator writes
  `build/verilator/dump.vcd`; ModelSim writes `build/modelsim/vsim.wlf`. Save
  reusable Surfer signal/layout state in `waves/top.surf.ron`, reusable GTKWave
  signal/layout state in `waves/top.gtkw`, and reusable ModelSim wave commands
  in `waves/top.do`.
- Use modern cocotb APIs, such as `unit="ns"` instead of deprecated
  `units="ns"`.
- Keep Python compatible with `.python-version` and `pyproject.toml`.
- Format and check Python with Ruff and ty through the Makefile targets.

## Validation expectations

After RTL, test, or tooling changes, run the relevant subset of:

- `make format`
- `make lint`
- `make test`

For Markdown-only documentation or prompt changes, a build is not required, but
verify that referenced paths and Makefile targets are accurate.

Do not add new tools, generated artifacts, or broad helper files unless they are
necessary for the requested change.
