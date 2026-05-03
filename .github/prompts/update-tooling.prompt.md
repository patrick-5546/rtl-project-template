# Update project tooling

Use this prompt when changing Python dependencies, uv settings, Makefile targets,
Ruff, ty, Verible, Verilator, ModelSim, or waveform tooling.

## Goal

Update the tooling coherently so local commands remain simple and documented.

## Instructions

1. Inspect `Makefile`, `pyproject.toml`, `.python-version`, `uv.lock`, and
   `README.md` before editing.
2. Prefer updating existing Makefile targets over adding unrelated scripts.
3. Keep Python tools managed through uv.
4. Keep cocotb's Python compatibility in mind. The current project pins local
   uv Python to `3.13` because cocotb 2.0.1 does not support Python 3.14.
5. If Python dependencies change, run `uv sync` so `uv.lock` stays current.
6. Keep these validation surfaces wired together:
   - Ruff format/check for Python.
   - ty for Python type checking.
   - Verible format/lint for SystemVerilog.
   - Verilator `--lint-only --timing -Wall --sv` for RTL linting.
   - pytest/cocotb with Verilator for default simulation.
   - pytest/cocotb with ModelSim through cocotb's `SIM=questa` runner when
     ModelSim support is affected.
7. Update `README.md` when command names, required tools, or workflow behavior
   changes.

## Validation

Run the affected targets. For broad tooling changes, use:

```sh
make format
make lint
make test
```

For dependency changes, also confirm:

```sh
uv sync
```
