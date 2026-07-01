import logging
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from cocotb_tools.runner import get_runner

if TYPE_CHECKING:
    from flow.simulators import SimulatorProfile

# Default tool/DUT selections and SV filelist. Each is duplicated only by the
# matching Makefile selector (``SIM``/``VIEWER``/``DUT``/``SV_SOURCES_FILE``):
# these copies are the single source the CLI argparse defaults and the runner
# share, and the fallback used when the flow runs without the Makefile (e.g. a
# bare ``uv run pytest``). ``SV_SOURCES_FILE`` may name several filelists
# separated by whitespace (each handed to the simulator with its own ``-f``);
# ``DEFAULT_SOURCES_FILE`` is the single fallback when it is unset.
DEFAULT_SIM = "verilator"
DEFAULT_VIEWER = "gtkwave"
DEFAULT_DUT = "top"
DEFAULT_SOURCES_FILE = "rtl/sources.vf"

# Sentinel ``DUT`` value meaning "every DUT": ``make test-all`` passes it so each
# collected ``tests/test_*.py`` builds and runs its own module instead of being
# filtered to a single one. ``make test`` and the single-target commands use a
# concrete module (defaulting to ``DEFAULT_DUT``) instead.
ALL_DUTS = "all"


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
    sources_files: list[Path]


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


class _CommandEchoFormatter(logging.Formatter):
    """Render cocotb runner command logs in the project's ``+ <cmd>`` style.

    cocotb's runner logs every subprocess it launches as
    ``"Running command %s in directory %s"`` (the command is the first log
    argument); reformat those to match the ``+ <cmd>`` echoes :func:`run`
    already prints for the coverage/waveform tools. Any other record (e.g.
    ``"Removing: ..."``) is passed through unchanged, so a future cocotb wording
    change still prints the command rather than hiding it.
    """

    def format(self, record: logging.LogRecord) -> str:
        if (
            record.msg == "Running command %s in directory %s"
            and isinstance(record.args, tuple)
            and record.args
        ):
            return f"+ {record.args[0]}"
        return record.getMessage()


def echo_runner_commands(runner_log: logging.Logger) -> None:
    """Make cocotb's actual build/sim subprocess commands print to stdout.

    cocotb logs each command it runs (verilator, make, the simulator
    executable, vsim, vcs/simv) at ``INFO``, but with no INFO handler configured
    those records are dropped by Python's default WARNING-only "last resort"
    handler (and pytest's log capture hides them too). Attach a stdout handler
    so every shell command is visible, matching the ``+ <cmd>`` echoes used for
    the coverage and waveform tools. ``propagate`` is disabled so the records
    bypass pytest's capture and are not printed twice.

    Idempotent: cocotb's per-simulator loggers are process-global singletons and
    :func:`build_and_test` runs once per test file, so only one handler is ever
    attached.
    """
    marker = "_flow_command_echo"
    if any(getattr(handler, marker, False) for handler in runner_log.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, marker, True)
    handler.setFormatter(_CommandEchoFormatter())
    runner_log.addHandler(handler)
    runner_log.propagate = False


def require(path: Path, hint: str, *, kind: str = "file") -> None:
    """Exit with a helpful message when *path* (a file or directory) is missing."""
    ok = path.is_dir() if kind == "dir" else path.is_file()
    if not ok:
        raise SystemExit(f"{path} not found. {hint}")


def open_html(index: Path, *, hint: str) -> None:
    """Open an HTML report *index* with ``$HTML_VIEWER`` (default xdg-open)."""
    require(index, hint)
    run([env_str("HTML_VIEWER", "xdg-open"), str(index)])


def resolve_project_path(value: str | None, project_dir: Path, default: Path) -> Path:
    """Resolve *value* (or *default* when empty) against *project_dir*.

    A relative path is taken relative to *project_dir* (the repo root); an
    absolute path is used unchanged. Shared by the ``$VAR`` environment lookups
    (:func:`project_path_from_env`) and the flow CLI's path flags (e.g.
    ``--sources-file``).
    """
    path = Path(value) if value else default
    return path if path.is_absolute() else project_dir / path


def project_path_from_env(name: str, project_dir: Path, default: Path) -> Path:
    return resolve_project_path(os.environ.get(name), project_dir, default)


def resolve_sources_files(value: str | None, project_dir: Path) -> list[Path]:
    """Resolve a whitespace-separated *value* of filelists against *project_dir*.

    ``SV_SOURCES_FILE`` (and the flow CLI's ``--sources-file``) may name several
    SystemVerilog filelists separated by whitespace; each entry is resolved like
    :func:`resolve_project_path` (relative paths against the repo root, absolute
    paths unchanged), and every list is handed to the simulator with its own
    ``-f``. An empty/unset *value* falls back to the single
    :data:`DEFAULT_SOURCES_FILE`. Individual paths therefore cannot contain
    spaces, matching the absolute-path convention of ``rtl/sources.vf``.
    """
    default = project_dir / DEFAULT_SOURCES_FILE
    tokens = value.split() if value else []
    if not tokens:
        return [default]
    return [resolve_project_path(token, project_dir, default) for token in tokens]


def dut_from_test_module(test_module: str) -> str:
    """The DUT module a test file targets, by filename convention.

    ``tests/test_<module>__<variant>.py`` (and plain ``test_<module>.py``) target
    ``<module>``: the stem between the ``test_`` prefix and the first ``__``
    variant separator (or the end). RTL module names use single underscores, so
    splitting on ``__`` keeps the module unambiguous even for names like
    ``ede_lz_data_assembler``.
    """
    return test_module.removeprefix("test_").split("__", 1)[0]


def discover_duts(tests_dir: Path) -> list[str]:
    """Sorted, de-duplicated DUT modules discovered from ``tests/test_*.py``.

    Each ``test_*.py`` maps to its module via :func:`dut_from_test_module`;
    several files (e.g. ``test_top.py`` and ``test_top__smoke.py``) may share one
    module. Used for the ``DUT`` validation in the flow CLI, the ``list-duts``
    command, and the ``coverage-all`` loop.
    """
    modules = {dut_from_test_module(path.stem) for path in tests_dir.glob("test_*.py")}
    return sorted(modules)


def default_build_dir(project_dir: Path, dut: str, simulator: str) -> Path:
    """``$BUILD_DIR`` override, or the per-DUT, per-simulator ``build/<dut>/<sim>`` default."""
    return project_path_from_env("BUILD_DIR", project_dir, project_dir / "build" / dut / simulator)


def default_coverage_dat(
    project_dir: Path, build_dir: Path, profile: "SimulatorProfile | None"
) -> Path:
    """``$COVERAGE_DAT`` override, or the profile's coverage artifact under *build_dir*."""
    base = profile.coverage_data_path(build_dir) if profile else build_dir / "coverage.dat"
    return project_path_from_env("COVERAGE_DAT", project_dir, base)


def default_sources_files(project_dir: Path) -> list[Path]:
    """``$SV_SOURCES_FILE`` overrides (whitespace-separated), or ``rtl/sources.vf``.

    The flow CLI sets ``SV_SOURCES_FILE`` in the regression subprocess from its
    ``--sources-file`` flag (the channel the Makefile passes ``SV_SOURCES_FILE``
    through), so this resolves the same list(s) the SV lint/format targets parse.
    Several filelists may be given, separated by whitespace; each is handed to
    the simulator with its own ``-f``.
    """
    return resolve_sources_files(os.environ.get("SV_SOURCES_FILE"), project_dir)


def default_verilator_wave(project_dir: Path, build_dir: Path) -> Path:
    """``$WAVE`` override, or the Verilator ``dump.vcd`` under *build_dir*."""
    return project_path_from_env("WAVE", project_dir, build_dir / "dump.vcd")


def default_vcs_wave(project_dir: Path, build_dir: Path) -> Path:
    """``$VCS_WAVE`` override, or the VCS ``dump.fsdb`` under *build_dir*."""
    return project_path_from_env("VCS_WAVE", project_dir, build_dir / "dump.fsdb")


def default_questa_wave(project_dir: Path, build_dir: Path) -> Path:
    """``$QUESTA_WAVE`` override, or the Questa ``vsim.wlf`` under *build_dir*."""
    return project_path_from_env("QUESTA_WAVE", project_dir, build_dir / "vsim.wlf")


def default_questa_do(project_dir: Path, dut: str) -> Path:
    """``$QUESTA_DO`` override, or the ``waves/<dut>.do`` layout for *dut*."""
    return project_path_from_env("QUESTA_DO", project_dir, project_dir / "waves" / f"{dut}.do")


def vsim_exe() -> str:
    """The ``vsim`` executable, overridable via ``$VSIM``."""
    return env_str("VSIM", "vsim")


def verdi_command() -> list[str]:
    """``verdi`` plus ``$VERDI_ARGS`` (default ``-nologo``) as a command prefix."""
    return [env_str("VERDI", "verdi"), *shlex.split(env_str("VERDI_ARGS", "-nologo"))]


def build_and_test(test_module: str | list[str]) -> None:
    """Build RTL and run the cocotb tests in *test_module* for its DUT.

    *test_module* is a single module name or a list of them. A list is built
    once and run together in one simulator process, so every test shares one
    build and lands in a single end-of-test summary (and one waveform) -- this
    is how a ``test_<module>`` aggregator can run its
    ``test_<module>__<variant>`` modules together.

    The DUT is derived from *test_module* (the first entry, for a list) by
    filename convention (:func:`dut_from_test_module`):
    ``test_<module>__<variant>`` -> ``<module>``.
    The ``DUT`` environment variable (set by the flow CLI from
    ``make ... DUT=<module>``) is a *selector*, not an override: when it names a
    concrete module other than this file's, the test self-skips, so one pytest
    run can hold test files for several DUTs (``make test-all`` passes
    ``DUT=all`` to run them all). The derived module drives the build dir, the
    GTKWave stems, and the ``waves/<DUT>.*`` layouts.

    All other configuration (SIM, BUILD_DIR, TEST, ABV, HDL_COVERAGE,
    QUESTA_GUI, etc.) is read from environment variables, matching the
    Makefile-driven workflow. Per-simulator defaults (covergroup support,
    coverage-artifact path, build/test arguments) come from the matching
    profile in :mod:`flow.simulators`.
    """
    first_module = test_module if isinstance(test_module, str) else test_module[0]
    hdl_toplevel = dut_from_test_module(first_module)
    selector = env_str("DUT", ALL_DUTS)
    if selector != ALL_DUTS and selector != hdl_toplevel:
        import pytest

        pytest.skip(f"DUT={selector!r} selected; this file targets {hdl_toplevel!r}")

    # Lazy import: ``flow.simulators`` imports this module, so importing it at
    # module scope would be circular.
    from flow.simulators import SIMULATORS

    project_dir = Path(__file__).resolve().parents[1]
    test_dir = project_dir / "tests"
    simulator = env_str("SIM", DEFAULT_SIM)
    profile = SIMULATORS.get(simulator)
    build_dir = default_build_dir(project_dir, hdl_toplevel, simulator)
    questa_wave = default_questa_wave(project_dir, build_dir)
    questa_do = default_questa_do(project_dir, hdl_toplevel)
    vcs_wave = default_vcs_wave(project_dir, build_dir)
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
    coverage_dat = default_coverage_dat(project_dir, build_dir, profile)
    sources_files = default_sources_files(project_dir)
    for sources_file in sources_files:
        require(sources_file, "Set SV_SOURCES_FILE to a valid filelist (see rtl/sources.vf).")
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

    sources: list[Path] = []
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
                sources_files=sources_files,
            )
        )
        if profile
        else SimArgs(build_args=[arg for f in sources_files for arg in ("-f", str(f))])
    )
    build_args = sim_args.build_args
    plusargs = sim_args.plusargs
    test_args = sim_args.test_args
    pre_cmd = sim_args.pre_cmd
    sources.extend(sim_args.sources)

    runner = get_runner(simulator)
    echo_runner_commands(runner.log)
    runner.build(
        sources=sources,
        includes=[],
        defines=defines,
        build_args=build_args,
        hdl_toplevel=hdl_toplevel,
        build_dir=build_dir,
        always=rebuild,
        waves=True,
    )
    extra_env = {"PYTHONPATH": pythonpath}
    # vsim wraps cocotb's stdout (its transcript), so cocotb's TTY check fails
    # and it strips ANSI color that Verilator/VCS keep. On a real terminal (not
    # GUI, and only if the user hasn't pinned color via COCOTB_ANSI_OUTPUT or
    # NO_COLOR), force color so Questa output matches the other simulators.
    if (
        profile
        and profile.forces_ansi_on_tty
        and not questa_gui
        and sys.stdout.isatty()
        and "COCOTB_ANSI_OUTPUT" not in os.environ
        and not os.environ.get("NO_COLOR")
    ):
        extra_env["COCOTB_ANSI_OUTPUT"] = "1"
    runner.test(
        hdl_toplevel=hdl_toplevel,
        hdl_toplevel_lang="verilog",
        test_module=test_module,
        test_filter=test_filter,
        build_dir=build_dir,
        waves=not questa_gui,
        gui=questa_gui,
        extra_env=extra_env,
        test_args=test_args,
        plusargs=plusargs,
        pre_cmd=pre_cmd,
    )
