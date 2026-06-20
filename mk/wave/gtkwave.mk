# GTKWave viewer profile (the default). The top-level Makefile includes this
# file when VIEWER=gtkwave. GTKWave reads the Verilator VCD, so WAVE_SIM pins
# the producing simulator to verilator; the top-level Makefile then includes
# mk/sim/verilator.mk, which provides WAVE, BUILD_DIR, and the SV source vars
# this file uses.
#
# The `waves`/`open-waves` recipes also generate GTKWave RTL-browser "stems" so
# waveform signals link back to source, and load waves/top.gtkw when present.
#
# To add a viewer, copy this file to mk/wave/<viewer>.mk, set WAVE_SIM to the
# simulator whose wave format it reads, and define `waves`/`open-waves`.
WAVE_SIM := verilator
GTKWAVE ?= gtkwave
GTKWAVE_ARGS ?= -o
JSON2STEMS ?= json2stems
GTKWAVE_SAVE ?= waves/top.gtkw
GTKWAVE_STEMS_TOP ?= top
GTKWAVE_STEMS_DIR ?= $(BUILD_DIR)/rtlbrowse
GTKWAVE_STEMS ?= $(GTKWAVE_STEMS_DIR)/$(GTKWAVE_STEMS_TOP).stems
GTKWAVE_STEMS_JSON ?= $(GTKWAVE_STEMS_DIR)/V$(GTKWAVE_STEMS_TOP).tree.json
GTKWAVE_STEMS_META ?= $(GTKWAVE_STEMS_DIR)/V$(GTKWAVE_STEMS_TOP).tree.meta.json
GTKWAVE_STEMS_SOURCES = $(SV_SOURCES)
GTKWAVE_STEMS_DEFINES = $(if $(filter 1 true yes on,$(ABV)),+define+ABV)

waves: test
	$(MAKE) open-waves VIEWER="$(VIEWER)"

open-waves:
	@test -f "$(WAVE)" || { echo "Waveform '$(WAVE)' not found. Run 'make test' first."; exit 1; }
	$(MAKE) gtkwave-stems
	if test -f "$(GTKWAVE_SAVE)"; then \
		$(GTKWAVE) $(GTKWAVE_ARGS) -t "$(GTKWAVE_STEMS)" "$(WAVE)" "$(GTKWAVE_SAVE)"; \
	else \
		$(GTKWAVE) $(GTKWAVE_ARGS) -t "$(GTKWAVE_STEMS)" "$(WAVE)"; \
	fi

# Generate GTKWave RTL-browser "stems" so waveform signals link back to source.
gtkwave-stems:
	mkdir -p "$(GTKWAVE_STEMS_DIR)" "$(dir $(GTKWAVE_STEMS))"
	verilator -Wno-fatal --json-only --bbox-sys --timing --sv \
		--top-module "$(GTKWAVE_STEMS_TOP)" --Mdir "$(GTKWAVE_STEMS_DIR)" \
		$(SV_INCLUDE_FLAGS) $(GTKWAVE_STEMS_DEFINES) $(GTKWAVE_STEMS_SOURCES)
	$(JSON2STEMS) "$(GTKWAVE_STEMS_META)" "$(GTKWAVE_STEMS_JSON)" "$(GTKWAVE_STEMS)"
	@echo "GTKWave stems: $(GTKWAVE_STEMS)"
