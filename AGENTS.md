# Agent instructions

Read `README.md` and `docs/flow/development.md` before changing code,
`docs/flow/workflows.md` before adding RTL or tests, and `flow/README.md`
before changing `flow/`. A module's specification is
`docs/design/<module>.md`: read it before changing the module, and update it
with the RTL. `make help` is the command reference, and each source file's
header documents its own implementation.

- Run Python tools through `uv run` or the Makefile targets.
- Before finishing, run `make lint` and `make test`, plus
  `make test-flow-py` after changing `flow/`. `make doctor` shows which tools
  are installed; if a check's tool is missing, say which checks did not run.
- When behavior changes, update the affected docs, `make help`, source headers
  and docstrings.
