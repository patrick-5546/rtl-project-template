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
from collections.abc import Callable
from pathlib import Path

from flow import doctor
from flow.runner import (
    DEFAULT_SIM,
    DEFAULT_SOURCES_FILE,
    EXECUTED_CASES_FILE_ENV,
    artifact_build_mode,
    default_build_dir,
    default_coverage_dat,
    discover_duts,
    env_flag,
    hdl_configs,
    make_target_command,
)
from flow.simulators import SIMULATORS, SimulatorProfile
from flow.viewers import VIEWERS, ViewerProfile

PROJECT_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = PROJECT_DIR / "tests"
# pytest's exit status for a usage error, such as a node ID that matches no test
# (pytest.ExitCode.USAGE_ERROR; the CLI does not import pytest).
PYTEST_USAGE_ERROR = 4


def _sim(name: str) -> SimulatorProfile:
    try:
        return SIMULATORS[name]
    except KeyError:
        available = ", ".join(sorted(SIMULATORS))
        raise SystemExit(f"Unknown SIM '{name}'. Available: {available}") from None


def _viewer(simulator: str) -> ViewerProfile:
    """Return the waveform viewer for *simulator*'s waves."""
    _sim(simulator)
    try:
        return VIEWERS[simulator]
    except KeyError:
        supported = ", ".join(sorted(VIEWERS))
        raise SystemExit(
            f"SIM={simulator} has no waveform viewer. Simulators with one: {supported}."
        ) from None


def _configs(dut: str) -> dict[str, dict[str, object]]:
    return hdl_configs(PROJECT_DIR, dut)


def _read_executed_cases(path: Path) -> set[tuple[str, str]]:
    """Read DUT/configuration pairs recorded by successful ``build_and_test`` calls."""
    if not path.is_file():
        return set()
    cases: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        case_dut, separator, config = line.partition("\t")
        if not separator or not case_dut or not config:
            raise SystemExit(f"Invalid cocotb execution record: {line!r}")
        cases.add((case_dut, config))
    return cases


def _format_case(case: tuple[str, str]) -> str:
    dut, config = case
    return f"{dut}.{config}"


def _system_exit_status(error: SystemExit) -> int:
    """Return a shell status for a caught ``SystemExit``."""
    return error.code if isinstance(error.code, int) else 1


def _duts(dut: str | None) -> list[str]:
    """*dut*, checked, or every DUT that has a harness when *dut* is unset."""
    duts = discover_duts(TESTS_DIR)
    if not duts:
        raise SystemExit("No DUTs found: add a tests/test_<module>.py harness.")
    if dut is None:
        return duts
    if dut not in duts:
        raise SystemExit(f"Unknown DUT '{dut}'. Available: {', '.join(duts)}")
    return [dut]


def _selected_cases(dut: str | None, config: str | None) -> list[tuple[str, str]]:
    """Return the DUT/configuration cases that *dut* and *config* select, sorted.

    An unset *dut* selects every DUT that has a harness, and an unset *config*
    every configuration of each selected DUT. A configuration belongs to one DUT,
    so *config* without *dut* needs a project with one DUT. Batch commands (test,
    report-coverage) run every selected case.
    """
    duts = _duts(dut)
    if config is not None and len(duts) > 1:
        raise SystemExit(f"Set DUT with CONFIG, to one of: {', '.join(duts)}")
    cases: list[tuple[str, str]] = []
    for case_dut in duts:
        configs = _configs(case_dut)
        if config is None:
            cases.extend((case_dut, name) for name in configs)
        elif config in configs:
            cases.append((case_dut, config))
        else:
            available = ", ".join(configs)
            raise SystemExit(
                f"Unknown CONFIG '{config}' for DUT '{case_dut}'. Available: {available}"
            )
    return sorted(cases)


def _single_case(dut: str | None, config: str | None) -> tuple[str, str]:
    """Return the one case that a command opening a single artifact needs.

    *dut* may be unset when the project has one DUT, and *config* when the DUT
    has one configuration.
    """
    duts = _duts(dut)
    if len(duts) > 1:
        raise SystemExit(f"Set DUT to one of: {', '.join(duts)}")
    cases = _selected_cases(duts[0], config)
    if len(cases) > 1:
        available = ", ".join(case_config for _, case_config in cases)
        raise SystemExit(
            f"DUT '{duts[0]}' has multiple configurations; set CONFIG to one of: {available}"
        )
    return cases[0]


def _build_dir(dut: str, simulator: str, config: str, artifact: str = "normal") -> Path:
    return default_build_dir(PROJECT_DIR, dut, simulator, config, artifact)


def _coverage_data(profile: SimulatorProfile, build_dir: Path) -> Path:
    return default_coverage_dat(build_dir, profile)


def _artifact_dir(
    simulator: str,
    dut: str,
    config: str,
    *,
    instrumentation: str,
    artifact: Callable[[Path], Path],
) -> Path:
    """Return the build directory that holds one case's waveform or coverage data.

    *instrumentation* is ``"waves"`` or ``"coverage"``. A waveform exists in the
    ``waves`` and ``waves-coverage`` builds, and coverage data in ``coverage`` and
    ``waves-coverage``. The other instrumentation's flag (``HDL_COVERAGE`` for a
    waveform, ``WAVES`` for coverage) selects one of the two; unset, the build
    whose *artifact* is newer is used, and named. With neither artifact present,
    the build without the other instrumentation is returned, for its hint.
    """
    other_flag = "HDL_COVERAGE" if instrumentation == "waves" else "WAVES"
    pinned = env_flag(other_flag, default=False) if os.environ.get(other_flag) else None
    candidates = [
        _build_dir(
            dut,
            simulator,
            config,
            artifact_build_mode(
                waves=instrumentation == "waves" or other,
                hdl_coverage=instrumentation == "coverage" or other,
            ),
        )
        for other in ((pinned,) if pinned is not None else (False, True))
    ]
    existing = [build_dir for build_dir in candidates if artifact(build_dir).exists()]
    if pinned is not None or not existing:
        return candidates[0]
    newest = max(existing, key=lambda build_dir: artifact(build_dir).stat().st_mtime)
    print(f"Using the {instrumentation} data in {newest}", flush=True)
    return newest


def _require_coverage(
    profile: SimulatorProfile,
    dut: str,
    config: str,
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
    dut: str | None,
    sources_file: str,
    config: str | None,
) -> None:
    """Run the cocotb regression for *simulator* via pytest.

    pytest runs each case that *dut* and *config* select (:func:`_selected_cases`)
    by its harness's node ID, ``tests/test_<dut>.py::test_<dut>[<config>]``, and
    every one must reach ``build_and_test``. *simulator* and *sources_file* are
    forwarded to the pytest subprocess as the ``SIM``/``SV_SOURCES_FILE``
    environment variables (the channel into ``build_and_test``);
    ``ABV``/``TEST``/``REBUILD``/... are inherited from the environment (the
    Makefile exports command-line ``VAR=value`` overrides).
    """
    _sim(simulator)
    cases = _selected_cases(dut, config)
    env = os.environ.copy()
    env["SIM"] = simulator
    env["SV_SOURCES_FILE"] = sources_file
    env.pop(EXECUTED_CASES_FILE_ENV, None)
    if not env.get("NO_COLOR"):
        env.setdefault("PY_COLORS", "1")
        env.setdefault("COCOTB_ANSI_OUTPUT", "1")
    node_ids = [
        f"{TESTS_DIR.relative_to(PROJECT_DIR).as_posix()}/test_{case_dut}.py"
        f"::test_{case_dut}[{case_config}]"
        for case_dut, case_config in cases
    ]
    cmd = [sys.executable, "-m", "pytest", "-s", *node_ids]
    print("+ " + shlex.join(cmd), flush=True)
    with tempfile.TemporaryDirectory(prefix="cocotb_cases_") as temp_dir:
        executed_cases_file = Path(temp_dir) / "executed"
        env[EXECUTED_CASES_FILE_ENV] = str(executed_cases_file)
        result = subprocess.run(cmd, cwd=PROJECT_DIR, env=env, check=False)
        if result.returncode == PYTEST_USAGE_ERROR:
            print(
                "Each DUT needs a harness, test_<dut> in tests/test_<dut>.py, "
                "parameterized with config_params (see docs/workflows.md).",
                file=sys.stderr,
            )
        if result.returncode != 0:
            raise SystemExit(result.returncode)
        missing = set(cases) - _read_executed_cases(executed_cases_file)
        if missing:
            missing_names = ", ".join(_format_case(case) for case in sorted(missing))
            raise SystemExit(
                f"No build_and_test call ran: {missing_names}. Ensure each pytest "
                "harness parameterizes every configuration in HDL_CONFIGS."
            )


def cmd_test(args: argparse.Namespace) -> None:
    run_regression(
        args.sim,
        dut=args.dut,
        sources_file=args.sources_file,
        config=args.config,
    )


def cmd_report_coverage(args: argparse.Namespace) -> None:
    """Report coverage for every case that DUT and CONFIG select, as test runs them."""
    profile = _sim(args.sim)
    cases = _selected_cases(args.dut, args.config)
    _require_coverage(profile, *cases[0], waves=env_flag("WAVES", default=False))
    report_status = 0
    for dut, config in cases:
        build_dir = _artifact_dir(
            args.sim,
            dut,
            config,
            instrumentation="coverage",
            artifact=profile.coverage_data_path,
        )
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
    profile = _sim(args.sim)
    dut, config = _single_case(args.dut, args.config)
    _require_coverage(profile, dut, config, waves=env_flag("WAVES", default=False))
    build_dir = _artifact_dir(
        args.sim, dut, config, instrumentation="coverage", artifact=profile.coverage_data_path
    )
    profile.open_coverage(
        PROJECT_DIR,
        build_dir,
        _coverage_data(profile, build_dir),
        dut=dut,
        config=config,
    )


def cmd_open_coverage_html(args: argparse.Namespace) -> None:
    profile = _sim(args.sim)
    dut, config = _single_case(args.dut, args.config)
    _require_coverage(profile, dut, config, waves=env_flag("WAVES", default=False))
    build_dir = _artifact_dir(
        args.sim, dut, config, instrumentation="coverage", artifact=profile.coverage_data_path
    )
    profile.open_coverage_html(PROJECT_DIR, build_dir, dut=dut, config=config)


def cmd_open_waves(args: argparse.Namespace) -> None:
    viewer = _viewer(args.sim)
    dut, config = _single_case(args.dut, args.config)
    build_dir = _artifact_dir(
        args.sim, dut, config, instrumentation="waves", artifact=viewer.wave_path
    )
    viewer.open_waves(PROJECT_DIR, build_dir, dut, config)


def cmd_list_sims(args: argparse.Namespace) -> None:
    print("\n".join(sorted(SIMULATORS)))


def cmd_list_duts(args: argparse.Namespace) -> None:
    print("\n".join(discover_duts(TESTS_DIR)))


def cmd_list_configs(args: argparse.Namespace) -> None:
    cases = _selected_cases(args.dut, None)
    if args.dut is None:
        print("\n".join(_format_case(case) for case in cases))
    else:
        print("\n".join(config for _, config in cases))


def cmd_lint_cases(args: argparse.Namespace) -> None:
    """Print ``<dut> -G<name>=<value>...`` for each configuration that overrides parameters.

    The Verilator and slang lint targets lint the RTL once with its default
    parameters, then once more per line, with that DUT as the top module.
    """
    for dut in discover_duts(TESTS_DIR):
        for config, parameters in _configs(dut).items():
            overrides = [f"-G{name}={value}" for name, value in parameters.items()]
            if any(any(char.isspace() for char in override) for override in overrides):
                raise SystemExit(
                    f"Cannot lint {dut}.{config}: a parameter value contains whitespace."
                )
            if overrides:
                print(dut, *overrides)


def cmd_validate_config(args: argparse.Namespace) -> None:
    """Check that DUT and CONFIG select the one case that a waves run needs."""
    _single_case(args.dut, args.config)


def cmd_doctor(args: argparse.Namespace) -> None:
    raise SystemExit(doctor.report())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="flow", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    test_parser = sub.add_parser("test")
    test_parser.add_argument("--sim", default=DEFAULT_SIM)
    test_parser.add_argument("--dut")
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
        p.add_argument("--dut")
        p.add_argument("--config")
        p.set_defaults(func=func)

    open_waves_parser = sub.add_parser("open-waves")
    open_waves_parser.add_argument("--sim", default=DEFAULT_SIM)
    open_waves_parser.add_argument("--dut")
    open_waves_parser.add_argument("--config")
    open_waves_parser.set_defaults(func=cmd_open_waves)

    list_configs_parser = sub.add_parser("list-configs")
    list_configs_parser.add_argument("--dut")
    list_configs_parser.set_defaults(func=cmd_list_configs)

    validate_config_parser = sub.add_parser("validate-config")
    validate_config_parser.add_argument("--dut")
    validate_config_parser.add_argument("--config")
    validate_config_parser.set_defaults(func=cmd_validate_config)

    sub.add_parser("lint-cases").set_defaults(func=cmd_lint_cases)
    sub.add_parser("doctor").set_defaults(func=cmd_doctor)
    sub.add_parser("list-sims").set_defaults(func=cmd_list_sims)
    sub.add_parser("list-duts").set_defaults(func=cmd_list_duts)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
