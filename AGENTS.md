# Agent instructions

Read `README.md` and `docs/development.md` before changing code, and
`docs/workflows.md` before adding RTL or tests. `make help` is the command
reference, and each source file's header documents its own implementation.

- Run Python tools through `uv run` or the Makefile targets.
- Before finishing, run `make lint` and `make test DUT=all`, plus
  `make test-flow-py` after changing `flow/`. `make doctor` shows which tools
  are installed; if a check's tool is missing, say which checks did not run.
- When behavior changes, update the affected docs, `make help`, source headers
  and docstrings.
