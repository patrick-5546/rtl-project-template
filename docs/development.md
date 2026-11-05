# Development

How the flow works and how to change it: the `flow/` package, adding a
simulator or viewer, the conventions that keep the flow consistent, linting, CI,
and updating dependencies.

## The flow package

The Makefile is a thin front end: its test, coverage and waveform targets call
the flow CLI, which runs the cocotb regression through pytest and then the
per-tool coverage and waveform commands.

- `flow/runner.py`: `build_and_test()`, which builds the RTL and runs the cocotb
  tests through cocotb's Python runner, plus the shared defaults and helpers.
- `flow/simulators.py`: a `SimulatorProfile` per simulator: its wave/coverage
  artifact defaults, cocotb runner build/test arguments, post-run wave
  preparation, and coverage behavior.
- `flow/viewers.py`: a `ViewerProfile` per viewer: the `wave_sim` whose format
  it reads and the `open-waves` behavior.
- `flow/cli.py`: the dispatcher the Makefile calls (`python -m flow.cli`).
- `flow/tests/`: the flow's unit tests, which run without any EDA tool.

Each source file's header and docstrings document how it works.

### Adding a simulator or viewer

Tool-specific behavior lives in the profiles, so the generic targets (`test`,
`waves`, `coverage`, ...) stay the same as the tool set grows. To add a
simulator, subclass `SimulatorProfile` in `flow/simulators.py` and register it
in the `SIMULATORS` dict. To add a viewer, subclass `ViewerProfile` in
`flow/viewers.py` and register it in `VIEWERS` (declaring its `wave_sim`).
`make help` lists both automatically, and an unknown `SIM`/`VIEWER` is rejected
with the list of available tools.

## Conventions

- Build and test configuration is read from environment variables. The flow's
  single-source defaults live in `flow/runner.py`: the
  `SIM`/`VIEWER`/`DUT`/`SV_SOURCES_FILE` selectors (`DEFAULT_*`) and the
  `default_*` build-dir/coverage/sources/wave-path helpers shared by `cli.py`,
  `simulators.py`, and `viewers.py`. Per-simulator specifics (build/test args,
  coverage artifact) stay in the matching `SimulatorProfile`. The Makefile
  selects `SIM`/`VIEWER`/`DUT`/`SV_SOURCES_FILE` and passes them to the flow CLI
  as flags; other command-line overrides reach the flow through the environment.
- Run Python tools through uv (`uv run ...`) or the Makefile targets, never bare
  `ruff`/`ty`/`pytest`.
- Do not commit files from `build/`, and do not add new tools unless a change
  needs them.
- When behavior changes, update what describes it: these guides, `make help`,
  source headers and docstrings.

## Linting and formatting

`make lint` runs every linter and type checker, and `make format` every
formatter. Each tool also runs alone as a `<lint|format>-<py|sv|md>-<tool>`
target, grouped per language as `lint-<py|sv|md>` and `format-<py|sv|md>`. Skip
any tool in the aggregates with its `ENABLE_<TOOL>=0` flag (e.g.
`make lint ENABLE_SLANG=0`); its own target stays invokable. Point a target at
another build of a tool with its executable variable (e.g.
`make lint-sv VERILATOR=/opt/verilator/bin/verilator`); `make help` lists them.

## Testing the flow

`make test-flow-py` runs the flow's unit tests in `flow/tests/`. They mock the
EDA tools, so they run anywhere. Normal pytest discovery stays confined to the
RTL tests under `tests/`.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests:

- `lint-sv`: Verible, Verilator and slang, built or downloaded at the pinned
  versions;
- `lint-py` and `lint-md`: the Python and Markdown checks;
- `coverage`: `make coverage-all` with Verilator and LCOV;
- `flow-tests`: `make test-flow-py`.

## Updating dependencies

Upgrade the locked Python packages with `uv lock --upgrade`, or one package with
`uv lock --upgrade-package <name>`; the next `uv run` installs them. The EDA tool
versions that CI uses are pinned in `.github/workflows/ci.yml`.

## cocotb's pytest plugin

cocotb 2.1 added an experimental pytest plugin (`cocotb_tools._pytest`) that
makes each cocotb test a pytest item, with `-k` selection, async fixtures, xdist
parallelism and per-test JUnit reports. The flow stays on cocotb's Python
runners for now: the plugin is a private module whose documentation warns that
its API will change in breaking ways over the next release or two. Revisit it
once it becomes a public, stable API; its `HDL` fixture exposes what the
simulator profiles set (sources, defines, parameters, build and test arguments,
plusargs, waves), so the profiles could feed it.
