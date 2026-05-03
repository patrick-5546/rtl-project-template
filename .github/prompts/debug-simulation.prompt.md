# Debug a cocotb simulation failure

Use this prompt when tests fail, Verilator or ModelSim errors during build, or
waveform inspection is needed.

## Goal

Reproduce the failure, identify whether the root cause is in RTL, tests, or
tooling, and implement the smallest correct fix.

## Debugging flow

1. Reproduce with the canonical command:

   ```sh
   make test
   ```

   For targeted debug, prefer cocotb selection through the Makefile rather than
   pytest `-k`:

   ```sh
   make test TEST=<cocotb_test_name>
   make test TEST_FILTER='<regex>'
   make test TEST=<cocotb_test_name> REBUILD=0
   ```

2. Read the pytest, cocotb, and simulator output carefully. Preserve the first
   meaningful error rather than chasing later cascading failures.
3. Check whether the failure happened during:
   - Python test collection.
   - Simulator compile/elaboration.
   - cocotb runtime.
   - RTL assertion or expected-value checking.
4. If Verilator waveforms are needed, use the generated
   `build/verilator/dump.vcd` file or run:

   ```sh
   make waves
   ```

   If ModelSim waveforms are needed, use `build/modelsim/vsim.wlf` or run:

   ```sh
   make waves-modelsim
   ```

   `make test-modelsim` uses cocotb's `SIM=questa` runner. Bare
   `make test-modelsim` automatically uses `.venv-modelsim32/bin/python -m pytest -s`
   when that venv exists; override with `MODELSIM_PYTEST` for another
   Python/cocotb environment.

5. Fix the root cause rather than weakening tests or hiding tool errors.
6. After changes, run the relevant subset of:

   ```sh
   make lint
   make test
   ```

## Things to check

- Python compatibility in `pyproject.toml`, especially cocotb's supported Python
  versions.
- cocotb API changes, such as `unit` versus deprecated `units`.
- Verilator warnings treated as failures by the lint-only flow.
- ModelSim/Questa runner issues use `SIM=questa` internally.
- For ModelSim GUI viewing, override the executable with `VSIM`, not `MODELSIM`;
  ModelSim treats `MODELSIM` as a `modelsim.ini` environment variable.
- For 32-bit Intel/Altera ModelSim, simulator, Python, and cocotb VPI library
  bitness must match.
- `SV_SOURCES` in the `Makefile` when new RTL files are added.
- Reset polarity and timing in both RTL and tests.
