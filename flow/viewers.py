"""Per-viewer profiles describing how each waveform viewer is launched.

Each profile declares the simulator whose wave format it reads (``wave_sim``),
whether it is a live-GUI flow (Questa) or a file-based one
(GTKWave/Surfer/Verdi), and how to open an existing waveform
(:meth:`ViewerProfile.open_waves`). The CLI (:mod:`flow.cli`) runs the
regression and then drives the viewer.

Add a viewer by subclassing :class:`ViewerProfile`, setting ``wave_sim``, and
registering an instance in :data:`VIEWERS`.
"""

import shlex
from pathlib import Path

from flow.runner import (
    env_flag,
    env_str,
    project_path_from_env,
    project_paths_from_list_file,
    require,
    run,
)


class ViewerProfile:
    """Base class for per-viewer waveform behavior.

    ``wave_sim`` pins the simulator that produces the format this viewer reads,
    so wave targets run under the right simulator. ``live_gui`` viewers show
    waves in an interactive run (no separate file to reopen); file-based viewers
    dump a waveform that :meth:`open_waves` later opens.
    """

    name: str = ""
    wave_sim: str = ""
    live_gui: bool = False

    def waves_run_env(self, project_dir: Path) -> dict[str, str]:
        """Extra environment for the ``waves`` regression (live-GUI viewers)."""
        return {}

    def open_waves(self, project_dir: Path, build_dir: Path) -> None:
        raise NotImplementedError


class GtkwaveProfile(ViewerProfile):
    name = "gtkwave"
    wave_sim = "verilator"

    def open_waves(self, project_dir: Path, build_dir: Path) -> None:
        wave = project_path_from_env("WAVE", project_dir, build_dir / "dump.vcd")
        require(wave, "Run 'make test' first.")
        stems = self._generate_stems(project_dir, build_dir)
        gtkwave = env_str("GTKWAVE", "gtkwave")
        gtkwave_args = shlex.split(env_str("GTKWAVE_ARGS", "-o"))
        save = project_path_from_env(
            "GTKWAVE_SAVE", project_dir, project_dir / "waves" / "top.gtkw"
        )
        cmd = [gtkwave, *gtkwave_args, "-t", str(stems), str(wave)]
        if save.is_file():
            cmd.append(str(save))
        run(cmd)

    def _generate_stems(self, project_dir: Path, build_dir: Path) -> Path:
        """Generate GTKWave RTL-browser "stems" so signals link back to source."""
        top = env_str("GTKWAVE_STEMS_TOP", "top")
        stems_dir = build_dir / "rtlbrowse"
        stems = stems_dir / f"{top}.stems"
        tree_json = stems_dir / f"V{top}.tree.json"
        tree_meta = stems_dir / f"V{top}.tree.meta.json"
        sources, includes = project_paths_from_list_file(
            "SV_SOURCES_FILE", project_dir, project_dir / "rtl" / "sources.vf"
        )
        verilator = env_str("VERILATOR", "verilator")
        json2stems = env_str("JSON2STEMS", "json2stems")
        defines = ["+define+ABV"] if env_flag("ABV", default=False) else []
        stems_dir.mkdir(parents=True, exist_ok=True)
        run(
            [
                verilator,
                "-Wno-fatal",
                "--json-only",
                "--bbox-sys",
                "--timing",
                "--sv",
                "--top-module",
                top,
                "--Mdir",
                str(stems_dir),
                *[f"-I{d}" for d in includes],
                *defines,
                *[str(s) for s in sources],
            ]
        )
        run([json2stems, str(tree_meta), str(tree_json), str(stems)])
        print(f"GTKWave stems: {stems}")
        return stems


class SurferProfile(ViewerProfile):
    name = "surfer"
    wave_sim = "verilator"

    def open_waves(self, project_dir: Path, build_dir: Path) -> None:
        wave = project_path_from_env("WAVE", project_dir, build_dir / "dump.vcd")
        require(wave, "Run 'make test' first.")
        surfer = env_str("SURFER", "surfer")
        state = project_path_from_env("STATE", project_dir, project_dir / "waves" / "top.surf.ron")
        cmd = [surfer]
        if state.is_file():
            cmd.extend(["--state-file", str(state)])
        cmd.append(str(wave))
        run(cmd)


class QuestaViewerProfile(ViewerProfile):
    name = "questa"
    wave_sim = "questa"
    live_gui = True

    def waves_run_env(self, project_dir: Path) -> dict[str, str]:
        # The live GUI needs full visibility (+acc) and the debug database.
        return {"QUESTA_ARGS": "-voptargs=+acc -debugdb"}

    def open_waves(self, project_dir: Path, build_dir: Path) -> None:
        questa_wave = project_path_from_env("QUESTA_WAVE", project_dir, build_dir / "vsim.wlf")
        require(questa_wave, "Run 'make test SIM=questa' first.")
        vsim = env_str("VSIM", "vsim")
        do = project_path_from_env("QUESTA_DO", project_dir, project_dir / "waves" / "top.do")
        cmd = [vsim, "-view", str(questa_wave)]
        if do.is_file():
            cmd.extend(["-do", str(do)])
        run(cmd)


class VerdiProfile(ViewerProfile):
    name = "verdi"
    wave_sim = "vcs"

    def open_waves(self, project_dir: Path, build_dir: Path) -> None:
        vcs_wave = project_path_from_env("VCS_WAVE", project_dir, build_dir / "dump.fsdb")
        require(vcs_wave, "Run 'make test SIM=vcs' first.")
        verdi = env_str("VERDI", "verdi")
        verdi_args = shlex.split(env_str("VERDI_ARGS", "-nologo"))
        daidir = project_path_from_env("VCS_DAIDIR", project_dir, build_dir / "simv.daidir")
        rc = project_path_from_env("VERDI_RC", project_dir, project_dir / "waves" / "top.rc")
        cmd = [verdi, *verdi_args, "-dbdir", str(daidir), "-ssf", str(vcs_wave)]
        if rc.is_file():
            cmd.extend(["-sswr", str(rc)])
        run(cmd)


VIEWERS: dict[str, ViewerProfile] = {
    profile.name: profile
    for profile in (GtkwaveProfile(), SurferProfile(), QuestaViewerProfile(), VerdiProfile())
}
