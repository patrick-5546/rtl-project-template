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

from flow.runner import project_path_from_env
from flow.simulators import SIMULATORS, SimulatorProfile
from flow.viewers import VIEWERS, ViewerProfile

PROJECT_DIR = Path(__file__).resolve().parents[1]


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


def _build_dir(simulator: str) -> Path:
    return project_path_from_env("BUILD_DIR", PROJECT_DIR, PROJECT_DIR / "build" / simulator)


def _coverage_data(profile: SimulatorProfile, build_dir: Path) -> Path:
    return project_path_from_env("COVERAGE_DAT", PROJECT_DIR, profile.coverage_data_path(build_dir))


def run_regression(simulator: str, *, extra_env: dict[str, str] | None = None) -> None:
    """Run the cocotb regression for *simulator* via pytest.

    ``ABV``/``TEST``/``REBUILD``/... are inherited from the environment (the
    Makefile exports command-line ``VAR=value`` overrides); *extra_env* layers on
    the values this command forces (e.g. ``QUESTA_GUI=1`` for the live-GUI wave
    flow).
    """
    profile = _sim(simulator)
    env = os.environ.copy()
    env["SIM"] = simulator
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, "-m", "pytest", "-s", *profile.pytest_args()]
    print("+ " + shlex.join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=PROJECT_DIR, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def cmd_test(args: argparse.Namespace) -> None:
    run_regression(args.sim)


def cmd_report_coverage(args: argparse.Namespace) -> None:
    profile = _sim(args.sim)
    build_dir = _build_dir(args.sim)
    profile.report_coverage(PROJECT_DIR, build_dir, _coverage_data(profile, build_dir))


def cmd_open_coverage(args: argparse.Namespace) -> None:
    profile = _sim(args.sim)
    build_dir = _build_dir(args.sim)
    profile.open_coverage(PROJECT_DIR, build_dir, _coverage_data(profile, build_dir))


def cmd_open_coverage_html(args: argparse.Namespace) -> None:
    profile = _sim(args.sim)
    profile.open_coverage_html(PROJECT_DIR, _build_dir(args.sim))


def cmd_waves(args: argparse.Namespace) -> None:
    viewer = _viewer(args.viewer)
    build_dir = _build_dir(viewer.wave_sim)
    if viewer.live_gui:
        # The interactive run *is* the wave view (e.g. Questa's GUI).
        run_regression(
            viewer.wave_sim, extra_env={"QUESTA_GUI": "1", **viewer.waves_run_env(PROJECT_DIR)}
        )
    else:
        run_regression(viewer.wave_sim)
        viewer.open_waves(PROJECT_DIR, build_dir)


def cmd_open_waves(args: argparse.Namespace) -> None:
    viewer = _viewer(args.viewer)
    viewer.open_waves(PROJECT_DIR, _build_dir(viewer.wave_sim))


def cmd_list_sims(args: argparse.Namespace) -> None:
    print("\n".join(sorted(SIMULATORS)))


def cmd_list_viewers(args: argparse.Namespace) -> None:
    print("\n".join(sorted(VIEWERS)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="flow", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func in (
        ("test", cmd_test),
        ("report-coverage", cmd_report_coverage),
        ("open-coverage", cmd_open_coverage),
        ("open-coverage-html", cmd_open_coverage_html),
    ):
        p = sub.add_parser(name)
        p.add_argument("--sim", default="verilator")
        p.set_defaults(func=func)

    for name, func in (("waves", cmd_waves), ("open-waves", cmd_open_waves)):
        p = sub.add_parser(name)
        p.add_argument("--viewer", default="gtkwave")
        p.set_defaults(func=func)

    sub.add_parser("list-sims").set_defaults(func=cmd_list_sims)
    sub.add_parser("list-viewers").set_defaults(func=cmd_list_viewers)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
