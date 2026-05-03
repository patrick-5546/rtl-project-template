UV ?= uv
PRE_COMMIT ?= $(UV) run pre-commit
PYTEST ?= $(UV) run pytest -s
SIM ?= verilator
MODELSIM_SIM ?= questa
VERILATOR_BUILD_DIR ?= build/verilator
MODELSIM_BUILD_DIR ?= build/modelsim
BUILD_DIR ?= $(if $(filter $(MODELSIM_SIM),$(SIM)),$(MODELSIM_BUILD_DIR),$(VERILATOR_BUILD_DIR))
SURFER ?= surfer
GTKWAVE ?= gtkwave
MARKDOWNLINT ?= markdownlint-cli2
VSIM ?= vsim
HTML_VIEWER ?= xdg-open
MODELSIM_ARGS ?= -voptargs=+acc
MODELSIM_ARCH ?= i686
MODELSIM_BITS ?= 32
MODELSIM32_PYTHON ?= .venv-modelsim32/bin/python
MODELSIM_PYTEST ?= $(if $(wildcard $(MODELSIM32_PYTHON)),$(MODELSIM32_PYTHON) -m pytest -s,$(PYTEST))
WAVE ?= $(VERILATOR_BUILD_DIR)/dump.vcd
MODELSIM_WAVE ?= $(MODELSIM_BUILD_DIR)/vsim.wlf
STATE ?= waves/top.surf.ron
GTKWAVE_SAVE ?= waves/top.gtkw
MODELSIM_DO ?= waves/top.do
MODELSIM_GUI ?= 0
TEST ?=
TEST_FILTER ?=
REBUILD ?= 1
ABV ?= 0
HDL_COVERAGE ?= 0
COVERAGE_DAT ?= $(BUILD_DIR)/coverage.dat
COVERAGE_ANNOTATION_DIR ?= $(BUILD_DIR)/coverage_annotated
COVERAGE_INFO ?= $(BUILD_DIR)/coverage.info
COVERAGE_HTML_DIR ?= $(VERILATOR_BUILD_DIR)/coverage_html
COVERAGE_HTML_INDEX ?= $(COVERAGE_HTML_DIR)/index.html
SV_SOURCES_FILE ?= rtl/sources.vf
ABV_SOURCES_FILE ?= rtl/abv_sources.vf

read_sources = $(strip $(shell sed -e 's/[[:space:]]*#.*//' -e '/^[[:space:]]*$$/d' $(1)))

SV_SOURCES := $(call read_sources,$(SV_SOURCES_FILE))
ABV_SOURCES := $(call read_sources,$(ABV_SOURCES_FILE))
ALL_SV_SOURCES := $(SV_SOURCES) $(ABV_SOURCES)

.PHONY: all check clean format help lint open-waves open-waves-gtkwave \
	md-format md-lint open-waves-modelsim pre-commit-install pre-commit-run \
	coverage open-coverage-html py-format py-format-check py-lint py-type sim \
	sv-format sv-format-check sv-lint sync test test-modelsim verilator-lint \
	waves waves-gtkwave waves-modelsim

all: check test

help:
	@echo "Common targets:"
	@echo "  make test                                      Run the full cocotb regression"
	@echo "  make test TEST=enable_high_counts             Run one cocotb test"
	@echo "  make test TEST_FILTER='enable_.*'             Run matching cocotb tests"
	@echo "  make test REBUILD=0                           Reuse an existing simulator build"
	@echo "  make test ABV=1                               Run with SVA assertions enabled"
	@echo "  make coverage                                 Run Verilator full coverage"
	@echo "  make open-coverage-html                       Open existing coverage HTML"
	@echo "  make waves [TEST=...]                         Run tests, then open Surfer"
	@echo "  make waves-gtkwave [TEST=...]                 Run tests, then open GTKWave"
	@echo "  make test-modelsim [TEST=...]                 Run tests with ModelSim"
	@echo "  make test-modelsim MODELSIM_PYTEST='<cmd>'    Run ModelSim with a custom Python env"
	@echo "  make waves-modelsim [TEST=...]                Run tests in live ModelSim GUI"
	@echo "  make open-waves                               Open existing waveform in Surfer"
	@echo "  make open-waves-gtkwave                       Open existing waveform in GTKWave"
	@echo "  make open-waves-modelsim                      Open existing WLF in ModelSim"
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
		BUILD_DIR="$(BUILD_DIR)" MODELSIM_WAVE="$(MODELSIM_WAVE)" \
		MODELSIM_ARGS="$(MODELSIM_ARGS)" ABV="$(ABV)" \
		HDL_COVERAGE="$(HDL_COVERAGE)" COVERAGE_DAT="$(COVERAGE_DAT)" \
		SV_SOURCES_FILE="$(SV_SOURCES_FILE)" ABV_SOURCES_FILE="$(ABV_SOURCES_FILE)" \
		MODELSIM_GUI="$(MODELSIM_GUI)" MODELSIM_DO="$(MODELSIM_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" $(PYTEST)

test-modelsim:
	$(MAKE) test SIM="$(MODELSIM_SIM)" BUILD_DIR="$(MODELSIM_BUILD_DIR)" \
		MODELSIM_WAVE="$(MODELSIM_WAVE)" TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" \
		REBUILD="$(REBUILD)" MODELSIM_ARGS="$(MODELSIM_ARGS)" \
		ARCH="$(MODELSIM_ARCH)" COCOTB_BITS="$(MODELSIM_BITS)" \
		PYTEST="$(MODELSIM_PYTEST)" UV="$(UV)" ABV="$(ABV)" \
		MODELSIM_GUI="$(MODELSIM_GUI)" MODELSIM_DO="$(MODELSIM_DO)"

sim: test

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

check: lint

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
	$(MAKE) open-waves-gtkwave WAVE="$(WAVE)" GTKWAVE_SAVE="$(GTKWAVE_SAVE)" GTKWAVE="$(GTKWAVE)"

open-waves-gtkwave:
	@test -f "$(WAVE)" || { echo "Waveform '$(WAVE)' not found. Run 'make test' first."; exit 1; }
	if test -f "$(GTKWAVE_SAVE)"; then \
		$(GTKWAVE) "$(WAVE)" "$(GTKWAVE_SAVE)"; \
	else \
		$(GTKWAVE) "$(WAVE)"; \
	fi

waves-modelsim:
	$(MAKE) test-modelsim MODELSIM_GUI=1 MODELSIM_DO="$(MODELSIM_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" \
		MODELSIM_ARGS="$(MODELSIM_ARGS)" MODELSIM_WAVE="$(MODELSIM_WAVE)" \
		ABV="$(ABV)" UV="$(UV)"

open-waves-modelsim:
	@test -f "$(MODELSIM_WAVE)" || { echo "Waveform '$(MODELSIM_WAVE)' not found. Run 'make test-modelsim' first."; exit 1; }
	if test -f "$(MODELSIM_DO)"; then \
		$(VSIM) $(MODELSIM_ARGS) -view "$(MODELSIM_WAVE)" -do "$(MODELSIM_DO)"; \
	else \
		$(VSIM) $(MODELSIM_ARGS) -view "$(MODELSIM_WAVE)"; \
	fi

clean:
	rm -rf build
