# Questa simulator profile. The top-level Makefile includes this file when
# SIM=questa. It owns everything Questa-specific:
#
#   * BUILD_DIR / QUESTA_WAVE  build output dir and the native WLF the Questa
#                              viewer reads (see mk/wave/questa.mk).
#   * PYTEST                   adds --timeout=0 so the interactive GUI flow is
#                              not killed by pytest-timeout.
#   * QUESTA_* / VSIM / VCOVER paths and executables for runs and reports.
#   * coverage / open-coverage / open-coverage-html recipes.
#
# Override the GUI executable with VSIM (not MODELSIM, which Questa treats as a
# modelsim.ini variable). To add a simulator, see mk/sim/verilator.mk.
BUILD_DIR ?= build/questa
PYTEST := $(UV) run pytest -s --timeout=0
NO_COVERGROUPS ?= 0

VSIM ?= vsim
VCOVER ?= vcover
QUESTA_WAVE ?= $(BUILD_DIR)/vsim.wlf
QUESTA_DO ?= waves/top.do

COVERAGE_DAT ?= $(BUILD_DIR)/coverage.dat
QUESTA_COVERAGE_UCDB ?= $(BUILD_DIR)/coverage.ucdb
QUESTA_COVERAGE_HTML_DIR ?= $(BUILD_DIR)/coverage_html
QUESTA_COVERAGE_HTML_INDEX ?= $(QUESTA_COVERAGE_HTML_DIR)/index.html

coverage:
	$(MAKE) test SIM=questa ABV=1 HDL_COVERAGE=1 \
		COVERAGE_DAT="$(QUESTA_COVERAGE_UCDB)" \
		QUESTA_ARGS="-extendedtogglemode 1" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)"
	$(VCOVER) report -summary "$(QUESTA_COVERAGE_UCDB)"
	rm -rf "$(QUESTA_COVERAGE_HTML_DIR)"
	$(VCOVER) report -html -details -output "$(QUESTA_COVERAGE_HTML_DIR)" "$(QUESTA_COVERAGE_UCDB)"
	@echo "Coverage UCDB: $(QUESTA_COVERAGE_UCDB)"
	@echo "HTML report: $(QUESTA_COVERAGE_HTML_INDEX)"

open-coverage:
	@test -f "$(QUESTA_COVERAGE_UCDB)" || { echo "UCDB '$(QUESTA_COVERAGE_UCDB)' not found. Run 'make coverage SIM=questa' first."; exit 1; }
	$(VSIM) -viewcov "$(QUESTA_COVERAGE_UCDB)"

open-coverage-html:
	@test -f "$(QUESTA_COVERAGE_HTML_INDEX)" || { echo "HTML report '$(QUESTA_COVERAGE_HTML_INDEX)' not found. Run 'make coverage SIM=questa' first."; exit 1; }
	$(HTML_VIEWER) "$(QUESTA_COVERAGE_HTML_INDEX)"
