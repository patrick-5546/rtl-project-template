import os
import re
import shlex
from pathlib import Path

from cocotb_tools.runner import get_runner


def env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def project_path_from_env(name: str, project_dir: Path, default: Path) -> Path:
    value = os.environ.get(name)
    path = Path(value) if value else default
    return path if path.is_absolute() else project_dir / path


def project_paths_from_list_file(name: str, project_dir: Path, default: Path) -> list[Path]:
    list_file = project_path_from_env(name, project_dir, default)
    paths: list[Path] = []
    for line in list_file.read_text().splitlines():
        entry = line.split("#", maxsplit=1)[0].strip()
        if not entry:
            continue
        path = Path(entry)
        paths.append(path if path.is_absolute() else project_dir / path)
    return paths


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
    pythonpath = os.pathsep.join(filter(None, [str(test_dir), os.environ.get("PYTHONPATH", "")]))
    selected_test = os.environ.get("TEST") or None
    test_filter = os.environ.get("TEST_FILTER") or None
    rebuild = env_flag("REBUILD", default=True)
    abv = env_flag("ABV", default=False)
    hdl_coverage = env_flag("HDL_COVERAGE", default=False)
    questa_gui = env_flag("QUESTA_GUI", default=False)
    coverage_dat = project_path_from_env(
        "COVERAGE_DAT",
        project_dir,
        build_dir / "coverage.dat",
    )
    sv_sources = project_paths_from_list_file(
        "SV_SOURCES_FILE",
        project_dir,
        project_dir / "rtl" / "sources.vf",
    )
    abv_sources = project_paths_from_list_file(
        "ABV_SOURCES_FILE",
        project_dir,
        project_dir / "rtl" / "abv_sources.vf",
    )
    if selected_test and test_filter:
        raise ValueError("Set either TEST or TEST_FILTER, not both.")
    if selected_test:
        test_filter = rf"(^|.*\.){re.escape(selected_test)}$"
    if hdl_coverage and simulator not in ("verilator", "questa"):
        raise ValueError("HDL_COVERAGE=1 is supported for the Verilator and Questa flows.")
    if questa_gui and simulator != "questa":
        raise ValueError("QUESTA_GUI=1 is supported for the Questa flow.")

    sources = [*sv_sources]
    defines: dict[str, object] = {}
    if abv:
        sources.extend(abv_sources)
        defines["ABV"] = 1

    build_args: list[str] = []
    plusargs: list[str] = []
    pre_cmd: list[str] | None = None
    test_args: list[str] = []
    if hdl_coverage:
        coverage_dat.parent.mkdir(parents=True, exist_ok=True)
        if simulator == "verilator":
            build_args.append("--coverage")
            plusargs.append(f"+verilator+coverage+file+{coverage_dat}")
        elif simulator == "questa":
            build_args.extend(["-cover", "bcesfx"])
    if simulator == "questa":
        questa_wave.parent.mkdir(parents=True, exist_ok=True)
        test_args = [
            *shlex.split(os.environ.get("QUESTA_ARGS", "")),
            "-wlf",
            str(questa_wave),
            "-nowlfdeleteonquit",
        ]
        if hdl_coverage:
            test_args.append("-coverage")
        if questa_gui:
            gui_commands = ["log -recursive /*", "run -all"]
            if hdl_coverage:
                gui_commands.insert(0, f"coverage save -onexit {coverage_dat}")
            if questa_do.is_file():
                gui_commands.append(f"source {{{questa_do.as_posix()}}}")
            pre_cmd = ["; ".join(gui_commands)]
        elif hdl_coverage:
            pre_cmd = [f"coverage save -onexit {coverage_dat}"]

    runner = get_runner(simulator)
    runner.build(
        sources=sources,
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
