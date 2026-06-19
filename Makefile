UV ?= uv
PREK ?= $(UV) run prek
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
SLANG ?= slang
SLANG_TIDY ?= slang-tidy
VSIM ?= vsim
VCOVER ?= vcover
HTML_VIEWER ?= xdg-open
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
NO_COVERGROUPS ?= $(if $(filter verilator,$(SIM)),1,0)
COVERAGE_DAT ?= $(BUILD_DIR)/coverage.dat
QUESTA_COVERAGE_UCDB ?= $(QUESTA_BUILD_DIR)/coverage.ucdb
COVERAGE_ANNOTATION_DIR ?= $(BUILD_DIR)/coverage_annotated
COVERAGE_INFO ?= $(BUILD_DIR)/coverage.info
COVERAGE_HTML_DIR ?= $(VERILATOR_BUILD_DIR)/coverage_html
COVERAGE_HTML_INDEX ?= $(COVERAGE_HTML_DIR)/index.html
COVERAGE_MIN_LINES ?= 90
COVERAGE_MIN_BRANCHES ?= 90
QUESTA_COVERAGE_HTML_DIR ?= $(QUESTA_BUILD_DIR)/coverage_html
QUESTA_COVERAGE_HTML_INDEX ?= $(QUESTA_COVERAGE_HTML_DIR)/index.html
SV_SOURCES_FILE ?= rtl/sources.vf

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

GTKWAVE_STEMS_SOURCES = $(SV_SOURCES)
GTKWAVE_STEMS_DEFINES = $(if $(filter 1 true yes on,$(ABV)),+define+ABV)

.PHONY: all clean coverage coverage-questa format gtkwave-stems help lint \
	md-format md-lint \
	open-coverage-html open-coverage-questa open-coverage-questa-html \
	open-waves open-waves-questa open-waves-surfer \
	prek-install prek-run \
	py-format py-format-check py-lint py-lint-all py-type py-lsp \
	sv-format sv-format-check sv-lint sv-lint-all sv-lint-slang sv-tidy-slang \
	sync update-py-deps \
	test test-questa verilator-lint \
	waves waves-questa waves-surfer

all: lint test

help:
	@echo "Common targets:"
	@echo "  make all                                      Run lint + test (default)"
	@echo "  make test                                     Run the full cocotb regression"
	@echo "  make test TEST=enable_high_counts             Run one cocotb test"
	@echo "  make test TEST_FILTER='enable_.*'             Run matching cocotb tests"
	@echo "  make test REBUILD=0                           Reuse an existing simulator build"
	@echo "  make test ABV=1                               Run with SVA assertions enabled"
	@echo "  make coverage                                 Run Verilator full coverage"
	@echo "  make coverage-questa                          Run Questa full coverage"
	@echo "  make open-coverage-html                       Open existing Verilator coverage HTML"
	@echo "  make open-coverage-questa                     Open Questa coverage in GUI"
	@echo "  make open-coverage-questa-html                Open Questa coverage as HTML"
	@echo "  make waves [TEST=...]                         Run tests, then open GTKWave"
	@echo "  make waves-surfer [TEST=...]                  Run tests, then open Surfer"
	@echo "  make test-questa [TEST=...]                   Run tests with Questa"
	@echo "  make waves-questa [TEST=...]                  Run tests in live Questa GUI"
	@echo "  make open-waves                               Open existing waveform in GTKWave"
	@echo "  make open-waves-surfer                        Open existing waveform in Surfer"
	@echo "  make open-waves-questa                        Open existing WLF in Questa"
	@echo "  make prek-install                             Install the Git pre-commit hook"
	@echo "  make prek-run                                 Run all prek hooks"
	@echo "  make lint                                     Run all lint/type checks"
	@echo "  make format                                   Format Python, Markdown, and SystemVerilog"
	@echo "  make sync                                     Run uv sync"
	@echo "  make update-py-deps                           Upgrade Python deps (uv lock --upgrade + sync)"
	@echo "  make clean                                    Remove generated artifacts"

sync:
	$(UV) sync

update-py-deps:
	$(UV) lock --upgrade
	$(UV) sync

prek-install:
	$(PREK) install

prek-run:
	$(PREK) run --all-files

test:
	SIM=$(SIM) \
		BUILD_DIR="$(BUILD_DIR)" QUESTA_WAVE="$(QUESTA_WAVE)" \
		ABV="$(ABV)" \
		NO_COVERGROUPS="$(NO_COVERGROUPS)" \
		HDL_COVERAGE="$(HDL_COVERAGE)" COVERAGE_DAT="$(COVERAGE_DAT)" \
		SV_SOURCES_FILE="$(SV_SOURCES_FILE)" \
		QUESTA_GUI="$(QUESTA_GUI)" QUESTA_DO="$(QUESTA_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" $(PYTEST)

test-questa:
	$(MAKE) test SIM="$(QUESTA_SIM)" BUILD_DIR="$(QUESTA_BUILD_DIR)" \
		QUESTA_WAVE="$(QUESTA_WAVE)" TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" \
		REBUILD="$(REBUILD)" \
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
	rm -rf "$(COVERAGE_HTML_DIR)"
	genhtml --branch-coverage --no-function-coverage --show-details \
		--legend --title "Verilator coverage" --prefix "$(CURDIR)" \
		--fail-under-lines $(COVERAGE_MIN_LINES) \
		--fail-under-branches $(COVERAGE_MIN_BRANCHES) \
		--output-directory "$(COVERAGE_HTML_DIR)" \
		"$(COVERAGE_INFO)"
	@echo "Coverage data: $(COVERAGE_DAT)"
	@echo "Annotated report: $(COVERAGE_ANNOTATION_DIR)"
	@echo "HTML report: $(COVERAGE_HTML_INDEX)"

coverage-questa:
	$(MAKE) test-questa ABV=1 HDL_COVERAGE=1 \
		COVERAGE_DAT="$(QUESTA_COVERAGE_UCDB)" \
		QUESTA_ARGS="-extendedtogglemode 1" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)"
	$(VCOVER) report -summary "$(QUESTA_COVERAGE_UCDB)"
	rm -rf "$(QUESTA_COVERAGE_HTML_DIR)"
	$(VCOVER) report -html -details -output "$(QUESTA_COVERAGE_HTML_DIR)" "$(QUESTA_COVERAGE_UCDB)"
	@echo "Coverage UCDB: $(QUESTA_COVERAGE_UCDB)"
	@echo "HTML report: $(QUESTA_COVERAGE_HTML_INDEX)"

open-coverage-questa:
	@test -f "$(QUESTA_COVERAGE_UCDB)" || { echo "UCDB '$(QUESTA_COVERAGE_UCDB)' not found. Run 'make coverage-questa' first."; exit 1; }
	$(VSIM) -viewcov "$(QUESTA_COVERAGE_UCDB)"

open-coverage-questa-html:
	@test -f "$(QUESTA_COVERAGE_HTML_INDEX)" || { echo "HTML report '$(QUESTA_COVERAGE_HTML_INDEX)' not found. Run 'make coverage-questa' first."; exit 1; }
	$(HTML_VIEWER) "$(QUESTA_COVERAGE_HTML_INDEX)"

open-coverage-html:
	@test -f "$(COVERAGE_HTML_INDEX)" || { echo "HTML report '$(COVERAGE_HTML_INDEX)' not found. Run 'make coverage' first."; exit 1; }
	$(HTML_VIEWER) "$(COVERAGE_HTML_INDEX)"

waves: test
	$(MAKE) open-waves WAVE="$(WAVE)" GTKWAVE_SAVE="$(GTKWAVE_SAVE)" \
		GTKWAVE="$(GTKWAVE)" GTKWAVE_ARGS="$(GTKWAVE_ARGS)" \
		GTKWAVE_STEMS="$(GTKWAVE_STEMS)"

open-waves:
	@test -f "$(WAVE)" || { echo "Waveform '$(WAVE)' not found. Run 'make test' first."; exit 1; }
	$(MAKE) gtkwave-stems GTKWAVE_STEMS="$(GTKWAVE_STEMS)"
	if test -f "$(GTKWAVE_SAVE)"; then \
		$(GTKWAVE) $(GTKWAVE_ARGS) -t "$(GTKWAVE_STEMS)" "$(WAVE)" "$(GTKWAVE_SAVE)"; \
	else \
		$(GTKWAVE) $(GTKWAVE_ARGS) -t "$(GTKWAVE_STEMS)" "$(WAVE)"; \
	fi

waves-surfer: test
	$(MAKE) open-waves-surfer WAVE="$(WAVE)" STATE="$(STATE)" SURFER="$(SURFER)"

open-waves-surfer:
	@test -f "$(WAVE)" || { echo "Waveform '$(WAVE)' not found. Run 'make test' first."; exit 1; }
	if test -f "$(STATE)"; then \
		$(SURFER) --state-file "$(STATE)" "$(WAVE)"; \
	else \
		$(SURFER) "$(WAVE)"; \
	fi

gtkwave-stems:
	mkdir -p "$(GTKWAVE_STEMS_DIR)" "$(dir $(GTKWAVE_STEMS))"
	verilator -Wno-fatal --json-only --bbox-sys --timing --sv \
		--top-module "$(GTKWAVE_STEMS_TOP)" --Mdir "$(GTKWAVE_STEMS_DIR)" \
		$(SV_INCLUDE_FLAGS) $(GTKWAVE_STEMS_DEFINES) $(GTKWAVE_STEMS_SOURCES)
	$(JSON2STEMS) "$(GTKWAVE_STEMS_META)" "$(GTKWAVE_STEMS_JSON)" "$(GTKWAVE_STEMS)"
	@echo "GTKWave stems: $(GTKWAVE_STEMS)"

waves-questa:
	$(MAKE) test-questa QUESTA_GUI=1 QUESTA_DO="$(QUESTA_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" \
		QUESTA_ARGS="-voptargs=+acc -debugdb" \
		QUESTA_WAVE="$(QUESTA_WAVE)" ABV="$(ABV)" UV="$(UV)"

open-waves-questa:
	@test -f "$(QUESTA_WAVE)" || { echo "Waveform '$(QUESTA_WAVE)' not found. Run 'make test-questa' first."; exit 1; }
	if test -f "$(QUESTA_DO)"; then \
		$(VSIM) -view "$(QUESTA_WAVE)" -do "$(QUESTA_DO)"; \
	else \
		$(VSIM) -view "$(QUESTA_WAVE)"; \
	fi

clean:
	rm -rf build work transcript
