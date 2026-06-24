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
from pathlib import Path

from flow.runner import (
    ALL_DUTS,
    DEFAULT_DUT,
    DEFAULT_SIM,
    DEFAULT_SOURCES_FILE,
    DEFAULT_VIEWER,
    default_build_dir,
    default_coverage_dat,
    discover_duts,
    resolve_sources_files,
)
from flow.simulators import SIMULATORS, SimulatorProfile
from flow.viewers import VIEWERS, ViewerProfile

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


def _build_dir(dut: str, simulator: str) -> Path:
    return default_build_dir(PROJECT_DIR, dut, simulator)


def _coverage_data(profile: SimulatorProfile, build_dir: Path) -> Path:
    return default_coverage_dat(PROJECT_DIR, build_dir, profile)


def _sources_files(args: argparse.Namespace) -> list[Path]:
    """Resolve the ``--sources-file`` flag (whitespace-separated) against the root."""
    return resolve_sources_files(args.sources_file, PROJECT_DIR)


def run_regression(
    simulator: str,
    *,
    dut: str,
    sources_file: str,
    extra_env: dict[str, str] | None = None,
) -> None:
    """Run the cocotb regression for *simulator* via pytest.

    *simulator*, *dut*, and *sources_file* are forwarded to the pytest subprocess
    as the ``SIM``/``DUT``/``SV_SOURCES_FILE`` environment variables (the channel
    into ``build_and_test``); ``ABV``/``TEST``/``REBUILD``/... are inherited from
    the environment (the Makefile exports command-line ``VAR=value`` overrides).
    *extra_env* layers on the values this command forces (e.g. ``QUESTA_GUI=1``
    for the live-GUI wave flow).
    """
    profile = _sim(simulator)
    env = os.environ.copy()
    env["SIM"] = simulator
    env["DUT"] = dut
    env["SV_SOURCES_FILE"] = sources_file
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, "-m", "pytest", "-s", *profile.pytest_args()]
    print("+ " + shlex.join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_DIR, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def cmd_test(args: argparse.Namespace) -> None:
    duts = discover_duts(TESTS_DIR)
    if args.dut != ALL_DUTS and args.dut not in duts:
        available = ", ".join(duts) or "(none)"
        raise SystemExit(f"Unknown DUT '{args.dut}'. Available: {available}")
    run_regression(args.sim, dut=args.dut, sources_file=args.sources_file)


def cmd_report_coverage(args: argparse.Namespace) -> None:
    profile = _sim(args.sim)
    build_dir = _build_dir(args.dut, args.sim)
    profile.report_coverage(PROJECT_DIR, build_dir, _coverage_data(profile, build_dir))


def cmd_open_coverage(args: argparse.Namespace) -> None:
    profile = _sim(args.sim)
    build_dir = _build_dir(args.dut, args.sim)
    profile.open_coverage(PROJECT_DIR, build_dir, _coverage_data(profile, build_dir))


def cmd_open_coverage_html(args: argparse.Namespace) -> None:
    profile = _sim(args.sim)
    profile.open_coverage_html(PROJECT_DIR, _build_dir(args.dut, args.sim))


def cmd_waves(args: argparse.Namespace) -> None:
    viewer = _viewer(args.viewer)
    build_dir = _build_dir(args.dut, viewer.wave_sim)
    sources_files = _sources_files(args)
    if viewer.live_gui:
        # The interactive run *is* the wave view (e.g. Questa's GUI).
        run_regression(
            viewer.wave_sim,
            dut=args.dut,
            sources_file=args.sources_file,
            extra_env={"QUESTA_GUI": "1", **viewer.waves_run_env(PROJECT_DIR)},
        )
    else:
        run_regression(viewer.wave_sim, dut=args.dut, sources_file=args.sources_file)
        viewer.open_waves(PROJECT_DIR, build_dir, args.dut, sources_files)


def cmd_open_waves(args: argparse.Namespace) -> None:
    viewer = _viewer(args.viewer)
    viewer.open_waves(
        PROJECT_DIR, _build_dir(args.dut, viewer.wave_sim), args.dut, _sources_files(args)
    )


def cmd_list_sims(args: argparse.Namespace) -> None:
    print("\n".join(sorted(SIMULATORS)))


def cmd_list_viewers(args: argparse.Namespace) -> None:
    print("\n".join(sorted(VIEWERS)))


def cmd_list_duts(args: argparse.Namespace) -> None:
    print("\n".join(discover_duts(TESTS_DIR)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="flow", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    test_parser = sub.add_parser("test")
    test_parser.add_argument("--sim", default=DEFAULT_SIM)
    test_parser.add_argument("--dut", default=DEFAULT_DUT)
    test_parser.add_argument("--sources-file", default=DEFAULT_SOURCES_FILE)
    test_parser.set_defaults(func=cmd_test)

    for name, func in (
        ("report-coverage", cmd_report_coverage),
        ("open-coverage", cmd_open_coverage),
        ("open-coverage-html", cmd_open_coverage_html),
    ):
        p = sub.add_parser(name)
        p.add_argument("--sim", default=DEFAULT_SIM)
        p.add_argument("--dut", default=DEFAULT_DUT)
        p.set_defaults(func=func)

    for name, func in (("waves", cmd_waves), ("open-waves", cmd_open_waves)):
        p = sub.add_parser(name)
        p.add_argument("--viewer", default=DEFAULT_VIEWER)
        p.add_argument("--dut", default=DEFAULT_DUT)
        p.add_argument("--sources-file", default=DEFAULT_SOURCES_FILE)
        p.set_defaults(func=func)

    sub.add_parser("list-sims").set_defaults(func=cmd_list_sims)
    sub.add_parser("list-viewers").set_defaults(func=cmd_list_viewers)
    sub.add_parser("list-duts").set_defaults(func=cmd_list_duts)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
