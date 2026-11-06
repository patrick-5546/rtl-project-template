# flow

The Python package that the Makefile's test, coverage and waveform targets
call. Its CLI runs the cocotb regression through pytest, and then each
simulator's coverage reports and each viewer's waveform commands. Using the flow
is described in [Workflows](../docs/flow/workflows.md); the repository's
conventions, linting, CI and dependencies in
[Development](../docs/flow/development.md).

## Modules

- `runner.py`: `build_and_test()`, which builds the RTL and runs the cocotb
  tests through cocotb's Python runner, plus the shared defaults and helpers.
- `build_inputs.py`: the files that a build reads, followed through the
  filelists and the files they include, so that `REBUILD=0` rebuilds when
  they change.
- `simulators.py`: a `SimulatorProfile` per simulator: its wave/coverage
  artifact defaults, cocotb runner build/test arguments, post-run wave
  preparation, and coverage behavior.
- `viewers.py`: a `ViewerProfile` per simulator's waveform viewer: the
  `wave_sim` whose format it reads and the `open-waves` behavior.
- `cli.py`: the dispatcher the Makefile calls (`python -m flow.cli`).
- `doctor.py`: the `make doctor` report of the external tools and their
  versions.
- `tests/`: the flow's unit tests, which run without any EDA tool.

Each module's header and docstrings document how it works.

Build and test configuration is read from environment variables. The flow's
single-source defaults live in `runner.py`: the `SIM`/`SV_SOURCES_FILE`
selectors (`DEFAULT_*`) and the `default_*` build-dir/coverage/sources/wave-path
helpers shared by `cli.py`, `simulators.py`, and `viewers.py`. Per-simulator
specifics (build/test args, coverage artifact) stay in the matching
`SimulatorProfile`. The Makefile passes `SIM`, `DUT`, `CONFIG` and
`SV_SOURCES_FILE` to the flow CLI as flags; other command-line overrides reach
the flow through the environment.

## Adding a simulator or viewer

Tool-specific behavior lives in the profiles, so the generic targets (`test`,
`waves`, `coverage`, ...) stay the same as the tool set grows. To add a
simulator, subclass `SimulatorProfile` in `simulators.py` and register it in the
`SIMULATORS` dict. Each simulator has one waveform viewer: to add or replace
one, subclass `ViewerProfile` in `viewers.py`, set its `wave_sim`, and register
it in `VIEWERS`, which is keyed by `wave_sim`. `make help` lists the simulators
automatically, and an unknown `SIM` is rejected with the list of available
simulators. List a new tool's executables in `GROUPS` in `doctor.py`, so that
`make doctor` reports them.

## Testing the flow

`make test-flow-py` runs the flow's unit tests in `tests/`. They mock the EDA
tools, so they run anywhere. Normal pytest discovery stays confined to the RTL
tests in the repository's `tests/`. pytest runs in strict mode, and a warning
fails the test that raises it, in both suites. Some of them catch drift:
`make help` must list every target, `ENABLE_*` flag and executable variable,
and the docs must match CI's version pins, the minimum versions, the Python
version, and their own relative links.

## cocotb's pytest plugin

cocotb 2.1 added an experimental pytest plugin (`cocotb_tools._pytest`) that
makes each cocotb test a pytest item, with `-k` selection, async fixtures, xdist
parallelism and per-test JUnit reports. The flow stays on cocotb's Python
runners for now: the plugin is a private module whose documentation warns that
its API will change in breaking ways over the next release or two. Revisit it
once it becomes a public, stable API; its `HDL` fixture exposes what the
simulator profiles set (sources, defines, parameters, build and test arguments,
plusargs, waves), so the profiles could feed it.
