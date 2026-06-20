# Verilator simulator profile. The top-level Makefile includes this file when
# SIM=verilator (the default). It owns everything Verilator-specific:
#
#   * BUILD_DIR / WAVE        build output dir and the VCD the GTKWave and
#                             Surfer viewers read (see mk/wave/*.mk).
#   * NO_COVERGROUPS          Verilator parses but ignores SV covergroups, so
#                             they are excluded here (mirrored in tests/runner.py).
#   * COVERAGE_*              line/branch coverage paths and HTML thresholds.
#   * coverage / open-coverage / open-coverage-html recipes.
#
# To add a simulator, copy this file to mk/sim/<sim>.mk, adjust the variables
# and recipes, and add a matching entry to the registry in tests/runner.py.
BUILD_DIR ?= build/verilator
WAVE ?= $(BUILD_DIR)/dump.vcd
NO_COVERGROUPS ?= 1

COVERAGE_DAT ?= $(BUILD_DIR)/coverage.dat
COVERAGE_ANNOTATION_DIR ?= $(BUILD_DIR)/coverage_annotated
COVERAGE_INFO ?= $(BUILD_DIR)/coverage.info
COVERAGE_HTML_DIR ?= $(BUILD_DIR)/coverage_html
COVERAGE_HTML_INDEX ?= $(COVERAGE_HTML_DIR)/index.html
COVERAGE_MIN_LINES ?= 90
COVERAGE_MIN_BRANCHES ?= 90

coverage:
	$(MAKE) test SIM=verilator BUILD_DIR="$(BUILD_DIR)" \
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

open-coverage:
	@echo "Verilator has no native GUI coverage viewer."
	@echo "Use 'make open-coverage-html' (or 'make open-coverage-html SIM=questa')."

open-coverage-html:
	@test -f "$(COVERAGE_HTML_INDEX)" || { echo "HTML report '$(COVERAGE_HTML_INDEX)' not found. Run 'make coverage' first."; exit 1; }
	$(HTML_VIEWER) "$(COVERAGE_HTML_INDEX)"
