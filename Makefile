# Configuration variables. Override any of these on the command line as
# VAR=value (run `make help` for the common ones). Simulator and waveform-viewer
# behavior -- the build/test/coverage/wave commands and their defaults -- lives
# in the Python `flow/` package, which the sim/wave targets below dispatch to.
UV ?= uv
MARKDOWNLINT ?= markdownlint-cli2
SLANG ?= slang
SLANG_TIDY ?= slang-tidy

# Per-tool enable flags for the lint/format aggregates. Set any to 0 to drop
# that tool from `lint`/`format` (and the per-language `lint-<lang>` /
# `format-<lang>` groups); the per-tool target itself stays directly invokable.
ENABLE_RUFF ?= 1
ENABLE_TY ?= 1
ENABLE_BASEDPYRIGHT ?= 1
ENABLE_MARKDOWNLINT ?= 1
ENABLE_VERIBLE ?= 1
ENABLE_VERILATOR ?= 1
ENABLE_SLANG ?= 1
ENABLE_SLANG_TIDY ?= 1

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

# Top-level module under test. Passed to the flow CLI (which forwards it to the
# cocotb runner and the waveform viewers: GTKWave stems and the waves/<DUT>.*
# layouts) so every command targets the same module; override as
# `make test DUT=<module>`.
DUT ?= top

.PHONY: all clean coverage format help lint \
	lint-py lint-sv lint-md format-py format-sv format-md \
	format-py-ruff lint-py-ruff lint-py-ty lint-py-basedpyright \
	format-md-markdownlint lint-md-markdownlint \
	format-sv-verible lint-sv-verible lint-sv-verilator lint-sv-slang lint-sv-slang-tidy \
	open-coverage open-coverage-html open-waves \
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
	@echo "Test:"
	@echo "  test [SIM=questa]               Run the full cocotb regression"
	@echo "  test TEST=enable_high_counts    Run one cocotb test by exact name"
	@echo "  test TEST_FILTER='enable_.*'    Run cocotb tests matching a regex"
	@echo "  test REBUILD=0                  Reuse the existing simulator build"
	@echo "  test ABV=1                      Run with SVA assertions enabled"
	@echo "  test ABV=1 HDL_COVERAGE=1       Instrument coverage without a report"
	@echo ""
	@echo "Waveforms:"
	@echo "  waves [VIEWER=questa]           Run tests, then open the waveform viewer"
	@echo "  open-waves [VIEWER=...]         Open the existing waveform in the viewer"
	@echo ""
	@echo "Coverage:"
	@echo "  coverage [SIM=questa]           Run full coverage + report"
	@echo "  open-coverage [SIM=questa]      Open coverage in the simulator's GUI viewer"
	@echo "  open-coverage-html [SIM=...]    Open the coverage HTML report"
	@echo ""
	@echo "Quality:"
	@echo "  lint                            Run all lint/type checks (py, sv, md)"
	@echo "  lint-<py|sv|md>                 Run lint/type checks for one language"
	@echo "  format                          Format Python, Markdown, and SystemVerilog"
	@echo "  format-<py|sv|md>               Format one language"
	@echo "  all                             Run lint + test (default target)"
	@echo "  clean                           Remove generated local artifacts"
	@echo "  help                            Show this message"
	@echo ""
	@echo "Per-tool quality targets (<lint|format>-<lang>-<tool>):"
	@echo "  lint-py-ruff lint-py-ty lint-py-basedpyright  format-py-ruff"
	@echo "  lint-sv-verible lint-sv-verilator lint-sv-slang lint-sv-slang-tidy  format-sv-verible"
	@echo "  lint-md-markdownlint  format-md-markdownlint"
	@echo ""
	@echo "Tool enable flags (default 1; set 0 to skip a tool in lint/format):"
	@echo "  ENABLE_RUFF ENABLE_TY ENABLE_BASEDPYRIGHT ENABLE_MARKDOWNLINT"
	@echo "  ENABLE_VERIBLE ENABLE_VERILATOR ENABLE_SLANG ENABLE_SLANG_TIDY"
	@echo ""
	@echo "Tool selection:"
	@echo "  SIM=<sim>                       Simulator; available: $$($(FLOW) list-sims | tr '\n' ' ')"
	@echo "  VIEWER=<viewer>                 Waveform viewer; available: $$($(FLOW) list-viewers | tr '\n' ' ')"
	@echo ""
	@echo "Common variables (override as VAR=value):"
	@echo "  DUT=<module>                    Top module to build/test/view"
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
	$(FLOW) test --sim $(SIM) --dut $(DUT)

coverage:
	$(MAKE) test SIM=$(SIM) DUT=$(DUT) ABV=1 HDL_COVERAGE=1
	$(FLOW) report-coverage --sim $(SIM) --dut $(DUT)

open-coverage:
	$(FLOW) open-coverage --sim $(SIM) --dut $(DUT)

open-coverage-html:
	$(FLOW) open-coverage-html --sim $(SIM) --dut $(DUT)

waves:
	$(FLOW) waves --viewer $(VIEWER) --dut $(DUT)

open-waves:
	$(FLOW) open-waves --viewer $(VIEWER) --dut $(DUT)

format-py-ruff:
	$(UV) run ruff format .

lint-py-ruff:
	$(UV) run ruff format --check .
	$(UV) run ruff check .

lint-py-ty:
	$(UV) run ty check

lint-py-basedpyright:
	$(UV) run basedpyright

format-md-markdownlint:
	$(MARKDOWNLINT) --fix

lint-md-markdownlint:
	$(MARKDOWNLINT)

format-sv-verible:
	verible-verilog-format --inplace $(SV_VERIBLE_INPUTS)

lint-sv-verible:
	@for source in $(SV_VERIBLE_INPUTS); do \
		verible-verilog-format --verify "$$source" || exit $$?; \
	done
	verible-verilog-lint $(SV_VERIBLE_INPUTS)

lint-sv-verilator:
	verilator --lint-only --timing -Wall --sv --coverage +define+ABV +define+NO_COVERGROUPS $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

lint-sv-slang:
	$(SLANG) -Werror +define+ABV $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

lint-sv-slang-tidy:
	$(SLANG_TIDY) +define+ABV $(SV_INCLUDE_FLAGS) $(SV_SOURCES)

# Per-tool ENABLE_<TOOL> flags select which targets the language aggregates run;
# a disabled tool drops out of `lint`/`format` but its target stays invokable.
LINT_PY_TARGETS :=
FORMAT_PY_TARGETS :=
ifeq ($(ENABLE_RUFF),1)
LINT_PY_TARGETS += lint-py-ruff
FORMAT_PY_TARGETS += format-py-ruff
endif
ifeq ($(ENABLE_TY),1)
LINT_PY_TARGETS += lint-py-ty
endif
ifeq ($(ENABLE_BASEDPYRIGHT),1)
LINT_PY_TARGETS += lint-py-basedpyright
endif

LINT_MD_TARGETS :=
FORMAT_MD_TARGETS :=
ifeq ($(ENABLE_MARKDOWNLINT),1)
LINT_MD_TARGETS += lint-md-markdownlint
FORMAT_MD_TARGETS += format-md-markdownlint
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

format-py: $(FORMAT_PY_TARGETS)
format-sv: $(FORMAT_SV_TARGETS)
format-md: $(FORMAT_MD_TARGETS)

lint: lint-py lint-sv lint-md

format: format-py format-sv format-md

clean:
	rm -rf build work transcript verdiLog vdCovLog vdCov.conf novas.rc novas.conf
