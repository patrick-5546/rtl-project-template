# Configuration variables. Override any of these on the command line as
# VAR=value (run `make help` for the common ones). Simulator and waveform-viewer
# behavior -- the build/test/coverage/wave commands and their defaults -- lives
# in the Python `flow/` package, which the sim/wave targets below dispatch to.
UV ?= uv
MARKDOWNLINT ?= markdownlint-cli2
SLANG ?= slang
SLANG_TIDY ?= slang-tidy

# The flow CLI (flow/cli.py) runs the tests, coverage, and waveform viewers; the
# sim/wave targets below are thin wrappers around it.
FLOW := $(UV) run python -m flow.cli

# SystemVerilog source list (see rtl/sources.vf for the file format). Exported
# so the flow package reads the same list the SV lint/format targets parse below.
SV_SOURCES_FILE ?= rtl/sources.vf
export SV_SOURCES_FILE

# Parse sources.vf into compile sources, +incdir+ dirs, and +verible+ extras,
# then validate (below) that every referenced path exists. The flow package
# parses the same file for the cocotb runner; this copy serves the SystemVerilog
# lint/format targets, which must stay usable without the cocotb environment.
read_sources = $(strip $(shell sed -e 's/[[:space:]]*\#.*//' -e '/^[[:space:]]*$$/d' $(1)))

SV_ENTRIES := $(call read_sources,$(SV_SOURCES_FILE))
SV_INCLUDE_DIRS := $(patsubst +incdir+%,%,$(filter +incdir+%,$(SV_ENTRIES)))
SV_VERIBLE_EXTRAS := $(patsubst +verible+%,%,$(filter +verible+%,$(SV_ENTRIES)))
SV_SOURCES := $(filter-out +%,$(SV_ENTRIES))
SV_INCLUDE_FLAGS := $(addprefix -I,$(SV_INCLUDE_DIRS))
SV_VERIBLE_INPUTS := $(SV_SOURCES) $(SV_VERIBLE_EXTRAS)

$(foreach dir,$(SV_INCLUDE_DIRS),$(if $(wildcard $(dir)/.),,$(error sources.vf: '+incdir+$(dir)' does not resolve to a directory)))
$(foreach src,$(SV_VERIBLE_EXTRAS),$(if $(wildcard $(src)),,$(error sources.vf: '+verible+$(src)' does not resolve to a file)))
$(foreach src,$(SV_SOURCES),$(if $(wildcard $(src)),,$(error sources.vf: '$(src)' does not resolve to a file)))

# Tool selection. SIM picks a simulator profile (flow/simulators.py) for the
# test/coverage targets; VIEWER picks a viewer profile (flow/viewers.py) for the
# wave targets. Unknown values are rejected by the flow CLI with the list of
# available tools. Add a simulator or viewer by registering a profile in those
# modules -- no edits to this Makefile required.
SIM ?= verilator
VIEWER ?= gtkwave

.PHONY: all clean coverage format help lint \
	md-format md-lint \
	open-coverage open-coverage-html open-waves \
	py-format py-format-check py-lint py-lint-all py-type py-lsp \
	sv-format sv-format-check sv-lint sv-lint-all sv-lint-slang sv-tidy-slang sv-lint-verilator \
	sync update-py-deps \
	test waves

all: lint test

help:
	@echo "Usage: make <target> [VAR=value ...]"
	@echo ""
	@echo "Setup:"
	@echo "  sync                            Install/update the uv-managed Python env"
	@echo "  update-py-deps                  Upgrade Python deps (uv lock --upgrade + sync)"
	@echo ""
	@echo "Test (default sim: verilator):"
	@echo "  test [SIM=questa]               Run the full cocotb regression"
	@echo "  test TEST=enable_high_counts    Run one cocotb test by exact name"
	@echo "  test TEST_FILTER='enable_.*'    Run cocotb tests matching a regex"
	@echo "  test REBUILD=0                  Reuse the existing simulator build"
	@echo "  test ABV=1                      Run with SVA assertions enabled"
	@echo "  test ABV=1 HDL_COVERAGE=1       Instrument coverage without a report"
	@echo ""
	@echo "Waveforms (default viewer: gtkwave):"
	@echo "  waves [VIEWER=questa]           Run tests, then open the waveform viewer"
	@echo "  open-waves [VIEWER=...]         Open the existing waveform in the viewer"
	@echo ""
	@echo "Coverage (default sim: verilator):"
	@echo "  coverage [SIM=questa]           Run full coverage + report"
	@echo "  open-coverage [SIM=questa]      Open coverage in the simulator's GUI viewer"
	@echo "  open-coverage-html [SIM=...]    Open the coverage HTML report"
	@echo ""
	@echo "Quality:"
	@echo "  lint                            Run all lint/type checks (py, sv, md)"
	@echo "  format                          Format Python, Markdown, and SystemVerilog"
	@echo "  all                             Run lint + test (default target)"
	@echo "  clean                           Remove generated local artifacts"
	@echo "  help                            Show this message"
	@echo ""
	@echo "Tool selection:"
	@echo "  SIM=<sim>                       Simulator (default $(SIM)); available: $$($(FLOW) list-sims | tr '\n' ' ')"
	@echo "  VIEWER=<viewer>                 Waveform viewer (default $(VIEWER)); available: $$($(FLOW) list-viewers | tr '\n' ' ')"
	@echo ""
	@echo "Common variables (override as VAR=value):"
	@echo "  TEST= / TEST_FILTER=            Select one test by exact name / by regex"
	@echo "  REBUILD=0                       Reuse the existing build instead of rebuilding"
	@echo "  ABV=1                           Enable SVA assertions and cover properties"
	@echo "  HDL_COVERAGE=1                  Enable simulator coverage instrumentation"
	@echo "  WAVE= / GTKWAVE_SAVE= / STATE=  Verilator wave file / GTKWave save / Surfer state"
	@echo "  QUESTA_WAVE= / QUESTA_DO=       Questa WLF / Questa .do layout"
	@echo "  VCS_WAVE= / VERDI_RC= / WAVES=0 VCS FSDB / Verdi layout / disable FSDB dump"
	@echo "  HTML_VIEWER=wslview             HTML opener (e.g. wslview on WSL)"

sync:
	$(UV) sync

update-py-deps:
	$(UV) lock --upgrade
	$(UV) sync

# Build the RTL and run the cocotb tests. flow/cli.py sets up the per-simulator
# pytest invocation (the supported cocotb runner path); command-line VAR=value
# overrides (ABV, TEST, TEST_FILTER, REBUILD, ...) reach it through the
# environment, which GNU Make exports automatically.
test:
	$(FLOW) test --sim $(SIM)

coverage:
	$(MAKE) test SIM=$(SIM) ABV=1 HDL_COVERAGE=1
	$(FLOW) report-coverage --sim $(SIM)

open-coverage:
	$(FLOW) open-coverage --sim $(SIM)

open-coverage-html:
	$(FLOW) open-coverage-html --sim $(SIM)

waves:
	$(FLOW) waves --viewer $(VIEWER)

open-waves:
	$(FLOW) open-waves --viewer $(VIEWER)

py-format:
	$(UV) run ruff format .

py-format-check:
	$(UV) run ruff format --check .

py-lint:
	$(UV) run ruff check .

py-type:
	$(UV) run ty check

py-lsp:
	$(UV) run basedpyright

md-lint:
	$(MARKDOWNLINT)

md-format:
	$(MARKDOWNLINT) --fix

sv-format:
	verible-verilog-format --inplace $(SV_VERIBLE_INPUTS)

sv-format-check:
	@for source in $(SV_VERIBLE_INPUTS); do \
		verible-verilog-format --verify "$$source" || exit $$?; \
	done

sv-lint:
	verible-verilog-lint $(SV_VERIBLE_INPUTS)

sv-lint-verilator:
	verilator --lint-only --timing -Wall --sv --coverage +define+ABV +define+NO_COVERGROUPS $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

sv-lint-slang:
	$(SLANG) -Werror +define+ABV $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

sv-tidy-slang:
	$(SLANG_TIDY) +define+ABV $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

py-lint-all: py-format-check py-lint py-type py-lsp

sv-lint-all: sv-format-check sv-lint sv-lint-verilator sv-lint-slang sv-tidy-slang

lint: py-lint-all sv-lint-all md-lint

format: py-format md-format sv-format

clean:
	rm -rf build work transcript verdiLog vdCovLog vdCov.conf novas.rc novas.conf
