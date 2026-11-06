"""Per-viewer profiles describing how each waveform viewer is launched.

Each simulator has one waveform viewer. A profile declares the simulator whose
wave format it reads (``wave_sim``) and how to open an existing waveform
(:meth:`ViewerProfile.open_waves`).

Add or replace a simulator's viewer by subclassing :class:`ViewerProfile`,
setting ``wave_sim``, and registering an instance in :data:`VIEWERS`, which is
keyed by ``wave_sim``.
"""

import shlex
import shutil
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

# The first GTKWave release with json2stems, which writes RTLBrowse's stems from
# Verilator's JSON design tree.
JSON2STEMS_GTKWAVE = "3.3.125"


class ViewerProfile:
    """Base class for per-viewer waveform behavior."""

    name: str = ""
    wave_sim: str = ""

    def wave_path(self, build_dir: Path) -> Path:
        """Canonical waveform path produced by this viewer's simulator."""
        return SIMULATORS[self.wave_sim].wave_path(build_dir)

    def waves_hint(self, dut: str, config: str) -> str:
        """Return the command that generates this viewer's waveform artifacts."""
        command = make_target_command(
            "waves",
            simulator=self.wave_sim,
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
        config: str,
    ) -> None:
        raise NotImplementedError


def drop_builtin_modules(stems: Path) -> None:
    """Remove the modules whose file is ``<built-in>`` from the RTLBrowse *stems*.

    Verilator's tree lists internal modules, such as ``$unit`` and
    ``__Vconstpool``, which have no source: RTLBrowse would list them in its
    hierarchy and fail to open them.
    """
    lines = stems.read_text(encoding="utf-8").splitlines(keepends=True)

    def is_builtin_module(line: str) -> bool:
        fields = line.split()
        return fields[:2] == ["++", "module"] and fields[3:5] == ["file", "<built-in>"]

    stems.write_text("".join(line for line in lines if not is_builtin_module(line)), "utf-8")


class GtkwaveProfile(ViewerProfile):
    """GTKWave, with its RTLBrowse window unless ``NO_RTLBROWSE`` is set.

    RTLBrowse reads stems, which GTKWave's ``json2stems`` writes from Verilator's
    design tree, without Verilator's internal modules
    (:func:`drop_builtin_modules`).
    """

    name = "gtkwave"
    wave_sim = "verilator"

    @override
    def open_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        dut: str,
        config: str,
    ) -> None:
        wave = self.wave_path(build_dir)
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
            top = dut
            json_dir = build_dir / "rtlbrowse"
            tree_json = json_dir / f"V{top}.tree.json"
            tree_meta = json_dir / f"V{top}.tree.meta.json"
            stems = json_dir / f"{top}.stems"
            require(tree_json, self.waves_hint(dut, config))
            require(tree_meta, self.waves_hint(dut, config))
            json2stems = env_str("JSON2STEMS", "json2stems")
            if shutil.which(json2stems) is None:
                raise SystemExit(
                    f"{json2stems}: command not found. It comes with GTKWave "
                    f"{JSON2STEMS_GTKWAVE} or newer: install that, point JSON2STEMS at it, "
                    "or skip RTLBrowse with NO_RTLBROWSE=1."
                )
            run([json2stems, str(tree_meta), str(tree_json), str(stems)], cwd=build_dir)
            drop_builtin_modules(stems)
            print(f"GTKWave stems: {stems}")
            cmd += ["-t", str(stems)]
        cmd.append(str(wave))
        if save.is_file():
            cmd.append(str(save))
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
        config: str,
    ) -> None:
        wave = self.wave_path(build_dir)
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
        config: str,
    ) -> None:
        wave = self.wave_path(build_dir)
        require(wave, self.waves_hint(dut, config))
        daidir = build_dir / "simv.daidir"
        rc = project_path_from_env("VERDI_RC", project_dir, project_dir / "waves" / f"{dut}.rc")
        cmd = [*verdi_command(), "-dbdir", str(daidir), "-ssf", str(wave)]
        if rc.is_file():
            cmd.extend(["-sswr", str(rc)])
        run(cmd, cwd=build_dir)


VIEWERS: dict[str, ViewerProfile] = {
    profile.wave_sim: profile
    for profile in (GtkwaveProfile(), QuestaViewerProfile(), VerdiProfile())
}
