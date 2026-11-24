# flow

The Python package that the Makefile's test, coverage and waveform targets
call. Its CLI runs the cocotb regression through pytest, and then each
simulator's coverage reports and each viewer's waveform commands.

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
- `stems.py`: the stems that GTKWave's RTLBrowse reads, written from
  Verilator's design tree; a port of GTKWave 3's `json2stems`.
- `cli.py`: the dispatcher the Makefile calls (`python -m flow.cli`).
- `doctor.py`: the `make doctor` report of the external tools and their
  versions.
- `tests/`: the flow's unit tests, which run without any EDA tool.

Each module's header and docstrings document how it works.

## Adding a simulator or viewer

Tool-specific behavior lives in the profiles, so the generic targets (`test`,
`waves`, `coverage`, ...) stay the same as the tool set grows. Add a
simulator's profile to `simulators.py` and its viewer's to `viewers.py`, as
their headers describe, and list its executables in `GROUPS` in `doctor.py`, so
that `make doctor` reports them.

## Testing the flow

`make test-flow-py` runs the flow's unit tests in `tests/`, which mock the EDA
tools, so they run anywhere; a bare `pytest` runs only the RTL tests. In both, a
warning fails the test that raises it. Some of the flow's tests catch drift
between the code and `make help` or the docs.

## cocotb's pytest plugin

cocotb 2.1 added an experimental pytest plugin (`cocotb_tools._pytest`) that
makes each cocotb test a pytest item, with `-k` selection, async fixtures, xdist
parallelism and per-test JUnit reports. The flow stays on cocotb's Python
runners for now: the plugin is a private module whose documentation warns that
its API will change in breaking ways over the next release or two. Revisit it
once it becomes a public, stable API; its `HDL` fixture exposes what the
simulator profiles set (sources, defines, parameters, build and test arguments,
plusargs, waves), so the profiles could feed it.
