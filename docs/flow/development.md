# Development

How the repository is kept consistent and up to date: its conventions, linting,
CI, and updating dependencies. The flow package itself, its unit tests, and
adding a simulator or viewer are described in
[flow/README.md](../../flow/README.md).

## Conventions

- Run Python tools through uv (`uv run ...`) or the Makefile targets, never bare
  `ruff`/`ty`/`pytest`.
- Do not commit files from `build/`, and do not add new tools unless a change
  needs them.
- `.editorconfig` gives editors each file type's indentation and line endings,
  and `.gitattributes` keeps every text file's line endings LF in Git.
- When behavior changes, update what describes it: a module's specification in
  `docs/design/`, these guides, `make help`, source headers and docstrings.

## Linting and formatting

`make lint` runs every check and `make format` every formatter, by language:

- `py`: Ruff, ty and Pyrefly;
- `sv`: Verible, Verilator, slang and slang-tidy;
- `md`: rumdl;
- `spell`: typos;
- `gha`: actionlint, with shellcheck on the workflow's scripts, and zizmor.

Each language also runs alone as `lint-<lang>` or `format-<lang>`, and each tool
as `<lint|format>-<lang>-<tool>` (e.g. `make lint-sv-slang`). `ENABLE_<TOOL>=0`
drops a tool from the aggregates, and an executable variable points a target at
another build of its tool (e.g. `make lint-sv VERILATOR=/opt/verilator/bin/verilator`);
`make help` lists both.

- Verible lints and formats every `.sv`, `.svh`, `.v` and `.vh` file that Git
  tracks, or would track since `.gitignore` does not ignore it, outside
  `rtl/vendor/`. Git lists a symlinked or submodule IP directory as one entry,
  so Verible never sees its files.
- Nothing lints or formats `rtl/vendor/`, where third-party RTL goes: Verible's
  file list leaves it out, `rtl/verilator.vlt` waives it for Verilator, the
  Makefile's options skip it for slang and slang-tidy, also through a symlinked
  IP directory, and `pyproject.toml` excludes it from the Python, Markdown and
  spelling tools.
- Verilator, slang and slang-tidy lint the RTL with its default parameters, with
  every DUT as a top level, and again for each named HDL configuration that
  overrides them, with that configuration's DUT as the top module: a Verilator
  or slang warning that only one configuration's widths cause still fails
  `make lint`. Like Verilator and the Questa build, slang and slang-tidy
  compile all files as one compilation unit, so a declaration outside any
  module or package in one file is visible in the files after it.
- slang-tidy warnings do not fail `make lint`, but checks configured as errors
  do. The named configuration passes use `--quiet` to hide passing checks
  without hiding findings. With `--quiet`, though, slang-tidy 12.1, which OSS
  CAD Suite has, exits 0 even when a check configured as an error fails
  ([slang#2101](https://github.com/MikePopoloski/slang/issues/2101)), so such a
  failure in only a named configuration does not fail `make lint`; slang 12.2
  fixes that.
- typos skips the viewer layouts and the lockfiles; allow a project's own words
  in `[tool.typos]` in `pyproject.toml`.
- zizmor also runs its online audits when `GH_TOKEN` is set.

## Continuous integration

`.github/workflows/ci.yml` runs on pushes to `main` and on pull requests; a newer
push to a pull request cancels its run in progress. Its jobs can only read the
repository, keep no credentials in their checkouts, pin each action by commit
SHA, have time limits, and fail if `uv.lock` or `mise.lock` is out of date
(`UV_LOCKED`, and mise's `--locked`):

- `lint`: the Python, Markdown, spelling and workflow checks, with zizmor's
  online audits;
- `lint-sv`: Verible, Verilator and slang;
- `flow-tests`: `make test-flow-py`;
- `rtl`: `make test`, again with `WAVES=1`, and `make coverage`, each with
  Verilator. The coverage job also writes the HTML reports with LCOV,
  uploads them and the LCOV data as the `coverage-reports` artifact, and
  summarizes each configuration's coverage by type on the run's summary page.

Each job installs the tools that `mise.lock` pins, uv and OSS CAD Suite among
them, with `jdx/mise-action`, which caches them.

## Updating dependencies

Dependabot (`.github/dependabot.yml`) proposes weekly updates of the locked
Python packages and of the actions that the workflow uses, in one pull request
per ecosystem; each major Python update comes on its own.
Most compromised releases are found and pulled within days, so every update
takes only releases at least a week old: Dependabot waits a week, uv locks only
week-old releases (`exclude-newer` in `pyproject.toml`), and mise upgrades only
to them (`minimum_release_age` in `mise.toml`).

To update by hand, upgrade the locked Python packages with `uv lock --upgrade`,
or one package with `uv lock --upgrade-package <name>`; the next `uv run`
installs them. To take a newer release, such as a security fix, add the package
to `pyproject.toml`'s `[tool.uv.exclude-newer-package]` table with the value
`false` and run `uv lock`; remove the entry once the release is a week old. A
minimum version in `pyproject.toml` must be a week old too, or locking fails.

Dependabot does not update the other tools. `mise.toml` and `mise.lock` pin GNU
Make, uv, Verible, LCOV and OSS CAD Suite: `mise outdated --bump --no-global`
lists their newer releases, and `mise upgrade --bump --no-global` upgrades them
in both files, or only the tools that you name. After editing `mise.toml` by
hand, run `mise lock`. The `env` of `.github/workflows/ci.yml` pins mise.

OSS CAD Suite releases daily, so it always has a newer release: take one for a
newer Verilator, slang or GTKWave, and note the versions that it bundles, which
`make doctor` shows. Its slang is 12.1, which needs the slang-tidy workarounds
for [slang#2100](https://github.com/MikePopoloski/slang/issues/2100) and
[slang#2101](https://github.com/MikePopoloski/slang/issues/2101). Take the
first release whose slang is 12.2 or newer before it is a week old, with
`mise upgrade --bump --no-global --minimum-release-age 0s github:YosysHQ/oss-cad-suite-build`,
and remove the workarounds.

After updating a tool, update the
[verified environment](tools.md#verified-environment) to match its pin;
`make doctor` reports the tools that `mise.toml` pins as verified at those
versions. A cocotb update
can raise the Verilator version that cocotb needs: `make test-flow-py` then
fails until the flow's own minimum, `VerilatorProfile.minimum_version` in
`flow/simulators.py`, is at least that.

Workarounds for upstream bugs are commented where they live, with their issue
and when to remove them; `git grep issues/` lists them.
