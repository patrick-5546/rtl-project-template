# RTL Project Template

A template for SystemVerilog RTL projects. cocotb tests run through pytest on
Verilator by default, with Questa and VCS profiles; Verible, Verilator and slang
lint and format the RTL; the flow collects code and functional coverage and
opens waveforms with reusable layouts. A Makefile is the front end to a small
Python package, `flow/`, that drives the tools.

## Layout

- `rtl/`: the RTL and its filelists.
  - `top.sv`: a parameterized counter, the example design.
  - `top_abv.sv`: assertions, cover properties and a covergroup for `top.sv`.
  - `sources.vf`: the compilation filelist (the default `SV_SOURCES_FILE`).
  - `verible.vf`: the files that Verible lints and formats.
  - `verilator_waivers.vlt`: Verilator configuration: lint waivers, and the
    coverage exclusion of Verilator's own library.
- `tests/`: the cocotb tests, launched by pytest.
  - `test_top.py`: tests for `top`.
  - `cocotb_configs.py`: named HDL parameter configurations.
- `flow/`: the build, run and view flow that the Makefile calls, with its own
  unit tests in `flow/tests/`.
- `waves/`: reusable waveform layouts, one per viewer, named `<DUT>.*`.
- `docs/`: the guides below.
- `Makefile`, `pyproject.toml` (uv-managed Python dependencies and tool
  settings), and `AGENTS.md` (instructions for coding agents).

Generated artifacts are ignored by Git and stay under `build/`.

## Quick start

Install the external tools first; see [Tools](docs/tools.md). Python and the
locked Python packages need no setup step: every target runs Python through
`uv run`, which creates or updates `.venv` from `uv.lock` first (`uv sync` does
that alone, e.g. for an editor).

```sh
make doctor # check the installed tools and their versions
make test   # run the cocotb regression of every DUT
make lint   # run all lint and type checks
make help   # list every target, override variable and simulator
```

## Documentation

- [Workflows](docs/workflows.md): running tests, adding RTL and tests, named
  configurations, assertions, coverage and waveforms.
- [Tools](docs/tools.md): installing the simulators, linters and viewers, how
  they compare, and the versions this template was verified with.
- [Development](docs/development.md): how `flow/` works, adding a simulator or
  viewer, conventions, linting, CI and updating dependencies.
