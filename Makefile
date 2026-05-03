UV ?= uv
PRE_COMMIT ?= $(UV) run pre-commit
PYTEST ?= $(UV) run pytest -s
SIM ?= verilator
QUESTA_SIM ?= questa
VERILATOR_BUILD_DIR ?= build/verilator
QUESTA_BUILD_DIR ?= build/questa
BUILD_DIR ?= $(if $(filter $(QUESTA_SIM),$(SIM)),$(QUESTA_BUILD_DIR),$(VERILATOR_BUILD_DIR))
SURFER ?= surfer
GTKWAVE ?= gtkwave
GTKWAVE_ARGS ?= -o
JSON2STEMS ?= json2stems
MARKDOWNLINT ?= markdownlint-cli2
VSIM ?= vsim
VCOVER ?= vcover
HTML_VIEWER ?= xdg-open
QUESTA_ARGS ?= -voptargs=+acc -debugdb
WAVE ?= $(VERILATOR_BUILD_DIR)/dump.vcd
QUESTA_WAVE ?= $(QUESTA_BUILD_DIR)/vsim.wlf
STATE ?= waves/top.surf.ron
GTKWAVE_SAVE ?= waves/top.gtkw
GTKWAVE_STEMS_TOP ?= top
GTKWAVE_STEMS_DIR ?= $(VERILATOR_BUILD_DIR)/rtlbrowse
GTKWAVE_STEMS ?= $(GTKWAVE_STEMS_DIR)/top.stems
GTKWAVE_STEMS_JSON ?= $(GTKWAVE_STEMS_DIR)/V$(GTKWAVE_STEMS_TOP).tree.json
GTKWAVE_STEMS_META ?= $(GTKWAVE_STEMS_DIR)/V$(GTKWAVE_STEMS_TOP).tree.meta.json
QUESTA_DO ?= waves/top.do
QUESTA_GUI ?= 0
TEST ?=
TEST_FILTER ?=
REBUILD ?= 1
ABV ?= 0
HDL_COVERAGE ?= 0
COVERAGE_DAT ?= $(BUILD_DIR)/coverage.dat
QUESTA_COVERAGE_UCDB ?= $(QUESTA_BUILD_DIR)/coverage.ucdb
COVERAGE_ANNOTATION_DIR ?= $(BUILD_DIR)/coverage_annotated
COVERAGE_INFO ?= $(BUILD_DIR)/coverage.info
COVERAGE_HTML_DIR ?= $(VERILATOR_BUILD_DIR)/coverage_html
COVERAGE_HTML_INDEX ?= $(COVERAGE_HTML_DIR)/index.html
QUESTA_COVERAGE_HTML_DIR ?= $(QUESTA_BUILD_DIR)/coverage_html
QUESTA_COVERAGE_HTML_INDEX ?= $(QUESTA_COVERAGE_HTML_DIR)/index.html
SV_SOURCES_FILE ?= rtl/sources.vf
ABV_SOURCES_FILE ?= rtl/abv_sources.vf

read_sources = $(strip $(shell sed -e 's/[[:space:]]*#.*//' -e '/^[[:space:]]*$$/d' $(1)))

SV_SOURCES := $(call read_sources,$(SV_SOURCES_FILE))
ABV_SOURCES := $(call read_sources,$(ABV_SOURCES_FILE))
ALL_SV_SOURCES := $(SV_SOURCES) $(ABV_SOURCES)
GTKWAVE_STEMS_SOURCES = $(SV_SOURCES) $(if $(filter 1 true yes on,$(ABV)),$(ABV_SOURCES))
GTKWAVE_STEMS_DEFINES = $(if $(filter 1 true yes on,$(ABV)),+define+ABV)

.PHONY: all clean format gtkwave-stems help lint open-waves open-waves-gtkwave \
	md-format md-lint open-waves-questa pre-commit-install pre-commit-run \
	coverage coverage-questa open-coverage-html \
	open-coverage-questa open-coverage-questa-html \
	py-format py-format-check py-lint py-type \
	sv-format sv-format-check sv-lint sync test test-questa verilator-lint \
	waves waves-gtkwave waves-questa

all: lint test

help:
	@echo "Common targets:"
	@echo "  make test                                      Run the full cocotb regression"
	@echo "  make test TEST=enable_high_counts             Run one cocotb test"
	@echo "  make test TEST_FILTER='enable_.*'             Run matching cocotb tests"
	@echo "  make test REBUILD=0                           Reuse an existing simulator build"
	@echo "  make test ABV=1                               Run with SVA assertions enabled"
	@echo "  make coverage                                 Run Verilator full coverage"
	@echo "  make coverage-questa                          Run Questa full coverage"
	@echo "  make open-coverage-html                       Open existing Verilator coverage HTML"
	@echo "  make open-coverage-questa                     Open Questa coverage in GUI"
	@echo "  make open-coverage-questa-html                Open Questa coverage as HTML"
	@echo "  make waves [TEST=...]                         Run tests, then open Surfer"
	@echo "  make waves-gtkwave [TEST=...]                 Run tests, then open GTKWave"
	@echo "  make gtkwave-stems                            Generate GTKWave rtlbrowser stems"
	@echo "  make test-questa [TEST=...]                   Run tests with Questa"
	@echo "  make waves-questa [TEST=...]                  Run tests in live Questa GUI"
	@echo "  make open-waves                               Open existing waveform in Surfer"
	@echo "  make open-waves-gtkwave                       Open existing waveform in GTKWave"
	@echo "  make open-waves-questa                        Open existing WLF in Questa"
	@echo "  make pre-commit-install                       Install the Git pre-commit hook"
	@echo "  make pre-commit-run                           Run all pre-commit hooks"
	@echo "  make lint                                     Run all lint/type checks"
	@echo "  make format                                   Format Python, Markdown, and SystemVerilog"
	@echo "  make md-lint                                  Run Markdown lint checks"
	@echo "  make md-format                                Apply Markdown lint fixes"
	@echo "  make clean                                    Remove generated artifacts"

sync:
	$(UV) sync

pre-commit-install:
	$(PRE_COMMIT) install

pre-commit-run:
	$(PRE_COMMIT) run --all-files

test:
	ARCH="$(ARCH)" COCOTB_BITS="$(COCOTB_BITS)" SIM=$(SIM) \
		BUILD_DIR="$(BUILD_DIR)" QUESTA_WAVE="$(QUESTA_WAVE)" \
		QUESTA_ARGS="$(QUESTA_ARGS)" ABV="$(ABV)" \
		HDL_COVERAGE="$(HDL_COVERAGE)" COVERAGE_DAT="$(COVERAGE_DAT)" \
		SV_SOURCES_FILE="$(SV_SOURCES_FILE)" ABV_SOURCES_FILE="$(ABV_SOURCES_FILE)" \
		QUESTA_GUI="$(QUESTA_GUI)" QUESTA_DO="$(QUESTA_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" $(PYTEST)

test-questa:
	$(MAKE) test SIM="$(QUESTA_SIM)" BUILD_DIR="$(QUESTA_BUILD_DIR)" \
		QUESTA_WAVE="$(QUESTA_WAVE)" TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" \
		REBUILD="$(REBUILD)" QUESTA_ARGS="$(QUESTA_ARGS)" \
		PYTEST="$(UV) run pytest -s --timeout=0" UV="$(UV)" ABV="$(ABV)" \
		QUESTA_GUI="$(QUESTA_GUI)" QUESTA_DO="$(QUESTA_DO)"

py-format:
	$(UV) run ruff format .

py-format-check:
	$(UV) run ruff format --check .

py-lint:
	$(UV) run ruff check .

py-type:
	$(UV) run ty check

md-lint:
	$(MARKDOWNLINT)

md-format:
	$(MARKDOWNLINT) --fix

sv-format:
	verible-verilog-format --inplace $(ALL_SV_SOURCES)

sv-format-check:
	@for source in $(ALL_SV_SOURCES); do \
		verible-verilog-format --verify "$$source" || exit $$?; \
	done

sv-lint:
	verible-verilog-lint $(ALL_SV_SOURCES)

verilator-lint:
	verilator --lint-only --timing -Wall --sv --coverage +define+ABV $(ALL_SV_SOURCES)

lint: py-format-check py-lint py-type md-lint sv-format-check sv-lint verilator-lint

format: py-format md-format sv-format

coverage:
	$(MAKE) test SIM=verilator BUILD_DIR="$(VERILATOR_BUILD_DIR)" \
		ABV=1 HDL_COVERAGE=1 COVERAGE_DAT="$(COVERAGE_DAT)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" \
		PYTEST="$(PYTEST)" UV="$(UV)"
	rm -rf "$(COVERAGE_ANNOTATION_DIR)"
	verilator_coverage --annotate "$(COVERAGE_ANNOTATION_DIR)" \
		--annotate-all --annotate-points --annotate-min 1 --include-reset-arcs \
		"$(COVERAGE_DAT)"
	verilator_coverage --write-info "$(COVERAGE_INFO)" \
		--include-reset-arcs \
		"$(COVERAGE_DAT)"
	@echo "Coverage data: $(COVERAGE_DAT)"
	@echo "Annotated report: $(COVERAGE_ANNOTATION_DIR)"
	@echo "LCOV info: $(COVERAGE_INFO)"

coverage-questa:
	$(MAKE) test-questa ABV=1 HDL_COVERAGE=1 \
		COVERAGE_DAT="$(QUESTA_COVERAGE_UCDB)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)"
	$(VCOVER) report -summary "$(QUESTA_COVERAGE_UCDB)"
	@echo "Coverage UCDB: $(QUESTA_COVERAGE_UCDB)"

open-coverage-questa:
	@test -f "$(QUESTA_COVERAGE_UCDB)" || { echo "UCDB '$(QUESTA_COVERAGE_UCDB)' not found. Run 'make coverage-questa' first."; exit 1; }
	$(VSIM) -viewcov "$(QUESTA_COVERAGE_UCDB)"

open-coverage-questa-html:
	@test -f "$(QUESTA_COVERAGE_UCDB)" || { echo "UCDB '$(QUESTA_COVERAGE_UCDB)' not found. Run 'make coverage-questa' first."; exit 1; }
	rm -rf "$(QUESTA_COVERAGE_HTML_DIR)"
	$(VCOVER) report -html -details -output "$(QUESTA_COVERAGE_HTML_DIR)" "$(QUESTA_COVERAGE_UCDB)"
	@echo "HTML report: $(QUESTA_COVERAGE_HTML_INDEX)"
	$(HTML_VIEWER) "$(QUESTA_COVERAGE_HTML_INDEX)"

open-coverage-html:
	@test -f "$(COVERAGE_INFO)" || { echo "Coverage info '$(COVERAGE_INFO)' not found. Run 'make coverage' first."; exit 1; }
	rm -rf "$(COVERAGE_HTML_DIR)"
	genhtml --branch-coverage --no-function-coverage --show-details \
		--legend --title "Verilator coverage" --prefix "$(CURDIR)" \
		--output-directory "$(COVERAGE_HTML_DIR)" \
		"$(COVERAGE_INFO)"
	@echo "HTML report: $(COVERAGE_HTML_INDEX)"
	$(HTML_VIEWER) "$(COVERAGE_HTML_INDEX)"

waves: test
	$(MAKE) open-waves WAVE="$(WAVE)" STATE="$(STATE)" SURFER="$(SURFER)"

open-waves:
	@test -f "$(WAVE)" || { echo "Waveform '$(WAVE)' not found. Run 'make test' first."; exit 1; }
	if test -f "$(STATE)"; then \
		$(SURFER) --state-file "$(STATE)" "$(WAVE)"; \
	else \
		$(SURFER) "$(WAVE)"; \
	fi

waves-gtkwave: test
	$(MAKE) open-waves-gtkwave WAVE="$(WAVE)" GTKWAVE_SAVE="$(GTKWAVE_SAVE)" \
		GTKWAVE="$(GTKWAVE)" GTKWAVE_ARGS="$(GTKWAVE_ARGS)" \
		GTKWAVE_STEMS="$(GTKWAVE_STEMS)"

open-waves-gtkwave:
	@test -f "$(WAVE)" || { echo "Waveform '$(WAVE)' not found. Run 'make test' first."; exit 1; }
	$(MAKE) gtkwave-stems GTKWAVE_STEMS="$(GTKWAVE_STEMS)"
	if test -f "$(GTKWAVE_SAVE)"; then \
		$(GTKWAVE) $(GTKWAVE_ARGS) -t "$(GTKWAVE_STEMS)" "$(WAVE)" "$(GTKWAVE_SAVE)"; \
	else \
		$(GTKWAVE) $(GTKWAVE_ARGS) -t "$(GTKWAVE_STEMS)" "$(WAVE)"; \
	fi

gtkwave-stems:
	mkdir -p "$(GTKWAVE_STEMS_DIR)" "$(dir $(GTKWAVE_STEMS))"
	verilator -Wno-fatal --json-only --bbox-sys --timing --sv \
		--top-module "$(GTKWAVE_STEMS_TOP)" --Mdir "$(GTKWAVE_STEMS_DIR)" \
		$(GTKWAVE_STEMS_DEFINES) $(GTKWAVE_STEMS_SOURCES)
	$(JSON2STEMS) "$(GTKWAVE_STEMS_META)" "$(GTKWAVE_STEMS_JSON)" "$(GTKWAVE_STEMS)"
	@echo "GTKWave stems: $(GTKWAVE_STEMS)"

waves-questa:
	$(MAKE) test-questa QUESTA_GUI=1 QUESTA_DO="$(QUESTA_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" \
		QUESTA_ARGS="$(QUESTA_ARGS)" QUESTA_WAVE="$(QUESTA_WAVE)" \
		ABV="$(ABV)" UV="$(UV)"

open-waves-questa:
	@test -f "$(QUESTA_WAVE)" || { echo "Waveform '$(QUESTA_WAVE)' not found. Run 'make test-questa' first."; exit 1; }
	if test -f "$(QUESTA_DO)"; then \
		$(VSIM) $(QUESTA_ARGS) -view "$(QUESTA_WAVE)" -do "$(QUESTA_DO)"; \
	else \
		$(VSIM) $(QUESTA_ARGS) -view "$(QUESTA_WAVE)"; \
	fi

clean:
	rm -rf build
