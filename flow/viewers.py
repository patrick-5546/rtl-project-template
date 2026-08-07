"""Per-viewer profiles describing how each waveform viewer is launched.

Each profile declares the simulator whose wave format it reads (``wave_sim``)
and how to open an existing waveform (:meth:`ViewerProfile.open_waves`).

Add a viewer by subclassing :class:`ViewerProfile`, setting ``wave_sim``, and
registering an instance in :data:`VIEWERS`.
"""

import shlex
from pathlib import Path
from typing import override

from flow.runner import (
    default_questa_do,
    env_flag,
    env_str,
    make_target_command,
    project_path_from_env,
    require,
    run,
    verdi_command,
    vsim_exe,
)
from flow.simulators import SIMULATORS


class ViewerProfile:
    """Base class for per-viewer waveform behavior."""

    name: str = ""
    wave_sim: str = ""

    def wave_path(self, project_dir: Path, build_dir: Path) -> Path:
        """Canonical waveform path produced by this viewer's simulator."""
        return SIMULATORS[self.wave_sim].wave_path(project_dir, build_dir)

    def waves_hint(self, dut: str, config: str | None) -> str:
        """Return the command that generates this viewer's waveform artifacts."""
        command = make_target_command(
            "waves",
            simulator=self.wave_sim,
            viewer=self.name,
            dut=dut,
            config=config,
            hdl_coverage=env_flag("HDL_COVERAGE", default=False),
        )
        return f"Run '{command}'."

    def open_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        dut: str,
        config: str | None,
    ) -> None:
        raise NotImplementedError


class GtkwaveProfile(ViewerProfile):
    name = "gtkwave"
    wave_sim = "verilator"

    @override
    def open_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        dut: str,
        config: str | None,
    ) -> None:
        wave = self.wave_path(project_dir, build_dir)
        require(wave, self.waves_hint(dut, config))
        gtkwave = env_str("GTKWAVE", "gtkwave")
        gtkwave_args = shlex.split(env_str("GTKWAVE_ARGS", "-o"))
        save = project_path_from_env(
            "GTKWAVE_SAVE",
            project_dir,
            project_dir / "waves" / f"{dut}.gtkw",
        )
        cmd = [gtkwave, *gtkwave_args]
        if not env_flag("NO_RTLBROWSE", default=False):
            top = env_str("GTKWAVE_STEMS_TOP", dut)
            json_dir = build_dir / "rtlbrowse"
            tree_json = json_dir / f"V{top}.tree.json"
            tree_meta = json_dir / f"V{top}.tree.meta.json"
            stems = json_dir / f"{top}.stems"
            require(tree_json, self.waves_hint(dut, config))
            require(tree_meta, self.waves_hint(dut, config))
            run(
                [env_str("JSON2STEMS", "json2stems"), str(tree_meta), str(tree_json), str(stems)],
                cwd=build_dir,
            )
            print(f"GTKWave stems: {stems}")
            cmd += ["-t", str(stems)]
        cmd.append(str(wave))
        if save.is_file():
            cmd.append(str(save))
        run(cmd, cwd=build_dir)


class SurferProfile(ViewerProfile):
    name = "surfer"
    wave_sim = "verilator"

    @override
    def open_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        dut: str,
        config: str | None,
    ) -> None:
        wave = self.wave_path(project_dir, build_dir)
        require(wave, self.waves_hint(dut, config))
        state = project_path_from_env(
            "SURFER_STATE",
            project_dir,
            project_dir / "waves" / f"{dut}.surf.ron",
        )
        cmd = [env_str("SURFER", "surfer")]
        if state.is_file():
            cmd.extend(["--state-file", str(state)])
        cmd.append(str(wave))
        run(cmd, cwd=build_dir)


class QuestaViewerProfile(ViewerProfile):
    name = "questa"
    wave_sim = "questa"

    @override
    def open_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        dut: str,
        config: str | None,
    ) -> None:
        wave = self.wave_path(project_dir, build_dir)
        require(wave, self.waves_hint(dut, config))
        do = default_questa_do(project_dir, dut)
        cmd = [vsim_exe(), "-gui", "-view", str(wave)]
        if do.is_file():
            cmd.extend(["-do", str(do)])
        run(cmd, cwd=build_dir)


class VerdiProfile(ViewerProfile):
    name = "verdi"
    wave_sim = "vcs"

    @override
    def open_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        dut: str,
        config: str | None,
    ) -> None:
        wave = self.wave_path(project_dir, build_dir)
        require(wave, self.waves_hint(dut, config))
        daidir = project_path_from_env("VCS_DAIDIR", project_dir, build_dir / "simv.daidir")
        rc = project_path_from_env("VERDI_RC", project_dir, project_dir / "waves" / f"{dut}.rc")
        cmd = [*verdi_command(), "-dbdir", str(daidir), "-ssf", str(wave)]
        if rc.is_file():
            cmd.extend(["-sswr", str(rc)])
        run(cmd, cwd=build_dir)


VIEWERS: dict[str, ViewerProfile] = {
    profile.name: profile
    for profile in (GtkwaveProfile(), SurferProfile(), QuestaViewerProfile(), VerdiProfile())
}

DEFAULT_VIEWERS: dict[str, str] = {
    "verilator": GtkwaveProfile.name,
    "questa": QuestaViewerProfile.name,
    "vcs": VerdiProfile.name,
}
