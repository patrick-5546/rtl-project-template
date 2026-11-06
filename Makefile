# Configuration variables. Override any of these on the command line as
# VAR=value (run `make help` for the common ones). Simulator and waveform-viewer
# behavior -- the build/test/coverage/wave commands and their defaults -- lives
# in the Python `flow/` package, which the sim/wave targets below dispatch to.

# Recipes and parse-time `$(shell ...)` calls run with bash, which fails on the
# first failing command, including inside a pipeline, and on unset variables.
# No suffix rules, which a task runner never needs. flow/tests/test_make.py
# checks for undefined make variables: adding --warn-undefined-variables (or
# --no-builtin-rules) to MAKEFLAGS here would also pass it to the make that
# builds each Verilator model.
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.SUFFIXES:
.DEFAULT_GOAL := help

# Tool executables, overridable as e.g. `make lint VERILATOR=/opt/verilator/bin/verilator`.
UV ?= uv
VERILATOR ?= verilator
VERIBLE_FORMAT ?= verible-verilog-format
VERIBLE_LINT ?= verible-verilog-lint
SLANG ?= slang
SLANG_TIDY ?= slang-tidy

# Per-tool enable flags for the lint/format aggregates. Set any to 0 to drop
# that tool from `lint`/`format` (and the per-language `lint-<lang>` /
# `format-<lang>` groups); the per-tool target itself stays directly invocable.
ENABLE_RUFF ?= 1
ENABLE_TY ?= 1
ENABLE_PYREFLY ?= 1
ENABLE_RUMDL ?= 1
ENABLE_TYPOS ?= 1
ENABLE_ACTIONLINT ?= 1
ENABLE_ZIZMOR ?= 1
ENABLE_VERIBLE ?= 1
ENABLE_VERILATOR ?= 1
ENABLE_SLANG ?= 1
ENABLE_SLANG_TIDY ?= 1

# The flow CLI (flow/cli.py) runs the tests, coverage, and waveform viewers; the
# sim/wave targets below are thin wrappers around it.
FLOW := $(UV) run python -m flow.cli

# Repo root, and the single source of truth for `${PROJECT_ROOT}` -- the anchor
# the SV filelists use so their entries resolve to absolute paths without
# committing a checkout path.
override export PROJECT_ROOT := $(CURDIR)

# File lists. SV_SOURCES_FILE may name several whitespace-separated filelists;
# each is handed -- with its own `-f` -- both to the simulators (via the flow
# package) and to the Verilator/slang lint targets, which read the
# `+incdir+`/`+define+`/source entries straight from the filelist. SV_VERIBLE_FILE
# is the standalone Verible input list, parsed below because Verible takes bare
# file paths rather than a `-f` command file.
SV_SOURCES_FILE ?= rtl/sources.vf
SV_VERIBLE_FILE ?= rtl/verible.vf

# Expand the source filelist(s) into the `-f <file>` flags the lint targets pass
# to Verilator/slang, and validate (here, at parse time) that each filelist
# exists -- mirroring how the flow package hands them to the simulators.
SV_SOURCES_ARGS := $(foreach f,$(SV_SOURCES_FILE),-f $(f))
$(foreach f,$(SV_SOURCES_FILE),$(if $(wildcard $(f)),,$(error SV_SOURCES_FILE: '$(f)' does not resolve to a file)))

# Verible has no `-f` command-file mode, so read its input list into bare file
# paths (dropping `#` comments and blank lines), expand environment variables,
# and validate that the list exists, names at least one file -- Verible passes
# when given no files -- and that each file exists. PROJECT_ROOT is passed
# explicitly because GNU make's parse-time `$(shell ...)` does not inherit
# `export`ed variables (recipe shells do), so `${PROJECT_ROOT}` in the list would
# otherwise expand to empty.
read_sources = $(strip $(shell sed -e 's/[[:space:]]*\#.*//' -e '/^[[:space:]]*$$/d' $(1) | PROJECT_ROOT='$(PROJECT_ROOT)' envsubst))
$(if $(wildcard $(SV_VERIBLE_FILE)),,$(error SV_VERIBLE_FILE: '$(SV_VERIBLE_FILE)' does not resolve to a file))
SV_VERIBLE_INPUTS := $(call read_sources,$(SV_VERIBLE_FILE))
$(if $(SV_VERIBLE_INPUTS),,$(error SV_VERIBLE_FILE: '$(SV_VERIBLE_FILE)' lists no files))
$(foreach src,$(SV_VERIBLE_INPUTS),$(if $(wildcard $(src)),,$(error verible.vf: '$(src)' does not resolve to a file)))

# Tool selection. SIM picks a simulator profile (flow/simulators.py) for the
# test/coverage targets, and the wave targets open that simulator's viewer
# (flow/viewers.py). An unknown SIM is rejected by the flow CLI with the list of
# available simulators. Add a simulator or viewer by registering a profile in
# those modules -- no edits to this Makefile required.
SIM ?= verilator

# Top-level module under test. Unset, test, coverage and configs select every
# module with a tests/test_<module>.py harness, and the commands that open one
# waveform or coverage report use the only one, or ask for DUT. Passed to the
# flow CLI (which forwards it to the cocotb runner and the waveform viewers:
# GTKWave stems and the waves/<DUT>.* layouts) so every command targets the same
# module. CONFIG selects one named HDL configuration of the DUT: test and coverage
# run every configuration of the selected DUTs without it, and the commands that
# open one artifact need it when the DUT has several.
DUT ?=
CONFIG ?=
DUT_ARG = $(if $(strip $(DUT)),--dut '$(DUT)')
CONFIG_ARG = $(if $(strip $(CONFIG)),--config '$(CONFIG)')
TEST_COMMAND = $(FLOW) test --sim $(SIM) $(DUT_ARG) $(CONFIG_ARG) --sources-file '$(SV_SOURCES_FILE)'

# Artifact workflows still post-process simulator output after a failed test.
# Preserve the test status so reporting or viewer errors cannot mask a regression.
define RUN_TEST_AND_POSTPROCESS
	@test_status=0; post_status=0; \
	$(TEST_COMMAND) || test_status=$$?; \
	$(1) || post_status=$$?; \
	if [ "$$test_status" -ne 0 ]; then exit "$$test_status"; fi; \
	exit "$$post_status"
endef

.PHONY: all clean configs coverage doctor format help lint \
	lint-py lint-sv lint-md lint-spell lint-gha format-py format-sv format-md \
	format-py-ruff lint-py-ruff lint-py-ty lint-py-pyrefly \
	format-md-rumdl lint-md-rumdl lint-spell-typos lint-gha-actionlint lint-gha-zizmor \
	format-sv-verible lint-sv-verible lint-sv-verilator lint-sv-slang lint-sv-slang-tidy \
	open-coverage open-coverage-html open-waves \
	test test-flow-py waves

all: lint test

help:
	@echo "Usage: make <target> [VAR=value ...]"
	@echo ""
	@echo "Setup:"
	@echo "  doctor                          Show where each tool is found, and its version"
	@echo ""
	@echo "Test:"
	@echo "  test [SIM=questa]               Run every DUT's cocotb regression, every config"
	@echo "  test DUT=<module>               Run one DUT's regression"
	@echo "  test CONFIG=<name>              Run one named HDL parameter configuration"
	@echo "  configs [DUT=<module>]          List the HDL configurations of every DUT, or one"
	@echo "  test-flow-py                    Run flow unit tests (not RTL/cocotb tests)"
	@echo "  test TEST=enable_high_counts    Run one cocotb test by exact name"
	@echo "  test TEST_FILTER='enable_.*'    Run cocotb tests matching a regex"
	@echo "  test REBUILD=0                  Reuse the Questa/VCS build if its inputs match"
	@echo "  test ABV=1                      Run with SVA assertions enabled"
	@echo "  test ABV=1 HDL_COVERAGE=1       Instrument coverage without a report"
	@echo ""
	@echo "Waveforms:"
	@echo "  waves [SIM=...] [CONFIG=...]    Run tests, then open the simulator's viewer"
	@echo "  open-waves [SIM=...] [CONFIG=...] Open the existing waveform in the viewer"
	@echo ""
	@echo "Coverage:"
	@echo "  coverage [DUT=...] [CONFIG=...] Run coverage, then report each configuration"
	@echo "  open-coverage [SIM=...] [CONFIG=...] Open coverage in the native GUI viewer"
	@echo "  open-coverage-html [SIM=...] [CONFIG=...] Open the coverage HTML report"
	@echo ""
	@echo "Quality:"
	@echo "  lint                            Run every check (py, sv, md, spell, gha)"
	@echo "  lint-<py|sv|md|spell|gha>       Run one group: a language, spelling or workflows"
	@echo "  format                          Format Python, Markdown, and SystemVerilog"
	@echo "  format-<py|sv|md>               Format one language"
	@echo "  all                             Run lint + test"
	@echo "  clean                           Remove generated local artifacts"
	@echo "  help                            Show this message (default target)"
	@echo ""
	@echo "Per-tool quality targets (<lint|format>-<lang>-<tool>):"
	@echo "  lint-py-ruff lint-py-ty lint-py-pyrefly format-py-ruff"
	@echo "  lint-sv-verible lint-sv-verilator lint-sv-slang lint-sv-slang-tidy  format-sv-verible"
	@echo "  lint-md-rumdl  format-md-rumdl  lint-spell-typos  lint-gha-actionlint  lint-gha-zizmor"
	@echo ""
	@echo "Tool enable flags (default 1; set 0 to skip a tool in lint/format):"
	@echo "  ENABLE_RUFF ENABLE_TY ENABLE_PYREFLY ENABLE_RUMDL ENABLE_TYPOS"
	@echo "  ENABLE_ACTIONLINT ENABLE_ZIZMOR"
	@echo "  ENABLE_VERIBLE ENABLE_VERILATOR ENABLE_SLANG ENABLE_SLANG_TIDY"
	@echo ""
	@echo "Tool executables (override as VAR=/path/to/tool; make doctor shows which it finds):"
	@echo "  UV VERILATOR VERILATOR_COVERAGE GENHTML VERIBLE_FORMAT VERIBLE_LINT SLANG SLANG_TIDY"
	@echo "  GTKWAVE JSON2STEMS VSIM VCOVER VCS URG VERDI"
	@echo ""
	@echo "Tool selection:"
	@echo "  SIM=<sim>                       Simulator; available: $$($(FLOW) list-sims | tr '\n' ' ')"
	@echo ""
	@echo "Common variables (override as VAR=value):"
	@echo "  DUT=<module>                    One module (default: every one); available: $$($(FLOW) list-duts | tr '\n' ' ')"
	@echo "  CONFIG=<name>                   Named HDL configuration; run 'make configs'"
	@echo "  SV_SOURCES_FILE='a.vf b.vf'     SystemVerilog filelist(s); space-separated for several"
	@echo "  TEST= / TEST_FILTER=            Select one test by exact name / by regex"
	@echo "  REBUILD=0                       Reuse an unchanged Questa/VCS build (not after RTL edits)"
	@echo "  BUILD_JOBS=<n>                  Parallel build jobs (capped to available CPUs)"
	@echo "  ABV=1                           Enable SVA assertions and cover properties"
	@echo "  HDL_COVERAGE=1                  Enable simulator coverage instrumentation"
	@echo "  WAVES=1 / WAVES=0               Force waveform dump on/off (test: off; waves: on)"
	@echo "  BUILD_DIR=<path>                Relocate the build/ root (the per-DUT tree below it)"
	@echo "  GTKWAVE_SAVE=                   GTKWave save layout"
	@echo "  NO_RTLBROWSE=1                  Skip GTKWave RTLBrowse stem generation"
	@echo "  QUESTA_DO=                      Questa .do layout"
	@echo "  VERDI_RC=                       Verdi layout"
	@echo "  CM_HIER= / ELLIST=              Optional VCS coverage hierarchy / exclusions"
	@echo "  COVERAGE_HTML=1                 coverage also writes Verilator's HTML report (LCOV)"
	@echo "  HTML_VIEWER=wslview             HTML opener (e.g. wslview on WSL)"

# Build the RTL and run the cocotb tests. flow/cli.py sets up the per-simulator
# pytest invocation (the supported cocotb runner path); command-line VAR=value
# overrides (ABV, TEST, TEST_FILTER, REBUILD, ...) reach it through the
# environment, which GNU Make exports automatically.
test:
	$(TEST_COMMAND)

test-flow-py:
	$(UV) run pytest flow/tests

configs:
	$(FLOW) list-configs $(DUT_ARG)

# Where the flow finds each external tool, and its version (flow/doctor.py). The
# report itself runs through uv, so check for uv first.
doctor:
	@command -v $(UV) >/dev/null || { echo "$(UV): command not found; install uv (docs/flow/tools.md)." >&2; exit 127; }
	$(FLOW) doctor

# coverage and waves pin the other instrumentation's flag, so that their report or
# viewer opens the build that this run made, not another mode's older data.
coverage: override export ABV := 1
coverage: override export HDL_COVERAGE := 1
coverage: export WAVES ?= 0
coverage:
	$(call RUN_TEST_AND_POSTPROCESS,$(FLOW) report-coverage --sim $(SIM) $(DUT_ARG) $(CONFIG_ARG))

open-coverage:
	$(FLOW) open-coverage --sim $(SIM) $(DUT_ARG) $(CONFIG_ARG)

open-coverage-html:
	$(FLOW) open-coverage-html --sim $(SIM) $(DUT_ARG) $(CONFIG_ARG)

waves: override export WAVES := 1
waves: export HDL_COVERAGE ?= 0
waves:
	$(FLOW) validate-config $(DUT_ARG) $(CONFIG_ARG)
	$(call RUN_TEST_AND_POSTPROCESS,$(FLOW) open-waves --sim $(SIM) $(DUT_ARG) $(CONFIG_ARG))

open-waves:
	$(FLOW) open-waves --sim $(SIM) $(DUT_ARG) $(CONFIG_ARG)

# Ruff's formatter leaves import order to its linter, so apply that fix first.
format-py-ruff:
	$(UV) run ruff check --select I --fix .
	$(UV) run ruff format .

lint-py-ruff:
	$(UV) run ruff format --check .
	$(UV) run ruff check .

lint-py-ty:
	$(UV) run ty check

lint-py-pyrefly:
	$(UV) run pyrefly check

format-md-rumdl:
	$(UV) run rumdl fmt .

lint-md-rumdl:
	$(UV) run rumdl check .

lint-spell-typos:
	$(UV) run typos

# actionlint also runs shellcheck on the workflow's and the local action's
# scripts. zizmor audits their security, including its online audits when
# GH_TOKEN is set (CI passes the job's token).
lint-gha-actionlint:
	$(UV) run actionlint

lint-gha-zizmor:
	$(UV) run zizmor $(if $(filter undefined,$(origin GH_TOKEN)),--offline) .github

format-sv-verible:
	$(VERIBLE_FORMAT) --inplace $(SV_VERIBLE_INPUTS)

lint-sv-verible:
	@for source in $(SV_VERIBLE_INPUTS); do \
		$(VERIBLE_FORMAT) --verify "$$source" || exit $$?; \
	done
	$(VERIBLE_LINT) $(SV_VERIBLE_INPUTS)

# Verilator and slang lint the RTL once with its default parameters, then once
# more for each named HDL configuration that overrides parameters, with its DUT
# as the top module. `$(call LINT_EACH_CONFIG,<lint command>,<top-module option>)`
# runs those passes; `flow lint-cases` prints them as `<dut> -G<name>=<value>...`.
define LINT_EACH_CONFIG
	@$(FLOW) lint-cases | while read -r dut overrides; do \
		echo "$(1) $(2) $$dut $$overrides $(SV_SOURCES_ARGS)"; \
		$(1) $(2) "$$dut" $$overrides $(SV_SOURCES_ARGS); \
	done
endef

# Modules without a `timescale get the simulators' 1ns/1ps (TIMESCALE in
# flow/simulators.py; a flow test keeps the two equal). Without that default,
# one module that declares it, as vendor RTL often does, makes the linters
# reject every module that does not.
SV_TIMESCALE := 1ns/1ps
# Third-party RTL, in SV_VENDOR_DIR/<ip>/, is compiled as delivered, so it is
# not linted: rtl/verilator.vlt waives it for Verilator, and the options below
# for slang and slang-tidy. slang resolves symlinks, so a symlinked IP's
# resolved path is passed too. The trailing slash keeps slang-tidy's
# --skip-path from skipping the parent directory as well
# (https://github.com/MikePopoloski/slang/issues/2100).
SV_VENDOR_DIR := rtl/vendor
SV_VENDOR_PATHS := $(sort $(realpath $(SV_VENDOR_DIR) $(wildcard $(SV_VENDOR_DIR)/*/)))
# The pass with default parameters names no top module, so each DUT is a top
# level there, which Verilator's MULTITOP warning would reject.
VERILATOR_LINT = $(VERILATOR) --lint-only --timing -Wall -Wno-MULTITOP --timescale $(SV_TIMESCALE) --sv +define+ABV rtl/verilator.vlt
SLANG_OPTIONS = $(strip +define+ABV --timescale $(SV_TIMESCALE) $(foreach path,$(SV_VENDOR_PATHS),--suppress-warnings $(path)/...))
SLANG_LINT = $(SLANG) -Werror $(SLANG_OPTIONS)
SLANG_TIDY_LINT = $(strip $(SLANG_TIDY) $(SLANG_OPTIONS) $(foreach path,$(SV_VENDOR_PATHS),--skip-path $(path)/))

lint-sv-verilator:
	$(VERILATOR_LINT) $(SV_SOURCES_ARGS)
	$(call LINT_EACH_CONFIG,$(VERILATOR_LINT),--top-module)

lint-sv-slang:
	$(SLANG_LINT) $(SV_SOURCES_ARGS)
	$(call LINT_EACH_CONFIG,$(SLANG_LINT),--top)

# The configuration passes print only slang-tidy's findings, not every check's PASS.
lint-sv-slang-tidy:
	$(SLANG_TIDY_LINT) $(SV_SOURCES_ARGS)
	$(call LINT_EACH_CONFIG,$(SLANG_TIDY_LINT) --quiet,--top)

# Per-tool ENABLE_<TOOL> flags select which targets the language aggregates run;
# a disabled tool drops out of `lint`/`format` but its target stays invocable.
LINT_PY_TARGETS :=
FORMAT_PY_TARGETS :=
ifeq ($(ENABLE_RUFF),1)
LINT_PY_TARGETS += lint-py-ruff
FORMAT_PY_TARGETS += format-py-ruff
endif
ifeq ($(ENABLE_TY),1)
LINT_PY_TARGETS += lint-py-ty
endif
ifeq ($(ENABLE_PYREFLY),1)
LINT_PY_TARGETS += lint-py-pyrefly
endif

LINT_MD_TARGETS :=
FORMAT_MD_TARGETS :=
ifeq ($(ENABLE_RUMDL),1)
LINT_MD_TARGETS += lint-md-rumdl
FORMAT_MD_TARGETS += format-md-rumdl
endif

LINT_SPELL_TARGETS :=
ifeq ($(ENABLE_TYPOS),1)
LINT_SPELL_TARGETS += lint-spell-typos
endif

LINT_GHA_TARGETS :=
ifeq ($(ENABLE_ACTIONLINT),1)
LINT_GHA_TARGETS += lint-gha-actionlint
endif
ifeq ($(ENABLE_ZIZMOR),1)
LINT_GHA_TARGETS += lint-gha-zizmor
endif

LINT_SV_TARGETS :=
FORMAT_SV_TARGETS :=
ifeq ($(ENABLE_VERIBLE),1)
LINT_SV_TARGETS += lint-sv-verible
FORMAT_SV_TARGETS += format-sv-verible
endif
ifeq ($(ENABLE_VERILATOR),1)
LINT_SV_TARGETS += lint-sv-verilator
endif
ifeq ($(ENABLE_SLANG),1)
LINT_SV_TARGETS += lint-sv-slang
endif
ifeq ($(ENABLE_SLANG_TIDY),1)
LINT_SV_TARGETS += lint-sv-slang-tidy
endif

lint-py: $(LINT_PY_TARGETS)
lint-sv: $(LINT_SV_TARGETS)
lint-md: $(LINT_MD_TARGETS)
lint-spell: $(LINT_SPELL_TARGETS)
lint-gha: $(LINT_GHA_TARGETS)

format-py: $(FORMAT_PY_TARGETS)
format-sv: $(FORMAT_SV_TARGETS)
format-md: $(FORMAT_MD_TARGETS)

lint: lint-py lint-sv lint-md lint-spell lint-gha

format: format-py format-sv format-md

clean:
	rm -rf build transcript verdiLog vdCovLog vdCov.conf novas.rc novas.conf
