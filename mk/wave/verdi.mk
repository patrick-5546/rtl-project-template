# Verdi viewer profile. The top-level Makefile includes this file when
# VIEWER=verdi. Verdi reads VCS's native FSDB, so WAVE_SIM pins the producing
# simulator to vcs; the top-level Makefile then includes mk/sim/vcs.mk, which
# provides VCS_WAVE, VCS_DAIDIR, VERDI, and VERDI_ARGS.
#
# Like the GTKWave/Surfer viewers (and unlike Questa's live GUI), Verdi is
# file-based: `waves` runs the regression to dump an FSDB, then `open-waves`
# opens it with source-linked debug. Both load a reusable Verdi session/restore
# file (waves/top.rc) with `-sswr` when present, the same way GTKWave loads
# top.gtkw and Questa sources top.do.
#
# To add a viewer, see mk/wave/gtkwave.mk.
WAVE_SIM := vcs
VERDI_RC ?= waves/top.rc

waves: test
	$(MAKE) open-waves VIEWER="$(VIEWER)"

open-waves:
	@test -f "$(VCS_WAVE)" || { echo "Waveform '$(VCS_WAVE)' not found. Run 'make test SIM=vcs' first."; exit 1; }
	if test -f "$(VERDI_RC)"; then \
		$(VERDI) $(VERDI_ARGS) -dbdir "$(VCS_DAIDIR)" -ssf "$(VCS_WAVE)" -sswr "$(VERDI_RC)"; \
	else \
		$(VERDI) $(VERDI_ARGS) -dbdir "$(VCS_DAIDIR)" -ssf "$(VCS_WAVE)"; \
	fi
