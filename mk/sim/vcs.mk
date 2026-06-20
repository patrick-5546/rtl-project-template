# VCS simulator profile. The top-level Makefile includes this file when
# SIM=vcs. It owns everything VCS-specific:
#
#   * BUILD_DIR / VCS_WAVE      build output dir and the native FSDB the Verdi
#                               viewer reads (see mk/wave/verdi.mk).
#   * VCS_DAIDIR                simv.daidir knowledge database Verdi uses for
#                               source-linked debug (built by VCS's -kdb).
#   * NO_COVERGROUPS            0: VCS collects SV covergroups natively, so they
#                               are kept (mirrored in tests/runner.py).
#   * PYTEST                    adds --timeout=0 so slower VCS builds/runs are
#                               not killed by pytest-timeout.
#   * VCS / URG / VERDI         executables for runs, coverage reports, and the
#                               coverage/waveform GUI.
#   * VCS_COVERAGE_*            coverage VDB and urg HTML report paths.
#   * coverage / open-coverage / open-coverage-html recipes.
#
# Waveforms are produced here (FSDB) but viewed by Verdi (mk/wave/verdi.mk),
# mirroring the Questa sim/viewer split. To add a simulator, copy this file to
# mk/sim/<sim>.mk, adjust the variables and recipes, and add a matching entry to
# the registry in tests/runner.py.
BUILD_DIR ?= build/vcs
PYTEST := $(UV) run pytest -s --timeout=0
NO_COVERGROUPS ?= 0

VCS ?= vcs
URG ?= urg
VERDI ?= verdi
VERDI_ARGS ?= -nologo
VCS_WAVE ?= $(BUILD_DIR)/dump.fsdb
VCS_DAIDIR ?= $(BUILD_DIR)/simv.daidir

COVERAGE_DAT ?= $(BUILD_DIR)/coverage.vdb
VCS_COVERAGE_VDB ?= $(BUILD_DIR)/coverage.vdb
VCS_COVERAGE_HTML_DIR ?= $(BUILD_DIR)/urgReport
VCS_COVERAGE_HTML_INDEX ?= $(VCS_COVERAGE_HTML_DIR)/dashboard.html

coverage:
	$(MAKE) test SIM=vcs ABV=1 HDL_COVERAGE=1 \
		COVERAGE_DAT="$(VCS_COVERAGE_VDB)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)"
	rm -rf "$(VCS_COVERAGE_HTML_DIR)"
	$(URG) -dir "$(VCS_COVERAGE_VDB)" -report "$(VCS_COVERAGE_HTML_DIR)" -format both
	@grep -A2 "Total Coverage Summary" "$(VCS_COVERAGE_HTML_DIR)/dashboard.txt" || true
	@echo "Coverage VDB: $(VCS_COVERAGE_VDB)"
	@echo "HTML report: $(VCS_COVERAGE_HTML_INDEX)"
	@echo "Text report: $(VCS_COVERAGE_HTML_DIR)/dashboard.txt"

open-coverage:
	@test -d "$(VCS_COVERAGE_VDB)" || { echo "Coverage VDB '$(VCS_COVERAGE_VDB)' not found. Run 'make coverage SIM=vcs' first."; exit 1; }
	$(VERDI) $(VERDI_ARGS) -cov -covdir "$(VCS_COVERAGE_VDB)"

open-coverage-html:
	@test -f "$(VCS_COVERAGE_HTML_INDEX)" || { echo "HTML report '$(VCS_COVERAGE_HTML_INDEX)' not found. Run 'make coverage SIM=vcs' first."; exit 1; }
	$(HTML_VIEWER) "$(VCS_COVERAGE_HTML_INDEX)"
