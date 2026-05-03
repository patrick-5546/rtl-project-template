UV ?= uv
SIM ?= verilator
SURFER ?= surfer
GTKWAVE ?= gtkwave
WAVE ?= build/sim/dump.vcd
STATE ?= waves/top.surf.ron
GTKWAVE_SAVE ?= waves/top.gtkw

SV_SOURCES := rtl/top.sv

.PHONY: all check clean format lint py-format py-format-check py-lint py-type sim sv-format \
	sv-format-check sv-lint sync test verilator-lint waves waves-gtkwave

all: check test

sync:
	$(UV) sync

test: sync
	SIM=$(SIM) $(UV) run pytest

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
	test -f "$(WAVE)"
	if test -f "$(STATE)"; then \
		$(SURFER) --state-file "$(STATE)" "$(WAVE)"; \
	else \
		$(SURFER) "$(WAVE)"; \
	fi

waves-gtkwave: test
	test -f "$(WAVE)"
	if test -f "$(GTKWAVE_SAVE)"; then \
		$(GTKWAVE) "$(WAVE)" "$(GTKWAVE_SAVE)"; \
	else \
		$(GTKWAVE) "$(WAVE)"; \
	fi

clean:
	rm -rf build .pytest_cache .ruff_cache .ty .venv __pycache__ tests/__pycache__
