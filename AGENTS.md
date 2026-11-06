# Agent instructions

Before changing code, read `README.md`, and follow the conventions in
`docs/flow/development.md`. Read `docs/flow/workflows.md` before adding RTL or
tests, and `flow/README.md` before changing `flow/`. A module's specification is
`docs/design/<module>.md`: read it before changing the module, and update it with
the RTL. `make help` is the command reference, and each source file's header
documents its own implementation.

Before finishing, run `make lint` and `make test`, plus `make test-flow-py` after
changing `flow/`. `make doctor` shows which tools are installed; if a check's
tool is missing, say which checks did not run.
