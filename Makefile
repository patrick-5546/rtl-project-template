UV ?= uv
SIM ?= verilator
SURFER ?= surfer
GTKWAVE ?= gtkwave
WAVE ?= build/sim/dump.vcd
STATE ?= waves/top.surf.ron
GTKWAVE_SAVE ?= waves/top.gtkw
TEST ?=
TEST_FILTER ?=
REBUILD ?= 1

SV_SOURCES := rtl/top.sv

.PHONY: all check clean format help lint open-waves open-waves-gtkwave py-format \
	py-format-check py-lint py-type sim sv-format sv-format-check sv-lint sync test \
	test-one verilator-lint waves waves-gtkwave

all: check test

help:
	@echo "Common targets:"
	@echo "  make test                                      Run the full cocotb regression"
	@echo "  make test TEST=enable_high_counts             Run one cocotb test"
	@echo "  make test TEST_FILTER='enable_.*'             Run matching cocotb tests"
	@echo "  make test TEST=enable_high_counts REBUILD=0   Reuse an existing simulator build"
	@echo "  make waves [TEST=...]                         Run tests, then open Surfer"
	@echo "  make waves-gtkwave [TEST=...]                 Run tests, then open GTKWave"
	@echo "  make open-waves                               Open existing waveform in Surfer"
	@echo "  make open-waves-gtkwave                       Open existing waveform in GTKWave"
	@echo "  make lint                                     Run all lint/type checks"
	@echo "  make format                                   Format Python and SystemVerilog"
	@echo "  make clean                                    Remove generated artifacts"

sync:
	$(UV) sync

test: sync
	SIM=$(SIM) TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" $(UV) run pytest -s

test-one:
	@test -n "$(TEST)" || { echo "Usage: make test-one TEST=<cocotb_test_name>"; exit 2; }
	$(MAKE) test TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" SIM="$(SIM)" UV="$(UV)"

sim: test

py-format: sync
	$(UV) run ruff format .

py-format-check: sync
	$(UV) run ruff format --check .

py-lint: sync
	$(UV) run ruff check .

py-type: sync
	$(UV) run ty check

sv-format:
	verible-verilog-format --inplace $(SV_SOURCES)

sv-format-check:
	verible-verilog-format --verify $(SV_SOURCES)

sv-lint:
	verible-verilog-lint $(SV_SOURCES)

verilator-lint:
	verilator --lint-only --timing -Wall --sv $(SV_SOURCES)

lint: py-format-check py-lint py-type sv-format-check sv-lint verilator-lint

check: lint

format: py-format sv-format

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

clean:
	rm -rf build
