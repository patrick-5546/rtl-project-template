# Agent instructions

Read `README.md` and `docs/development.md` before changing code, and
`docs/workflows.md` before adding RTL or tests. `make help` is the command
reference, and each source file's header documents its own implementation.

- Run Python tools through `uv run` or the Makefile targets.
- Before finishing, run `make lint` and `make test-all`, plus `make test-flow-py`
  after changing `flow/`.
- When behavior changes, update the affected docs, `make help`, source headers
  and docstrings.
