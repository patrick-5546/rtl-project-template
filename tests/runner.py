import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from cocotb_tools.runner import get_runner


@dataclass
class RunConfig:
    """Inputs the per-simulator profiles use to build their arguments."""

    hdl_coverage: bool
    gui: bool
    waves: bool
    coverage_dat: Path
    questa_wave: Path
    questa_do: Path
    questa_args: list[str]
    vcs_wave: Path
    build_dir: Path
    hdl_toplevel: str


@dataclass
class SimArgs:
    """Per-simulator arguments handed to the cocotb runner."""

    build_args: list[str] = field(default_factory=list)
    plusargs: list[str] = field(default_factory=list)
    test_args: list[str] = field(default_factory=list)
    pre_cmd: list[str] | None = None
    sources: list[Path] = field(default_factory=list)


def write_fsdb_dump_module(build_dir: Path, hdl_toplevel: str) -> Path:
    """Write a Verdi FSDB dump module into *build_dir* and return its path.

    VCS does not auto-dump waveforms, so (mirroring cocotb's Icarus dump-file
    approach) we generate a tiny top module that opens an FSDB and dumps the
    *hdl_toplevel* hierarchy.  The ``+fsdbfile=`` plusarg selects the output
    path; the ``$fsdb*`` system tasks come from VCS's ``-kdb`` flag, so no
    Verdi PLI (``novas.tab``/``pli.a``) needs to be linked explicitly.

    The module is bracketed with ``// VCS coverage off``/``on`` pragmas so it is
    excluded from the ``-cm`` coverage model; reports then reflect the design
    only, instead of being dragged down by this testbench wrapper.
    """
    build_dir.mkdir(parents=True, exist_ok=True)
    dump_module = build_dir / "cocotb_fsdb_dump.sv"
    contents = (
        "// VCS coverage off\n"
        "module cocotb_fsdb_dump;\n"
        "  initial begin\n"
        "    string fsdbfile;\n"
        '    if (!$value$plusargs("fsdbfile=%s", fsdbfile)) fsdbfile = "dump.fsdb";\n'
        "    $fsdbDumpfile(fsdbfile);\n"
        f"    $fsdbDumpvars(0, {hdl_toplevel});\n"
        "  end\n"
        "endmodule\n"
        "// VCS coverage on\n"
    )
    # Only rewrite when content changes so the file's mtime stays stable and
    # REBUILD=0 (cocotb's ``outdated`` mtime check) keeps reusing the build.
    if not dump_module.is_file() or dump_module.read_text() != contents:
        dump_module.write_text(contents)
    return dump_module


class SimulatorProfile:
    """Base class for per-simulator build/test argument construction.

    Add a simulator by subclassing this, setting ``name`` (and the
    ``supports_*`` capability flags), implementing :meth:`configure`, and adding
    an instance to ``SIMULATORS``. This is the Python mirror of the per-tool
    Makefile profiles in ``mk/sim/<name>.mk``. Simulators that cocotb supports
    but that have no profile here still run with default arguments.
    """

    name: str = ""
    supports_coverage: bool = False
    supports_gui: bool = False

    def configure(self, cfg: RunConfig) -> SimArgs:
        return SimArgs()


class VerilatorProfile(SimulatorProfile):
    name = "verilator"
    supports_coverage = True

    def configure(self, cfg: RunConfig) -> SimArgs:
        args = SimArgs()
        if cfg.hdl_coverage:
            args.build_args.append("--coverage")
            args.plusargs.append(f"+verilator+coverage+file+{cfg.coverage_dat}")
        return args


class QuestaProfile(SimulatorProfile):
    name = "questa"
    supports_coverage = True
    supports_gui = True

    def configure(self, cfg: RunConfig) -> SimArgs:
        args = SimArgs()
        if cfg.hdl_coverage:
            args.build_args.extend(["-cover", "bcesfx"])
        cfg.questa_wave.parent.mkdir(parents=True, exist_ok=True)
        args.test_args = [
            *cfg.questa_args,
            "-wlf",
            str(cfg.questa_wave),
            "-nowlfdeleteonquit",
        ]
        if cfg.hdl_coverage:
            args.test_args.append("-coverage")
        if cfg.gui:
            gui_commands = ["log -recursive /*", "run -all"]
            if cfg.hdl_coverage:
                gui_commands.insert(0, f"coverage save -onexit {cfg.coverage_dat}")
            if cfg.questa_do.is_file():
                gui_commands.append(f"source {{{cfg.questa_do.as_posix()}}}")
            args.pre_cmd = ["; ".join(gui_commands)]
        elif cfg.hdl_coverage:
            args.pre_cmd = [f"coverage save -onexit {cfg.coverage_dat}"]
        return args


class VcsProfile(SimulatorProfile):
    name = "vcs"
    supports_coverage = True

    def configure(self, cfg: RunConfig) -> SimArgs:
        args = SimArgs()
        # cocotb's VCS runner passes no timescale, so VCS would default to 1 s
        # precision and reject the ns-scale clock; pin it explicitly.
        args.build_args.append("-timescale=1ns/1ps")
        if cfg.waves:
            cfg.vcs_wave.parent.mkdir(parents=True, exist_ok=True)
            # -kdb gives both the native $fsdb* tasks and the Verdi source DB;
            # the generated dump module is an extra top alongside the DUT.
            args.sources.append(write_fsdb_dump_module(cfg.build_dir, cfg.hdl_toplevel))
            args.build_args.extend(["-kdb", "-top", "cocotb_fsdb_dump"])
            args.plusargs.append(f"+fsdbfile={cfg.vcs_wave}")
        if cfg.hdl_coverage:
            cm_args = ["-cm", "line+cond+fsm+tgl+branch+assert", "-cm_dir", str(cfg.coverage_dat)]
            args.build_args.extend(cm_args)
            args.test_args.extend(cm_args)
        return args


SIMULATORS: dict[str, SimulatorProfile] = {
    profile.name: profile for profile in (VerilatorProfile(), QuestaProfile(), VcsProfile())
}


def env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def project_path_from_env(name: str, project_dir: Path, default: Path) -> Path:
    value = os.environ.get(name)
    path = Path(value) if value else default
    return path if path.is_absolute() else project_dir / path


def project_paths_from_list_file(
    name: str, project_dir: Path, default: Path
) -> tuple[list[Path], list[Path]]:
    """Parse a Verilator-style ``.vf`` source list into sources and include dirs.

    Each non-comment, non-blank line is one of:

    * a path (compilation source, validated as a regular file),
    * ``+incdir+<dir>`` (preprocessor include directory, validated as
      an existing directory),
    * ``+verible+<file>`` (Verible-only file, validated as a file but
      not returned — the cocotb runner has no use for bare-SVA include
      files that aren't compilation units).

    Anything else raises.
    """
    list_file = project_path_from_env(name, project_dir, default)
    sources: list[Path] = []
    includes: list[Path] = []
    for line in list_file.read_text().splitlines():
        entry = line.split("#", maxsplit=1)[0].strip()
        if not entry:
            continue
        if entry.startswith("+incdir+"):
            raw = entry[len("+incdir+") :]
            path = Path(raw)
            if not path.is_absolute():
                path = project_dir / path
            if not path.is_dir():
                raise FileNotFoundError(
                    f"{list_file}: '+incdir+{raw}' does not resolve to a directory ({path})"
                )
            includes.append(path)
        elif entry.startswith("+verible+"):
            raw = entry[len("+verible+") :]
            path = Path(raw)
            if not path.is_absolute():
                path = project_dir / path
            if not path.is_file():
                raise FileNotFoundError(
                    f"{list_file}: '+verible+{raw}' does not resolve to a file ({path})"
                )
            # Validated for parity with the Makefile but not returned.
        else:
            path = Path(entry)
            if not path.is_absolute():
                path = project_dir / path
            if not path.is_file():
                raise FileNotFoundError(
                    f"{list_file}: '{entry}' does not resolve to a file ({path})"
                )
            sources.append(path)
    return sources, includes


def build_and_test(hdl_toplevel: str, test_module: str) -> None:
    """Build RTL and run cocotb tests for *hdl_toplevel*.

    All other configuration (SIM, BUILD_DIR, TEST, ABV, HDL_COVERAGE,
    QUESTA_GUI, etc.) is read from environment variables, matching the
    existing Makefile-driven workflow.
    """
    project_dir = Path(__file__).resolve().parents[1]
    test_dir = Path(__file__).resolve().parent
    simulator = os.environ.get("SIM", "verilator")
    build_dir = project_path_from_env("BUILD_DIR", project_dir, project_dir / "build" / simulator)
    questa_wave = project_path_from_env(
        "QUESTA_WAVE",
        project_dir,
        project_dir / "build" / "questa" / "vsim.wlf",
    )
    questa_do = project_path_from_env(
        "QUESTA_DO",
        project_dir,
        project_dir / "waves" / f"{hdl_toplevel}.do",
    )
    vcs_wave = project_path_from_env("VCS_WAVE", project_dir, build_dir / "dump.fsdb")
    pythonpath = os.pathsep.join(filter(None, [str(test_dir), os.environ.get("PYTHONPATH", "")]))
    selected_test = os.environ.get("TEST") or None
    test_filter = os.environ.get("TEST_FILTER") or None
    rebuild = env_flag("REBUILD", default=True)
    abv = env_flag("ABV", default=False)
    no_covergroups = env_flag("NO_COVERGROUPS", default=False)
    hdl_coverage = env_flag("HDL_COVERAGE", default=False)
    questa_gui = env_flag("QUESTA_GUI", default=False)
    waves_enabled = env_flag("WAVES", default=True)
    coverage_dat = project_path_from_env(
        "COVERAGE_DAT",
        project_dir,
        build_dir / "coverage.dat",
    )
    sv_sources, sv_include_dirs = project_paths_from_list_file(
        "SV_SOURCES_FILE",
        project_dir,
        project_dir / "rtl" / "sources.vf",
    )
    if selected_test and test_filter:
        raise ValueError("Set either TEST or TEST_FILTER, not both.")
    if selected_test:
        test_filter = rf"(^|.*\.){re.escape(selected_test)}$"
    profile = SIMULATORS.get(simulator)
    if hdl_coverage and not (profile and profile.supports_coverage):
        supported = ", ".join(sorted(n for n, p in SIMULATORS.items() if p.supports_coverage))
        raise ValueError(f"HDL_COVERAGE=1 is supported for these simulators: {supported}.")
    if questa_gui and not (profile and profile.supports_gui):
        supported = ", ".join(sorted(n for n, p in SIMULATORS.items() if p.supports_gui))
        raise ValueError(f"QUESTA_GUI=1 is supported for these simulators: {supported}.")

    sources = [*sv_sources]
    defines: dict[str, object] = {}
    if abv:
        defines["ABV"] = 1
    if no_covergroups:
        defines["NO_COVERGROUPS"] = 1

    if hdl_coverage:
        coverage_dat.parent.mkdir(parents=True, exist_ok=True)
    sim_args = (
        profile.configure(
            RunConfig(
                hdl_coverage=hdl_coverage,
                gui=questa_gui,
                waves=waves_enabled,
                coverage_dat=coverage_dat,
                questa_wave=questa_wave,
                questa_do=questa_do,
                questa_args=shlex.split(os.environ.get("QUESTA_ARGS", "")),
                vcs_wave=vcs_wave,
                build_dir=build_dir,
                hdl_toplevel=hdl_toplevel,
            )
        )
        if profile
        else SimArgs()
    )
    build_args = sim_args.build_args
    plusargs = sim_args.plusargs
    test_args = sim_args.test_args
    pre_cmd = sim_args.pre_cmd
    sources.extend(sim_args.sources)

    runner = get_runner(simulator)
    runner.build(
        sources=sources,
        includes=sv_include_dirs,
        defines=defines,
        build_args=build_args,
        hdl_toplevel=hdl_toplevel,
        build_dir=build_dir,
        always=rebuild,
        waves=True,
    )
    runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module=test_module,
        test_filter=test_filter,
        build_dir=build_dir,
        waves=not questa_gui,
        gui=questa_gui,
        extra_env={"PYTHONPATH": pythonpath},
        test_args=test_args,
        plusargs=plusargs,
        pre_cmd=pre_cmd,
    )
