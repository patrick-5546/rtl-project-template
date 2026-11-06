"""Per-simulator profiles describing how each simulator builds, runs, and
reports coverage.

Each profile owns:

* the cocotb runner build/test arguments (:meth:`SimulatorProfile.configure`,
  consumed by :func:`flow.runner.build_and_test`),
* per-simulator defaults (wave and coverage artifact paths),
* the coverage report/open behavior (:meth:`SimulatorProfile.report_coverage`,
  :meth:`SimulatorProfile.open_coverage`, :meth:`SimulatorProfile.open_coverage_html`).

Add a simulator by subclassing :class:`SimulatorProfile`, implementing the
capabilities it supports, and registering an instance in :data:`SIMULATORS`.
"""

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import override

from flow.runner import (
    PROJECT_DIR,
    RunConfig,
    SimArgs,
    env_flag,
    env_str,
    make_target_command,
    open_html,
    optional_path_from_env,
    require,
    require_tool_version,
    run,
    verdi_command,
    vsim_exe,
)

# Verilator's control file for the project's RTL: its builds, the RTLBrowse run
# and the lint target read it.
VERILATOR_CONTROL_FILE = PROJECT_DIR / "rtl" / "verilator.vlt"

# The timescale of a module that declares none, on every simulator. The
# Makefile's SV_TIMESCALE gives the linters the same default.
TIMESCALE = "1ns/1ps"


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
        f'    $fsdbDumpvars(0, {hdl_toplevel}, "+all");\n'
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


def add_lcov_line_totals(info: Path) -> None:
    """Add the ``LF``/``LH`` line totals that ``verilator_coverage --write-info`` omits.

    LCOV after 2.6 (its development branch, since lcov#561) rejects a section that has
    ``DA`` line records but no totals; 2.4 to 2.6 recompute them.
    Sections that already have totals, or have no line records, are left unchanged,
    so this is a no-op once Verilator writes the totals itself.
    """
    lines = info.read_text(encoding="utf-8").splitlines()
    output: list[str] = []
    line_hit: dict[str, bool] = {}
    has_totals = False
    for line in lines:
        if line.startswith("SF:"):
            line_hit = {}
            has_totals = False
        elif line.startswith("DA:"):
            number, _, rest = line.removeprefix("DA:").partition(",")
            hits = int(rest.split(",", 1)[0])
            line_hit[number] = line_hit.get(number, False) or hits > 0
        elif line.startswith(("LF:", "LH:")):
            has_totals = True
        elif line == "end_of_record" and line_hit and not has_totals:
            output.extend([f"LF:{len(line_hit)}", f"LH:{sum(line_hit.values())}"])
        output.append(line)
    if output != lines:
        info.write_text("\n".join(output) + "\n", encoding="utf-8")


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


def write_verilator_ports_vlt(build_dir: Path, hdl_toplevel: str) -> Path:
    """Write a Verilator control file that makes *hdl_toplevel*'s ports VPI-accessible.

    cocotb builds Verilator models with ``--public-flat-rw``, which makes every
    signal readable and writable through VPI, and so stops Verilator from
    optimizing most of the design: a large model then simulates many times
    slower. :meth:`VerilatorProfile.configure` turns that off with
    ``--no-public-flat-rw`` and passes this file instead, so that tests see the
    top level's ports only. Waveforms and coverage do not depend on it.

    Only rewritten when its content changes, so that its mtime stays stable.
    """
    build_dir.mkdir(parents=True, exist_ok=True)
    control_file = build_dir / "cocotb_ports.vlt"
    contents = f'`verilator_config\npublic_flat_rw -module "{hdl_toplevel}" -port "*"\n'
    if not control_file.is_file() or control_file.read_text() != contents:
        control_file.write_text(contents)
    return control_file


class SimulatorProfile:
    """Base class for per-simulator build/test/coverage behavior.

    Subclasses set ``name`` and the capability flags, implement
    :meth:`configure`, and (when ``supports_coverage``) the coverage methods.
    Simulators that cocotb supports but that have no profile here still run with
    default arguments.
    """

    name: str = ""
    wave_filename: str = ""
    supports_coverage: bool = False
    supports_gui: bool = False
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

    def wave_path(self, build_dir: Path) -> Path:
        """Canonical waveform artifact for this simulator under *build_dir*."""
        if not self.wave_filename:
            raise NotImplementedError(f"{type(self).__name__} does not define wave_filename")
        return build_dir / self.wave_filename

    def run_outputs(self, build_dir: Path, *, rebuild: bool) -> list[Path]:
        """The waveform, coverage data and reports that a run writes in *build_dir*.

        :func:`flow.runner.build_and_test` deletes them before building, so a
        run that fails to build leaves no previous run's outputs for ``make
        waves`` or ``make coverage`` to open or report. Outputs that span the
        build and the run are listed only when *rebuild* is set.
        """
        outputs = [self.coverage_data_path(build_dir)]
        if self.wave_filename:
            outputs.append(self.wave_path(build_dir))
        return outputs

    def prepare_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        hdl_toplevel: str,
        sources_files: list[Path],
        *,
        defines: Mapping[str, object],
        parameters: Mapping[str, object],
    ) -> None:
        """Generate simulator-specific auxiliary artifacts for a wave run.

        *defines* and *parameters* are the build's, so that the artifacts
        describe the configuration that the build elaborated.
        """

    def coverage_html_index(self, build_dir: Path) -> Path:
        raise NotImplementedError

    def coverage_hint(self, dut: str, config: str) -> str:
        command = make_target_command(
            "coverage",
            simulator=self.name,
            dut=dut,
            config=config,
            waves=env_flag("WAVES", default=False),
        )
        return f"Run '{command}' first."

    def report_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        raise NotImplementedError

    def open_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        raise NotImplementedError

    def open_coverage_html(
        self,
        project_dir: Path,
        build_dir: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        open_html(
            self.coverage_html_index(build_dir),
            hint=self.coverage_hint(dut, config),
        )


class VerilatorProfile(SimulatorProfile):
    name = "verilator"
    wave_filename = "dump.fst"
    supports_coverage = True
    # Verilator 5.050 added SV covergroups, and 5.052 and 5.054 fixed several of
    # their bugs; 5.054 is also the version that CI verifies. Every build and
    # coverage report checks it, so an older Verilator fails up front instead of
    # dropping covergroups from the coverage.
    minimum_version = "5.054"

    def require_version(self, executable: str) -> None:
        require_tool_version(executable, self.minimum_version, tool_name="Verilator")

    def elaboration_args(self) -> list[str]:
        """Options that the build and the RTLBrowse run share, so they see one design.

        A module without a `` `timescale `` gets :data:`TIMESCALE`, as on Questa
        and VCS, instead of Verilator's 1ps/1ps.
        """
        return ["--timing", "--timescale", TIMESCALE, "-Wno-fatal", str(VERILATOR_CONTROL_FILE)]

    @override
    def configure(self, cfg: RunConfig) -> SimArgs:
        self.require_version(env_str("VERILATOR", "verilator"))
        args = super().configure(cfg)
        args.build_args.extend(self.elaboration_args())
        # These follow cocotb's own --public-flat-rw, so they override it.
        args.build_args.append("--no-public-flat-rw")
        args.build_args.append(str(write_verilator_ports_vlt(cfg.build_dir, cfg.hdl_toplevel)))
        if cfg.hdl_coverage:
            args.build_args.append("--coverage")
            args.plusargs.append(f"+verilator+coverage+file+{cfg.coverage_dat}")
        if cfg.waves:
            args.build_args.append("--trace-fst")
            args.build_args.append("--trace-structs")
        return args

    @override
    def coverage_html_index(self, build_dir: Path) -> Path:
        return build_dir / "coverage_html" / "index.html"

    @override
    def run_outputs(self, build_dir: Path, *, rebuild: bool) -> list[Path]:
        reports = ["coverage.info", "coverage_annotated", "coverage_html", "rtlbrowse"]
        return [
            *super().run_outputs(build_dir, rebuild=rebuild),
            *(build_dir / report for report in reports),
        ]

    @override
    def report_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        require(coverage_data, self.coverage_hint(dut, config))
        annotated = build_dir / "coverage_annotated"
        info = build_dir / "coverage.info"
        verilator_coverage = env_str("VERILATOR_COVERAGE", "verilator_coverage")
        self.require_version(verilator_coverage)
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
            ],
            cwd=project_dir,
        )
        run(
            [
                verilator_coverage,
                "--write-info",
                str(info),
                "--include-reset-arcs",
                str(coverage_data),
            ],
            cwd=project_dir,
        )
        add_lcov_line_totals(info)
        print(f"Coverage data: {coverage_data}")
        print(f"Annotated report: {annotated}")
        print(f"LCOV data: {info}")
        # The HTML report needs LCOV's genhtml, so it is written only on request
        # (COVERAGE_HTML=1, or open-coverage-html), never as part of every report.
        if env_flag("COVERAGE_HTML", default=False):
            print(f"HTML report: {self.write_coverage_html(project_dir, build_dir)}")

    def write_coverage_html(self, project_dir: Path, build_dir: Path) -> Path:
        """Write the HTML report of *build_dir*'s LCOV data with genhtml; return its index."""
        html_dir = build_dir / "coverage_html"
        shutil.rmtree(html_dir, ignore_errors=True)
        run(
            [
                env_str("GENHTML", "genhtml"),
                "--branch-coverage",
                "--no-function-coverage",
                "--show-details",
                "--legend",
                "--title",
                "Verilator coverage",
                "--prefix",
                str(project_dir),
                "--output-directory",
                str(html_dir),
                str(build_dir / "coverage.info"),
            ],
            cwd=project_dir,
        )
        return html_dir / "index.html"

    @override
    def open_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        command = make_target_command(
            "open-coverage-html",
            simulator=self.name,
            dut=dut,
            config=config,
            waves=env_flag("WAVES", default=False),
        )
        raise SystemExit(f"Verilator has no native GUI coverage viewer. Use '{command}'.")

    @override
    def open_coverage_html(
        self,
        project_dir: Path,
        build_dir: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        require(build_dir / "coverage.info", self.coverage_hint(dut, config))
        index = self.write_coverage_html(project_dir, build_dir)
        open_html(index, hint="Check the genhtml output above.")

    @override
    def prepare_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        hdl_toplevel: str,
        sources_files: list[Path],
        *,
        defines: Mapping[str, object],
        parameters: Mapping[str, object],
    ) -> None:
        if env_flag("NO_RTLBROWSE", default=False):
            return
        top = hdl_toplevel
        json_dir = build_dir / "rtlbrowse"
        verilator = env_str("VERILATOR", "verilator")
        # Written as cocotb writes them for the build, which this run describes.
        configuration = [
            *(f"-D{name}={value}" for name, value in defines.items()),
            *(f"-G{name}={value}" for name, value in parameters.items()),
        ]
        filelist_args = [arg for sources in sources_files for arg in ("-f", str(sources))]
        json_dir.mkdir(parents=True, exist_ok=True)
        run(
            [
                verilator,
                "--json-only",
                "--bbox-sys",
                "--sv",
                "--top-module",
                top,
                "--Mdir",
                str(json_dir),
                *configuration,
                *self.elaboration_args(),
                *filelist_args,
            ],
            cwd=project_dir,
        )
        print(f"Verilator hierarchy JSON: {json_dir / f'V{top}.tree.json'}")


class QuestaProfile(SimulatorProfile):
    name = "questa"
    wave_filename = "vsim.wlf"
    supports_coverage = True
    supports_gui = True
    forces_ansi_on_tty = True

    @override
    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
        args.build_args.extend(["-mfcu", "-timescale", TIMESCALE])
        # cocotb's Questa runner emits one ``vlog`` per source (and none when the
        # source list is empty), so the ``-f`` filelist build arg needs a source
        # to ride along with. The anchor adds no design units; ``vlog`` reads the
        # real design from the filelist alongside it.
        args.sources.append(write_questa_anchor(cfg.build_dir))
        if cfg.hdl_coverage:
            args.build_args.extend(["-cover", "bcesfx"])
        cfg.wave_path.parent.mkdir(parents=True, exist_ok=True)
        args.test_args = [
            *cfg.questa_args,
            "-wlf",
            str(cfg.wave_path),
            "-nowlfdeleteonquit",
        ]
        if cfg.waves:
            args.test_args[:0] = ["-voptargs=+acc", "-debugdb"]
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

    @override
    def coverage_data_path(self, build_dir: Path) -> Path:
        return build_dir / "coverage.ucdb"

    @override
    def coverage_html_index(self, build_dir: Path) -> Path:
        return build_dir / "coverage_html" / "index.html"

    @override
    def run_outputs(self, build_dir: Path, *, rebuild: bool) -> list[Path]:
        return [*super().run_outputs(build_dir, rebuild=rebuild), build_dir / "coverage_html"]

    @override
    def report_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        vcover = env_str("VCOVER", "vcover")
        html_dir = build_dir / "coverage_html"
        require(coverage_data, self.coverage_hint(dut, config))
        run([vcover, "report", "-summary", str(coverage_data)], cwd=build_dir)
        shutil.rmtree(html_dir, ignore_errors=True)
        run(
            [vcover, "report", "-html", "-details", "-output", str(html_dir), str(coverage_data)],
            cwd=build_dir,
        )
        print(f"Coverage UCDB: {coverage_data}")
        print(f"HTML report: {html_dir / 'index.html'}")

    @override
    def open_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        require(coverage_data, self.coverage_hint(dut, config))
        run([vsim_exe(), "-gui", "-viewcov", str(coverage_data)], cwd=build_dir)


class VcsProfile(SimulatorProfile):
    name = "vcs"
    wave_filename = "dump.fsdb"
    supports_coverage = True

    @override
    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
        # cocotb's VCS runner passes no timescale, so VCS would default to 1 s
        # precision and reject the ns-scale clock; pin it explicitly.
        args.build_args.append(f"-timescale={TIMESCALE}")
        if cfg.waves:
            cfg.wave_path.parent.mkdir(parents=True, exist_ok=True)
            # -kdb gives both the native $fsdb* tasks and the Verdi source DB;
            # the generated dump module is an extra top alongside the DUT.
            args.sources.append(write_fsdb_dump_module(cfg.build_dir, cfg.hdl_toplevel))
            args.build_args.extend(["-kdb", "-top", "cocotb_fsdb_dump"])
            args.plusargs.append(f"+fsdbfile={cfg.wave_path}")
        if cfg.hdl_coverage:
            cm_args = [
                "-cm",
                "line+cond+fsm+tgl+branch+assert",
                "-cm_dir",
                str(cfg.coverage_dat),
                "-cm_noconst",
                "-cm_seqnoconst",
            ]
            args.build_args.extend(cm_args)
            args.test_args.extend(cm_args)
            if cfg.cm_hier is not None and cfg.cm_hier.is_file():
                args.build_args.extend(["-cm_hier", str(cfg.cm_hier)])
        return args

    @override
    def coverage_data_path(self, build_dir: Path) -> Path:
        return build_dir / "coverage.vdb"

    @override
    def coverage_html_index(self, build_dir: Path) -> Path:
        return build_dir / "urgReport" / "dashboard.html"

    @override
    def run_outputs(self, build_dir: Path, *, rebuild: bool) -> list[Path]:
        # The compile writes the coverage database's model and each run adds to
        # it, so it goes only with the build it belongs to.
        outputs = [self.wave_path(build_dir), build_dir / "urgReport"]
        if rebuild:
            outputs.append(self.coverage_data_path(build_dir))
        return outputs

    @override
    def report_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        require(coverage_data, self.coverage_hint(dut, config), kind="dir")
        urg = env_str("URG", "urg")
        html_dir = build_dir / "urgReport"
        shutil.rmtree(html_dir, ignore_errors=True)
        cmd = [urg, "-dir", str(coverage_data), "-report", str(html_dir), "-format", "both"]
        ellist = optional_path_from_env("ELLIST", project_dir)
        if ellist is not None and ellist.is_file():
            cmd.extend(["-elfilelist", str(ellist)])
        run(cmd, cwd=build_dir)
        _print_total_coverage_summary(html_dir / "dashboard.txt")
        print(f"Coverage VDB: {coverage_data}")
        print(f"HTML report: {html_dir / 'dashboard.html'}")
        print(f"Text report: {html_dir / 'dashboard.txt'}")

    @override
    def open_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str,
    ) -> None:
        require(coverage_data, self.coverage_hint(dut, config), kind="dir")
        cmd = [*verdi_command(), "-cov", "-covdir", str(coverage_data)]
        ellist = optional_path_from_env("ELLIST", project_dir)
        if ellist is not None and ellist.is_file():
            cmd.extend(["-elfilelist", str(ellist)])
        run(cmd, cwd=build_dir)


def _print_total_coverage_summary(dashboard_txt: Path) -> None:
    """Best-effort echo of urg's "Total Coverage Summary" block (grep -A2)."""
    if not dashboard_txt.is_file():
        return
    lines = dashboard_txt.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if "Total Coverage Summary" in line:
            print("\n".join(lines[i : i + 3]))
            break


SIMULATORS: dict[str, SimulatorProfile] = {
    profile.name: profile for profile in (VerilatorProfile(), QuestaProfile(), VcsProfile())
}
