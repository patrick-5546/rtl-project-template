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
  unit tests in `flow/tests/` and its README.
- `waves/`: reusable waveform layouts, one per viewer, named `<DUT>.*`.
- `docs/`: the documentation below: `design/` holds the design's
  specifications, and `flow/` the flow's guides.
- `Makefile`, `pyproject.toml` (uv-managed Python dependencies and tool
  settings), and `AGENTS.md` (instructions for coding agents).

Generated artifacts are ignored by Git and stay under `build/`.

## Quick start

Install the external tools first; see [Tools](docs/flow/tools.md). Python and the
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

The design:

- [top](docs/design/top.md): the example counter's specification. Give each
  module a specification in `docs/design/`.

The flow:

- [Workflows](docs/flow/workflows.md): running tests, adding RTL and tests,
  named configurations, assertions, coverage and waveforms.
- [Tools](docs/flow/tools.md): installing the simulators, linters and
  viewers, how they compare, and the versions this template was verified with.
- [Development](docs/flow/development.md): conventions, linting, CI and
  updating dependencies.
- [flow/README.md](flow/README.md): how the flow package works, its tests, and
  adding a simulator or viewer.
