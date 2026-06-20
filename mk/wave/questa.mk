# Questa viewer profile. The top-level Makefile includes this file when
# VIEWER=questa. Questa reads its native WLF, so WAVE_SIM pins the producing
# simulator to questa; mk/sim/questa.mk then provides QUESTA_WAVE, QUESTA_DO,
# and VSIM.
#
# Unlike the file-based viewers, Questa shows waves in its live GUI: `waves`
# runs the regression in the interactive GUI rather than dumping a file to
# reopen, while `open-waves` reopens an existing WLF.
#
# To add a viewer, see mk/wave/gtkwave.mk.
WAVE_SIM := questa

waves:
	$(MAKE) test SIM=questa QUESTA_GUI=1 QUESTA_DO="$(QUESTA_DO)" \
		TEST="$(TEST)" TEST_FILTER="$(TEST_FILTER)" REBUILD="$(REBUILD)" \
		QUESTA_ARGS="-voptargs=+acc -debugdb" \
		QUESTA_WAVE="$(QUESTA_WAVE)" ABV="$(ABV)" UV="$(UV)"

open-waves:
	@test -f "$(QUESTA_WAVE)" || { echo "Waveform '$(QUESTA_WAVE)' not found. Run 'make test SIM=questa' first."; exit 1; }
	if test -f "$(QUESTA_DO)"; then \
		$(VSIM) -view "$(QUESTA_WAVE)" -do "$(QUESTA_DO)"; \
	else \
		$(VSIM) -view "$(QUESTA_WAVE)"; \
	fi
