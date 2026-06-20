# Configuration variables. Override any of these on the command line as
# VAR=value (run `make help` for the common ones). Defaults for the build/test
# flags below are mirrored in tests/runner.py and must be kept in sync.
UV ?= uv
PYTEST ?= $(UV) run pytest -s
MARKDOWNLINT ?= markdownlint-cli2
SLANG ?= slang
SLANG_TIDY ?= slang-tidy
HTML_VIEWER ?= xdg-open
# Passed through to tests/runner.py for every simulator; only meaningful for
# the Questa flow, but kept defined so the generic `test` recipe (and the
# runner's boolean parsing) always see a concrete 0/1 value.
QUESTA_GUI ?= 0
# Test selection and build flags.
TEST ?=
TEST_FILTER ?=
REBUILD ?= 1
ABV ?= 0
HDL_COVERAGE ?= 0
# SystemVerilog source list (see rtl/sources.vf for the file format).
SV_SOURCES_FILE ?= rtl/sources.vf

# Parse sources.vf into compile sources, +incdir+ dirs, and +verible+ extras,
# then validate (below) that every referenced path exists.
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

# Tool selection. SIM picks a simulator profile from mk/sim/<SIM>.mk; VIEWER
# picks a waveform-viewer profile from mk/wave/<VIEWER>.mk. Add a simulator or
# viewer by dropping a new file in those directories (and, for a simulator, a
# registry entry in tests/runner.py) -- no edits to this Makefile required.
SIM ?= verilator
VIEWER ?= gtkwave
AVAILABLE_SIMS := $(sort $(patsubst mk/sim/%.mk,%,$(wildcard mk/sim/*.mk)))
AVAILABLE_VIEWERS := $(sort $(patsubst mk/wave/%.mk,%,$(wildcard mk/wave/*.mk)))

ifeq ($(filter $(VIEWER),$(AVAILABLE_VIEWERS)),)
$(error Unknown VIEWER '$(VIEWER)'. Available: $(AVAILABLE_VIEWERS))
endif
# Include the viewer first so WAVE_SIM is known: a waveform belongs to the
# simulator that produced it, so wave targets must run under the viewer's sim.
include mk/wave/$(VIEWER).mk
ifneq ($(filter waves open-waves,$(MAKECMDGOALS)),)
SIM := $(WAVE_SIM)
endif

ifeq ($(filter $(SIM),$(AVAILABLE_SIMS)),)
$(error Unknown SIM '$(SIM)'. Available: $(AVAILABLE_SIMS))
endif
include mk/sim/$(SIM).mk

.PHONY: all clean coverage format gtkwave-stems help lint \
	md-format md-lint \
	open-coverage open-coverage-html open-waves \
	py-format py-format-check py-lint py-lint-all py-type py-lsp \
	sv-format sv-format-check sv-lint sv-lint-all sv-lint-slang sv-tidy-slang \
	sync update-py-deps \
	test verilator-lint waves

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
	@echo "  waves [VIEWER=surfer|questa]    Run tests, then open the waveform viewer"
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
	@echo "  SIM=<sim>                       Simulator (default verilator); available: $(AVAILABLE_SIMS)"
	@echo "  VIEWER=<viewer>                 Waveform viewer (default gtkwave); available: $(AVAILABLE_VIEWERS)"
	@echo ""
	@echo "Common variables (override as VAR=value):"
	@echo "  TEST= / TEST_FILTER=            Select one test by exact name / by regex"
	@echo "  REBUILD=0                       Reuse the existing build instead of rebuilding"
	@echo "  ABV=1                           Enable SVA assertions and cover properties"
	@echo "  HDL_COVERAGE=1                  Enable simulator coverage instrumentation"
	@echo "  WAVE= / GTKWAVE_SAVE= / STATE=  Verilator wave file / GTKWave save / Surfer state"
	@echo "  QUESTA_WAVE= / QUESTA_DO=       Questa WLF / Questa .do layout"
	@echo "  HTML_VIEWER=wslview             HTML opener (e.g. wslview on WSL)"

sync:
	$(UV) sync

update-py-deps:
	$(UV) lock --upgrade
	$(UV) sync

# Build the RTL and run the cocotb tests via pytest. Configuration is passed
# through to tests/runner.py as environment variables. Simulator-specific
# values (BUILD_DIR, NO_COVERGROUPS, QUESTA_*, ...) come from mk/sim/$(SIM).mk.
test:
	SIM=$(SIM) \
		BUILD_DIR="$(BUILD_DIR)" QUESTA_WAVE="$(QUESTA_WAVE)" \
		ABV="$(ABV)" \
		NO_COVERGROUPS="$(NO_COVERGROUPS)" \
		HDL_COVERAGE="$(HDL_COVERAGE)" COVERAGE_DAT="$(COVERAGE_DAT)" \
		SV_SOURCES_FILE="$(SV_SOURCES_FILE)" \
		QUESTA_GUI="$(QUESTA_GUI)" QUESTA_DO="$(QUESTA_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" $(PYTEST)

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

verilator-lint:
	verilator --lint-only --timing -Wall --sv --coverage +define+ABV +define+NO_COVERGROUPS $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

sv-lint-slang:
	$(SLANG) -Werror +define+ABV $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

sv-tidy-slang:
	$(SLANG_TIDY) +define+ABV $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

py-lint-all: py-format-check py-lint py-type py-lsp

sv-lint-all: sv-format-check sv-lint verilator-lint sv-lint-slang sv-tidy-slang

lint: py-lint-all sv-lint-all md-lint

format: py-format md-format sv-format

clean:
	rm -rf build work transcript
