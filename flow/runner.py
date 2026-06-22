import os
import re
import shlex
import subprocess
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


def env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def env_str(name: str, default: str) -> str:
    """Return environment variable *name*, or *default* when unset/empty.

    Used by the simulator and viewer profiles to make tool executables (``VSIM``,
    ``VERDI``, ``GTKWAVE``, ``HTML_VIEWER``, ...) overridable from the
    environment (e.g. ``make ... VERDI=/path/to/verdi``).
    """
    value = os.environ.get(name)
    return value if value else default


def run(cmd: list[str]) -> None:
    """Echo and run *cmd*, raising :class:`SystemExit` on a non-zero exit.

    Shared by the simulator/viewer profiles and the CLI to drive external tools
    (coverage reporters, waveform viewers) the way the old Makefile recipes did.
    """
    print("+ " + shlex.join(cmd), flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def require(path: Path, hint: str, *, kind: str = "file") -> None:
    """Exit with a helpful message when *path* (a file or directory) is missing."""
    ok = path.is_dir() if kind == "dir" else path.is_file()
    if not ok:
        raise SystemExit(f"{path} not found. {hint}")


def open_html(index: Path, *, hint: str) -> None:
    """Open an HTML report *index* with ``$HTML_VIEWER`` (default xdg-open)."""
    require(index, hint)
    run([env_str("HTML_VIEWER", "xdg-open"), str(index)])


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
    Makefile-driven workflow. Per-simulator defaults (covergroup support,
    coverage-artifact path, build/test arguments) come from the matching
    profile in :mod:`flow.simulators`.
    """
    # Lazy import: ``flow.simulators`` imports this module, so importing it at
    # module scope would be circular.
    from flow.simulators import SIMULATORS

    project_dir = Path(__file__).resolve().parents[1]
    test_dir = project_dir / "tests"
    simulator = os.environ.get("SIM", "verilator")
    profile = SIMULATORS.get(simulator)
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
    # The cocotb sim subprocess loads the test module from ``test_dir`` and must
    # also import the ``flow`` package (via ``project_dir``); expose both.
    pythonpath = os.pathsep.join(
        filter(None, [str(project_dir), str(test_dir), os.environ.get("PYTHONPATH", "")])
    )
    selected_test = os.environ.get("TEST") or None
    test_filter = os.environ.get("TEST_FILTER") or None
    rebuild = env_flag("REBUILD", default=True)
    abv = env_flag("ABV", default=False)
    no_covergroups = env_flag(
        "NO_COVERGROUPS", default=profile.no_covergroups if profile else False
    )
    hdl_coverage = env_flag("HDL_COVERAGE", default=False)
    questa_gui = env_flag("QUESTA_GUI", default=False)
    waves_enabled = env_flag("WAVES", default=True)
    default_coverage = (
        profile.coverage_data_path(build_dir) if profile else build_dir / "coverage.dat"
    )
    coverage_dat = project_path_from_env("COVERAGE_DAT", project_dir, default_coverage)
    sv_sources, sv_include_dirs = project_paths_from_list_file(
        "SV_SOURCES_FILE",
        project_dir,
        project_dir / "rtl" / "sources.vf",
    )
    if selected_test and test_filter:
        raise ValueError("Set either TEST or TEST_FILTER, not both.")
    if selected_test:
        test_filter = rf"(^|.*\.){re.escape(selected_test)}$"
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
