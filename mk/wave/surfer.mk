# Surfer viewer profile. The top-level Makefile includes this file when
# VIEWER=surfer. Surfer reads the same Verilator VCD as GTKWave, so WAVE_SIM
# pins the producing simulator to verilator; mk/sim/verilator.mk then provides
# WAVE. The `open-waves` recipe loads waves/top.surf.ron (STATE) when present.
#
# To add a viewer, see mk/wave/gtkwave.mk.
WAVE_SIM := verilator
SURFER ?= surfer
STATE ?= waves/top.surf.ron

waves: test
	$(MAKE) open-waves VIEWER="$(VIEWER)"

open-waves:
	@test -f "$(WAVE)" || { echo "Waveform '$(WAVE)' not found. Run 'make test' first."; exit 1; }
	if test -f "$(STATE)"; then \
		$(SURFER) --state-file "$(STATE)" "$(WAVE)"; \
	else \
		$(SURFER) "$(WAVE)"; \
	fi
