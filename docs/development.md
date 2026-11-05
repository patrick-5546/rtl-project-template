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
- `flow/viewers.py`: a `ViewerProfile` per simulator's waveform viewer: the
  `wave_sim` whose format it reads and the `open-waves` behavior.
- `flow/cli.py`: the dispatcher the Makefile calls (`python -m flow.cli`).
- `flow/doctor.py`: the `make doctor` report of the external tools and their
  versions.
- `flow/tests/`: the flow's unit tests, which run without any EDA tool.

Each source file's header and docstrings document how it works.

### Adding a simulator or viewer

Tool-specific behavior lives in the profiles, so the generic targets (`test`,
`waves`, `coverage`, ...) stay the same as the tool set grows. To add a
simulator, subclass `SimulatorProfile` in `flow/simulators.py` and register it
in the `SIMULATORS` dict. Each simulator has one waveform viewer: to add or
replace one, subclass `ViewerProfile` in `flow/viewers.py`, set its `wave_sim`,
and register it in `VIEWERS`, which is keyed by `wave_sim`. `make help` lists
the simulators automatically, and an unknown `SIM` is rejected with the list of
available simulators. List a new tool's executables in `GROUPS` in
`flow/doctor.py`, so that `make doctor` reports them.

## Conventions

- Build and test configuration is read from environment variables. The flow's
  single-source defaults live in `flow/runner.py`: the
  `SIM`/`DUT`/`SV_SOURCES_FILE` selectors (`DEFAULT_*`) and the
  `default_*` build-dir/coverage/sources/wave-path helpers shared by `cli.py`,
  `simulators.py`, and `viewers.py`. Per-simulator specifics (build/test args,
  coverage artifact) stay in the matching `SimulatorProfile`. The Makefile
  selects `SIM`/`DUT`/`SV_SOURCES_FILE` and passes them to the flow CLI
  as flags; other command-line overrides reach the flow through the environment.
- Run Python tools through uv (`uv run ...`) or the Makefile targets, never bare
  `ruff`/`ty`/`pytest`.
- Do not commit files from `build/`, and do not add new tools unless a change
  needs them.
- `.editorconfig` gives editors each file type's indentation and line endings,
  and `.gitattributes` keeps every text file's line endings LF in Git.
- When behavior changes, update what describes it: these guides, `make help`,
  source headers and docstrings.

## Linting and formatting

`make lint` runs every linter and type checker, the typos spell checker, and
the workflow checks, and `make format` every formatter. Each tool also runs alone
as a `<lint|format>-<lang>-<tool>` target, grouped as `lint-<lang>` and
`format-<lang>`, where `<lang>` is `py`, `sv`, `md`, `spell` for spelling, or
`gha` for the GitHub workflow and local action. Skip
any tool in the aggregates with its `ENABLE_<TOOL>=0` flag (e.g.
`make lint ENABLE_SLANG=0`); its own target stays invocable. Point a target at
another build of a tool with its executable variable (e.g.
`make lint-sv VERILATOR=/opt/verilator/bin/verilator`); `make help` lists them.
typos skips the viewer layouts and `uv.lock`; allow a project's own words in
`[tool.typos]` in `pyproject.toml`. actionlint also runs shellcheck on the
workflow's scripts, and zizmor audits their security, online too when `GH_TOKEN`
is set; `.github/zizmor.yml` says which audit is off and why.

Verilator, slang and slang-tidy lint the RTL once with its default parameters,
then once more for each named HDL configuration that overrides parameters, with
that configuration's DUT as the top module, so a warning that only one
configuration's widths cause still fails `make lint`.

## Testing the flow

`make test-flow-py` runs the flow's unit tests in `flow/tests/`. They mock the
EDA tools, so they run anywhere. Normal pytest discovery stays confined to the
RTL tests under `tests/`. pytest runs in strict mode, and a warning fails the
test that raises it, in both suites. Some of them catch drift: `make help` must
list every target, `ENABLE_*` flag and executable variable, and the docs must
match CI's version pins, the minimum versions, the Python version, and their
own relative links.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests; a newer
push to a pull request cancels its run in progress. Its jobs can only read the
repository, keep no credentials in their checkouts, pin each action by commit
SHA, have time limits, and fail if `uv.lock` is out of date (`UV_LOCKED`):

- `lint`: the Python, Markdown, spelling and workflow checks, with zizmor's
  online audits;
- `lint-sv`: Verible, Verilator and slang;
- `flow-tests`: `make test-flow-py`;
- `rtl`: `make test DUT=all`, again with `WAVES=1`, and `make coverage DUT=all`,
  each with Verilator. The coverage job also writes the HTML reports with LCOV,
  uploads them and the LCOV data as the `coverage-reports` artifact, and
  summarizes each configuration's coverage on the run's summary page.

The local action `.github/actions/setup-eda-tools` builds Verilator and slang,
cached per version and runner image, and downloads Verible and LCOV, checked
against their SHA-256s. The workflow's `env` pins each tool's version and
checksum.

## Updating dependencies

Dependabot (`.github/dependabot.yml`) proposes weekly updates of the locked
Python packages and of the actions that the workflow and its local action use,
in one pull request per ecosystem; each major Python update comes on its own.
Most compromised releases are found and pulled within days, so every update
takes only releases at least a week old: Dependabot waits a week, and uv locks
only week-old releases (`exclude-newer` in `pyproject.toml`).

To update by hand, upgrade the locked Python packages with `uv lock --upgrade`,
or one package with `uv lock --upgrade-package <name>`; the next `uv run`
installs them. To take a newer release, such as a security fix, add the package
to `pyproject.toml`'s `[tool.uv.exclude-newer-package]` table with the value
`false` and run `uv lock`; remove the entry once the release is a week old. A
minimum version in `pyproject.toml` must be a week old too, or locking fails.
python-constraint, which cocotb-coverage needs, stays at 1.3.1: its only newer
release, 1.4.0 from 2018, has just a source archive whose name does not follow
PEP 625, which uv rejects.

Dependabot does not update the EDA tools. The `env` of
`.github/workflows/ci.yml` pins their versions, and the SHA-256s of the Verible
and LCOV archives. To move to a new release, change its version there, and for
Verible or LCOV its checksum, which the release's asset digests list:

```sh
gh api repos/chipsalliance/verible/releases/tags/<tag> --jq '.assets[] | [.name, .digest] | @tsv'
```

Then update the [verified environment](tools.md#verified-environment);
`make doctor` reads the pins from the workflow. A cocotb update can raise the
Verilator version that cocotb needs: `make test-flow-py` then fails until
`COCOTB_MINIMUM_VERILATOR` in `flow/doctor.py` matches it.

## cocotb's pytest plugin

cocotb 2.1 added an experimental pytest plugin (`cocotb_tools._pytest`) that
makes each cocotb test a pytest item, with `-k` selection, async fixtures, xdist
parallelism and per-test JUnit reports. The flow stays on cocotb's Python
runners for now: the plugin is a private module whose documentation warns that
its API will change in breaking ways over the next release or two. Revisit it
once it becomes a public, stable API; its `HDL` fixture exposes what the
simulator profiles set (sources, defines, parameters, build and test arguments,
plusargs, waves), so the profiles could feed it.
