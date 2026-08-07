"""Command-line dispatcher the Makefile calls (``python -m flow.cli``).

Runs the cocotb regression (via pytest) and then drives the per-simulator
coverage reports and per-viewer waveform tooling defined in
:mod:`flow.simulators` and :mod:`flow.viewers`.
"""

import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from flow.runner import (
    ALL_DUTS,
    DEFAULT_DUT,
    DEFAULT_SIM,
    DEFAULT_SOURCES_FILE,
    EXECUTED_CASES_FILE_ENV,
    artifact_build_mode,
    default_build_dir,
    default_coverage_dat,
    discover_configs,
    discover_duts,
    env_flag,
    make_target_command,
)
from flow.simulators import SIMULATORS, SimulatorProfile
from flow.viewers import DEFAULT_VIEWERS, VIEWERS, ViewerProfile

PROJECT_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = PROJECT_DIR / "tests"


def _sim(name: str) -> SimulatorProfile:
    try:
        return SIMULATORS[name]
    except KeyError:
        available = ", ".join(sorted(SIMULATORS))
        raise SystemExit(f"Unknown SIM '{name}'. Available: {available}") from None


def _viewer(name: str) -> ViewerProfile:
    try:
        return VIEWERS[name]
    except KeyError:
        available = ", ".join(sorted(VIEWERS))
        raise SystemExit(f"Unknown VIEWER '{name}'. Available: {available}") from None


def _resolve_wave_selection(simulator: str, viewer_name: str | None) -> tuple[str, ViewerProfile]:
    _sim(simulator)
    if viewer_name:
        viewer = _viewer(viewer_name)
        if simulator != viewer.wave_sim:
            raise SystemExit(
                f"VIEWER={viewer.name} requires SIM={viewer.wave_sim}, got SIM={simulator}."
            )
        return simulator, viewer
    try:
        default_viewer = DEFAULT_VIEWERS[simulator]
    except KeyError:
        supported = ", ".join(sorted(DEFAULT_VIEWERS))
        raise SystemExit(
            f"SIM={simulator} has no default waveform viewer. Available: {supported}."
        ) from None
    return simulator, _viewer(default_viewer)


def _configs(dut: str) -> dict[str, dict[str, object]]:
    return discover_configs(PROJECT_DIR, dut)


def _expected_cases(dut: str) -> set[tuple[str, str | None]]:
    """Return the configured or single unconfigured cases expected for *dut*."""
    duts = discover_duts(TESTS_DIR) if dut == ALL_DUTS else [dut]
    cases: set[tuple[str, str | None]] = set()
    for case_dut in duts:
        configs = _configs(case_dut)
        if configs:
            cases.update((case_dut, config) for config in configs)
        else:
            cases.add((case_dut, None))
    return cases


def _read_executed_cases(path: Path) -> set[tuple[str, str | None]]:
    """Read DUT/configuration pairs recorded by successful ``build_and_test`` calls."""
    if not path.is_file():
        return set()
    cases: set[tuple[str, str | None]] = set()
    for line in path.read_text().splitlines():
        case_dut, separator, config = line.partition("\t")
        if not separator or not case_dut:
            raise SystemExit(f"Invalid cocotb execution record: {line!r}")
        cases.add((case_dut, config or None))
    return cases


def _format_case(case: tuple[str, str | None]) -> str:
    dut, config = case
    return f"{dut}.{config}" if config else dut


def _system_exit_status(error: SystemExit) -> int:
    """Return a shell status for a caught ``SystemExit``."""
    return error.code if isinstance(error.code, int) else 1


def _require_dut(dut: str, *, allow_all: bool = False) -> None:
    duts = discover_duts(TESTS_DIR)
    if (allow_all and dut == ALL_DUTS) or dut in duts:
        return
    available = ", ".join(duts) or "(none)"
    raise SystemExit(f"Unknown DUT '{dut}'. Available: {available}")


def _resolve_config(dut: str, requested: str | None, *, require_for_multiple: bool) -> str | None:
    configs = _configs(dut)
    if requested:
        if requested not in configs:
            available = ", ".join(configs) or "(none)"
            raise SystemExit(
                f"Unknown CONFIG '{requested}' for DUT '{dut}'. Available: {available}"
            )
        return requested
    if len(configs) == 1:
        return next(iter(configs))
    if require_for_multiple and len(configs) > 1:
        available = ", ".join(configs)
        raise SystemExit(
            f"DUT '{dut}' has multiple configurations; set CONFIG to one of: {available}"
        )
    return None


def _build_dir(
    dut: str,
    simulator: str,
    config: str | None = None,
    artifact: str = "normal",
) -> Path:
    return default_build_dir(PROJECT_DIR, dut, simulator, config, artifact)


def _coverage_data(profile: SimulatorProfile, build_dir: Path) -> Path:
    return default_coverage_dat(build_dir, profile)


def _require_coverage(
    profile: SimulatorProfile,
    dut: str,
    config: str | None,
    *,
    waves: bool,
) -> None:
    """Exit with a recovery command when a simulator lacks coverage support."""
    if profile.supports_coverage:
        return
    supported = ", ".join(sorted(name for name, p in SIMULATORS.items() if p.supports_coverage))
    fallback = next(iter(sorted(name for name, p in SIMULATORS.items() if p.supports_coverage)))
    recovery = make_target_command(
        "coverage",
        simulator=fallback,
        dut=dut,
        config=config,
        waves=waves,
    )
    raise SystemExit(
        f"Coverage is not supported for SIM={profile.name}. "
        f"Use one of: {supported} (e.g. '{recovery}')."
    )


def run_regression(
    simulator: str,
    *,
    dut: str,
    sources_file: str,
    config: str | None,
) -> None:
    """Run the cocotb regression for *simulator* via pytest.

    *simulator*, *dut*, and *sources_file* are forwarded to the pytest subprocess
    as the ``SIM``/``DUT``/``SV_SOURCES_FILE`` environment variables (the channel
    into ``build_and_test``); ``ABV``/``TEST``/``REBUILD``/... are inherited from
    the environment (the Makefile exports command-line ``VAR=value`` overrides).
    """
    _sim(simulator)
    env = os.environ.copy()
    env["SIM"] = simulator
    env["DUT"] = dut
    env["SV_SOURCES_FILE"] = sources_file
    if config:
        env["CONFIG"] = config
    else:
        env.pop("CONFIG", None)
    env.pop(EXECUTED_CASES_FILE_ENV, None)
    if not env.get("NO_COLOR"):
        env.setdefault("PY_COLORS", "1")
        env.setdefault("COCOTB_ANSI_OUTPUT", "1")
    cmd = [sys.executable, "-m", "pytest", "-s"]
    print("+ " + shlex.join(cmd), flush=True)
    with tempfile.TemporaryDirectory(prefix="cocotb_cases_") as temp_dir:
        executed_cases_file = Path(temp_dir) / "executed"
        env[EXECUTED_CASES_FILE_ENV] = str(executed_cases_file)
        result = subprocess.run(cmd, cwd=PROJECT_DIR, env=env, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        expected = {(dut, config)} if config else _expected_cases(dut)
        missing = expected - _read_executed_cases(executed_cases_file)
        if missing:
            missing_names = ", ".join(_format_case(case) for case in sorted(missing))
            raise SystemExit(
                "No matching build_and_test variant was executed for: "
                f"{missing_names}. Ensure each pytest harness parameterizes every "
                "configuration in HDL_CONFIGS."
            )


def cmd_test(args: argparse.Namespace) -> None:
    _require_dut(args.dut, allow_all=True)
    if args.dut == ALL_DUTS and args.config:
        raise SystemExit("CONFIG cannot be combined with DUT=all")
    config = (
        _resolve_config(args.dut, args.config, require_for_multiple=False)
        if args.dut != ALL_DUTS and args.config
        else args.config
    )
    run_regression(
        args.sim,
        dut=args.dut,
        sources_file=args.sources_file,
        config=config,
    )


def cmd_report_coverage(args: argparse.Namespace) -> None:
    _require_dut(args.dut)
    profile = _sim(args.sim)
    config = _resolve_config(args.dut, args.config, require_for_multiple=True)
    waves = env_flag("WAVES", default=False)
    _require_coverage(profile, args.dut, config, waves=waves)
    artifact = artifact_build_mode(
        waves=waves,
        hdl_coverage=True,
    )
    build_dir = _build_dir(args.dut, args.sim, config, artifact)
    profile.report_coverage(
        PROJECT_DIR,
        build_dir,
        _coverage_data(profile, build_dir),
        dut=args.dut,
        config=config,
    )


def cmd_report_coverage_all(args: argparse.Namespace) -> None:
    """Generate reports for every expected DUT/configuration coverage artifact."""
    profile = _sim(args.sim)
    cases = _expected_cases(ALL_DUTS)
    if not cases:
        raise SystemExit("No DUTs were discovered for coverage reporting.")
    first_dut, first_config = min(cases, key=_format_case)
    waves = env_flag("WAVES", default=False)
    _require_coverage(profile, first_dut, first_config, waves=waves)
    artifact = artifact_build_mode(waves=waves, hdl_coverage=True)
    report_status = 0
    for dut, config in sorted(cases, key=_format_case):
        build_dir = _build_dir(dut, args.sim, config, artifact)
        try:
            profile.report_coverage(
                PROJECT_DIR,
                build_dir,
                _coverage_data(profile, build_dir),
                dut=dut,
                config=config,
            )
        except SystemExit as error:
            print(
                f"Coverage report failed for {_format_case((dut, config))}: {error}",
                file=sys.stderr,
            )
            report_status = report_status or _system_exit_status(error)
    if report_status:
        raise SystemExit(report_status)


def cmd_open_coverage(args: argparse.Namespace) -> None:
    _require_dut(args.dut)
    profile = _sim(args.sim)
    config = _resolve_config(args.dut, args.config, require_for_multiple=True)
    waves = env_flag("WAVES", default=False)
    _require_coverage(profile, args.dut, config, waves=waves)
    artifact = artifact_build_mode(
        waves=waves,
        hdl_coverage=True,
    )
    build_dir = _build_dir(args.dut, args.sim, config, artifact)
    profile.open_coverage(
        PROJECT_DIR,
        build_dir,
        _coverage_data(profile, build_dir),
        dut=args.dut,
        config=config,
    )


def cmd_open_coverage_html(args: argparse.Namespace) -> None:
    _require_dut(args.dut)
    profile = _sim(args.sim)
    config = _resolve_config(args.dut, args.config, require_for_multiple=True)
    waves = env_flag("WAVES", default=False)
    _require_coverage(profile, args.dut, config, waves=waves)
    artifact = artifact_build_mode(
        waves=waves,
        hdl_coverage=True,
    )
    profile.open_coverage_html(
        PROJECT_DIR,
        _build_dir(args.dut, args.sim, config, artifact),
        dut=args.dut,
        config=config,
    )


def cmd_open_waves(args: argparse.Namespace) -> None:
    _require_dut(args.dut)
    simulator, viewer = _resolve_wave_selection(args.sim, args.viewer)
    config = _resolve_config(args.dut, args.config, require_for_multiple=True)
    artifact = artifact_build_mode(
        waves=True,
        hdl_coverage=env_flag("HDL_COVERAGE", default=False),
    )
    viewer.open_waves(
        PROJECT_DIR,
        _build_dir(args.dut, simulator, config, artifact),
        args.dut,
        config,
    )


def cmd_list_sims(args: argparse.Namespace) -> None:
    print("\n".join(sorted(SIMULATORS)))


def cmd_list_viewers(args: argparse.Namespace) -> None:
    print("\n".join(sorted(VIEWERS)))


def cmd_list_duts(args: argparse.Namespace) -> None:
    print("\n".join(discover_duts(TESTS_DIR)))


def cmd_list_configs(args: argparse.Namespace) -> None:
    _require_dut(args.dut)
    print("\n".join(_configs(args.dut)))


def cmd_validate_config(args: argparse.Namespace) -> None:
    _require_dut(args.dut)
    _resolve_config(args.dut, args.config, require_for_multiple=args.artifact)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="flow", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    test_parser = sub.add_parser("test")
    test_parser.add_argument("--sim", default=DEFAULT_SIM)
    test_parser.add_argument("--dut", default=DEFAULT_DUT)
    test_parser.add_argument("--sources-file", default=DEFAULT_SOURCES_FILE)
    test_parser.add_argument("--config")
    test_parser.set_defaults(func=cmd_test)

    for name, func in (
        ("report-coverage", cmd_report_coverage),
        ("open-coverage", cmd_open_coverage),
        ("open-coverage-html", cmd_open_coverage_html),
    ):
        p = sub.add_parser(name)
        p.add_argument("--sim", default=DEFAULT_SIM)
        p.add_argument("--dut", default=DEFAULT_DUT)
        p.add_argument("--config")
        p.set_defaults(func=func)

    report_coverage_all_parser = sub.add_parser("report-coverage-all")
    report_coverage_all_parser.add_argument("--sim", default=DEFAULT_SIM)
    report_coverage_all_parser.set_defaults(func=cmd_report_coverage_all)

    open_waves_parser = sub.add_parser("open-waves")
    open_waves_parser.add_argument("--sim", default=DEFAULT_SIM)
    open_waves_parser.add_argument("--viewer")
    open_waves_parser.add_argument("--dut", default=DEFAULT_DUT)
    open_waves_parser.add_argument("--config")
    open_waves_parser.set_defaults(func=cmd_open_waves)

    list_configs_parser = sub.add_parser("list-configs")
    list_configs_parser.add_argument("--dut", default=DEFAULT_DUT)
    list_configs_parser.set_defaults(func=cmd_list_configs)

    validate_config_parser = sub.add_parser("validate-config")
    validate_config_parser.add_argument("--dut", default=DEFAULT_DUT)
    validate_config_parser.add_argument("--config")
    validate_config_parser.add_argument("--artifact", action="store_true")
    validate_config_parser.set_defaults(func=cmd_validate_config)

    sub.add_parser("list-sims").set_defaults(func=cmd_list_sims)
    sub.add_parser("list-viewers").set_defaults(func=cmd_list_viewers)
    sub.add_parser("list-duts").set_defaults(func=cmd_list_duts)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
