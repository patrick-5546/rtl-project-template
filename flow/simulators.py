"""Per-simulator profiles describing how each simulator builds, runs, and
reports coverage.

Each profile owns:

* the cocotb runner build/test arguments (:meth:`SimulatorProfile.configure`,
  consumed by :func:`flow.runner.build_and_test`),
* per-simulator defaults (covergroup support, coverage-artifact path, whether
  the slow/interactive flows need pytest's timeout disabled),
* the coverage report/open behavior (:meth:`SimulatorProfile.report_coverage`,
  :meth:`SimulatorProfile.open_coverage`, :meth:`SimulatorProfile.open_coverage_html`).

Add a simulator by subclassing :class:`SimulatorProfile`, implementing the
capabilities it supports, and registering an instance in :data:`SIMULATORS`.
"""

import shutil
from pathlib import Path

from flow.runner import (
    RunConfig,
    SimArgs,
    env_str,
    open_html,
    require,
    run,
    verdi_command,
    vsim_exe,
)


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
        f"    $fsdbDumpSVA(0, {hdl_toplevel});\n"
        "  end\n"
        "endmodule\n"
        "// VCS coverage on\n"
    )
    # Only rewrite when content changes so the file's mtime stays stable and
    # REBUILD=0 (cocotb's ``outdated`` mtime check) keeps reusing the build.
    if not dump_module.is_file() or dump_module.read_text() != contents:
        dump_module.write_text(contents)
    return dump_module


def write_questa_anchor(build_dir: Path) -> Path:
    """Write a no-op Questa source so cocotb emits a ``vlog`` for the ``-f`` list.

    cocotb's Questa runner builds one ``vlog`` invocation per source file and
    skips compilation entirely when no sources are given. The flow hands the
    design to ``vlog`` with ``-f <filelist>`` (a build arg), so it needs at
    least one source for that command to be emitted. This anchor declares no
    design units; ``vlog`` reads the real sources from the filelist alongside
    it.

    Only rewritten when its content changes so the file's mtime stays stable and
    ``REBUILD=0`` (cocotb's ``-incr`` reuse) keeps working.
    """
    build_dir.mkdir(parents=True, exist_ok=True)
    anchor = build_dir / "cocotb_questa_anchor.sv"
    contents = "// Questa filelist anchor: no design units; see flow/simulators.py\n"
    if not anchor.is_file() or anchor.read_text() != contents:
        anchor.write_text(contents)
    return anchor


class SimulatorProfile:
    """Base class for per-simulator build/test/coverage behavior.

    Subclasses set ``name`` and the capability flags, implement
    :meth:`configure`, and (when ``supports_coverage``) the coverage methods.
    Simulators that cocotb supports but that have no profile here still run with
    default arguments.
    """

    name: str = ""
    supports_coverage: bool = False
    supports_gui: bool = False
    # Verilator parses but ignores SV covergroups, so they are excluded by
    # default there; event-based simulators keep them.
    no_covergroups: bool = False
    # Questa's GUI flow and VCS's slower build/run should not be killed by
    # pytest-timeout.
    disable_pytest_timeout: bool = False
    # Some simulators (e.g. Questa's ``vsim``) run cocotb's Python embedded
    # behind their own transcript, so cocotb's ``sys.stdout.isatty()`` color
    # check fails and it strips ANSI -- unlike Verilator/VCS, which run a native
    # executable on the real terminal. ``build_and_test`` re-enables color for
    # these on a TTY so the output matches.
    forces_ansi_on_tty: bool = False

    def configure(self, cfg: RunConfig) -> SimArgs:
        """Default build args: hand each source filelist to the tool with ``-f``.

        Every profile inherits one ``-f <filelist>`` build arg per entry in
        ``cfg.sources_files`` (``SV_SOURCES_FILE`` may list several); overrides
        call ``super().configure(cfg)`` and extend the returned :class:`SimArgs`
        with their simulator-specific build/test args.
        """
        build_args: list[str] = []
        for sources_file in cfg.sources_files:
            build_args.extend(["-f", str(sources_file)])
        return SimArgs(build_args=build_args)

    def coverage_data_path(self, build_dir: Path) -> Path:
        """Canonical coverage artifact for this simulator under *build_dir*."""
        return build_dir / "coverage.dat"

    def pytest_args(self) -> list[str]:
        return ["--timeout=0"] if self.disable_pytest_timeout else []

    def coverage_html_index(self, build_dir: Path) -> Path:
        raise NotImplementedError

    def report_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        raise NotImplementedError

    def open_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        raise NotImplementedError

    def open_coverage_html(self, project_dir: Path, build_dir: Path) -> None:
        open_html(
            self.coverage_html_index(build_dir),
            hint=f"Run 'make coverage SIM={self.name}' first.",
        )


class VerilatorProfile(SimulatorProfile):
    name = "verilator"
    supports_coverage = True
    no_covergroups = True

    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
        if cfg.hdl_coverage:
            args.build_args.append("--coverage")
            args.plusargs.append(f"+verilator+coverage+file+{cfg.coverage_dat}")
        return args

    def coverage_html_index(self, build_dir: Path) -> Path:
        return build_dir / "coverage_html" / "index.html"

    def report_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        annotated = build_dir / "coverage_annotated"
        info = build_dir / "coverage.info"
        html_dir = build_dir / "coverage_html"
        verilator_coverage = env_str("VERILATOR_COVERAGE", "verilator_coverage")
        genhtml = env_str("GENHTML", "genhtml")
        min_lines = env_str("COVERAGE_MIN_LINES", "90")
        min_branches = env_str("COVERAGE_MIN_BRANCHES", "90")
        shutil.rmtree(annotated, ignore_errors=True)
        run(
            [
                verilator_coverage,
                "--annotate",
                str(annotated),
                "--annotate-all",
                "--annotate-points",
                "--annotate-min",
                "1",
                "--include-reset-arcs",
                str(coverage_data),
            ]
        )
        run(
            [
                verilator_coverage,
                "--write-info",
                str(info),
                "--include-reset-arcs",
                str(coverage_data),
            ]
        )
        shutil.rmtree(html_dir, ignore_errors=True)
        run(
            [
                genhtml,
                "--branch-coverage",
                "--no-function-coverage",
                "--show-details",
                "--legend",
                "--title",
                "Verilator coverage",
                "--prefix",
                str(project_dir),
                "--fail-under-lines",
                min_lines,
                "--fail-under-branches",
                min_branches,
                "--output-directory",
                str(html_dir),
                str(info),
            ]
        )
        print(f"Coverage data: {coverage_data}")
        print(f"Annotated report: {annotated}")
        print(f"HTML report: {html_dir / 'index.html'}")

    def open_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        print("Verilator has no native GUI coverage viewer.")
        print("Use 'make open-coverage-html' (or 'make open-coverage-html SIM=questa').")


class QuestaProfile(SimulatorProfile):
    name = "questa"
    supports_coverage = True
    supports_gui = True
    disable_pytest_timeout = True
    forces_ansi_on_tty = True

    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
        # cocotb's Questa runner emits one ``vlog`` per source (and none when the
        # source list is empty), so the ``-f`` filelist build arg needs a source
        # to ride along with. The anchor adds no design units; ``vlog`` reads the
        # real design from the filelist alongside it.
        args.sources.append(write_questa_anchor(cfg.build_dir))
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
            # -extendedtogglemode 1 widens toggle coverage (e.g. enum/FSM state
            # bits) so the report lines up with the other simulators.
            args.test_args.extend(["-coverage", "-extendedtogglemode", "1"])
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

    def coverage_data_path(self, build_dir: Path) -> Path:
        return build_dir / "coverage.ucdb"

    def coverage_html_index(self, build_dir: Path) -> Path:
        return build_dir / "coverage_html" / "index.html"

    def report_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        vcover = env_str("VCOVER", "vcover")
        html_dir = build_dir / "coverage_html"
        run([vcover, "report", "-summary", str(coverage_data)])
        shutil.rmtree(html_dir, ignore_errors=True)
        run([vcover, "report", "-html", "-details", "-output", str(html_dir), str(coverage_data)])
        print(f"Coverage UCDB: {coverage_data}")
        print(f"HTML report: {html_dir / 'index.html'}")

    def open_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        require(coverage_data, "Run 'make coverage SIM=questa' first.")
        run([vsim_exe(), "-viewcov", str(coverage_data)])


class VcsProfile(SimulatorProfile):
    name = "vcs"
    supports_coverage = True
    disable_pytest_timeout = True

    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
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

    def coverage_data_path(self, build_dir: Path) -> Path:
        return build_dir / "coverage.vdb"

    def coverage_html_index(self, build_dir: Path) -> Path:
        return build_dir / "urgReport" / "dashboard.html"

    def report_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        urg = env_str("URG", "urg")
        html_dir = build_dir / "urgReport"
        shutil.rmtree(html_dir, ignore_errors=True)
        run([urg, "-dir", str(coverage_data), "-report", str(html_dir), "-format", "both"])
        _print_total_coverage_summary(html_dir / "dashboard.txt")
        print(f"Coverage VDB: {coverage_data}")
        print(f"HTML report: {html_dir / 'dashboard.html'}")
        print(f"Text report: {html_dir / 'dashboard.txt'}")

    def open_coverage(self, project_dir: Path, build_dir: Path, coverage_data: Path) -> None:
        require(coverage_data, "Run 'make coverage SIM=vcs' first.", kind="dir")
        run([*verdi_command(), "-cov", "-covdir", str(coverage_data)])


def _print_total_coverage_summary(dashboard_txt: Path) -> None:
    """Best-effort echo of urg's "Total Coverage Summary" block (grep -A2)."""
    if not dashboard_txt.is_file():
        return
    lines = dashboard_txt.read_text().splitlines()
    for i, line in enumerate(lines):
        if "Total Coverage Summary" in line:
            print("\n".join(lines[i : i + 3]))
            break


SIMULATORS: dict[str, SimulatorProfile] = {
    profile.name: profile for profile in (VerilatorProfile(), QuestaProfile(), VcsProfile())
}
