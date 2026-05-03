# Add or update a SystemVerilog RTL module

Use this prompt when adding a new RTL module or modifying an existing module in
this FPGA project template.

## Goal

Implement the requested SystemVerilog RTL change while preserving the project
style and keeping the standard HDL checks working.

## Instructions

1. Inspect the existing RTL and tests before editing.
2. Put SystemVerilog source files under `rtl/`.
3. Use the project naming conventions:
   - `_i` for inputs.
   - `_o` for outputs.
   - `_ni` for active-low reset inputs.
   - `logic` for ports and internal signals.
4. Prefer parameterized widths when the module is intended to be reusable.
5. Keep reset, enable, and clock behavior explicit and easy to test.
6. If adding a new RTL file that should be linted by default, update
   `SV_SOURCES` in the `Makefile`.
7. Update or add cocotb tests when behavior changes.
8. Do not commit generated files from `build/` or raw waveform outputs.

## Validation

Run the relevant commands after editing:

```sh
make sv-format
make sv-lint
make verilator-lint
make test
```

If the change affects the standard pre-commit checks, also run:

```sh
make pre-commit-run
```

If the change is RTL-only and tests are not affected, explain why `make test`
was not needed.
