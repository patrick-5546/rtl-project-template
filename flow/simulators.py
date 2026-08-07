"""Per-simulator profiles describing how each simulator builds, runs, and
reports coverage.

Each profile owns:

* the cocotb runner build/test arguments (:meth:`SimulatorProfile.configure`,
  consumed by :func:`flow.runner.build_and_test`),
* per-simulator defaults (covergroup support, coverage-artifact path),
* the coverage report/open behavior (:meth:`SimulatorProfile.report_coverage`,
  :meth:`SimulatorProfile.open_coverage`, :meth:`SimulatorProfile.open_coverage_html`).

Add a simulator by subclassing :class:`SimulatorProfile`, implementing the
capabilities it supports, and registering an instance in :data:`SIMULATORS`.
"""

import shutil
from pathlib import Path
from typing import override

from flow.runner import (
    RunConfig,
    SimArgs,
    env_flag,
    env_str,
    make_target_command,
    open_html,
    optional_path_from_env,
    project_path_from_env,
    require,
    require_tool_version,
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
    wave_filename: str = ""
    wave_env: str = ""
    supports_coverage: bool = False
    supports_gui: bool = False
    # Verilator parses but ignores SV covergroups, so they are excluded by
    # default there; event-based simulators keep them.
    no_covergroups: bool = False
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

    def wave_path(self, project_dir: Path, build_dir: Path) -> Path:
        """Canonical waveform artifact for this simulator under *build_dir*."""
        if not self.wave_filename:
            raise NotImplementedError(f"{type(self).__name__} does not define wave_filename")
        default = build_dir / self.wave_filename
        return (
            project_path_from_env(self.wave_env, project_dir, default) if self.wave_env else default
        )

    def prepare_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        hdl_toplevel: str,
        sources_files: list[Path],
    ) -> None:
        """Generate simulator-specific auxiliary artifacts after a wave run."""

    def coverage_html_index(self, build_dir: Path) -> Path:
        raise NotImplementedError

    def coverage_hint(self, dut: str, config: str | None) -> str:
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
        config: str | None,
    ) -> None:
        raise NotImplementedError

    def open_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str | None,
    ) -> None:
        raise NotImplementedError

    def open_coverage_html(
        self,
        project_dir: Path,
        build_dir: Path,
        *,
        dut: str,
        config: str | None,
    ) -> None:
        open_html(
            self.coverage_html_index(build_dir),
            hint=self.coverage_hint(dut, config),
        )


class VerilatorProfile(SimulatorProfile):
    name = "verilator"
    wave_filename = "dump.fst"
    wave_env = "WAVE"
    supports_coverage = True
    no_covergroups = True
    minimum_coverage_version = "5.048"

    def require_coverage_version(self, executable: str) -> None:
        require_tool_version(
            executable,
            self.minimum_coverage_version,
            tool_name="Verilator coverage",
        )

    @override
    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
        args.build_args.append("--timing")
        args.build_args.append("-Wno-fatal")
        waivers = Path(__file__).resolve().parents[1] / "rtl" / "verilator_waivers.vlt"
        args.build_args.append(str(waivers))
        if cfg.hdl_coverage:
            self.require_coverage_version(env_str("VERILATOR", "verilator"))
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
    def report_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str | None,
    ) -> None:
        require(coverage_data, self.coverage_hint(dut, config))
        annotated = build_dir / "coverage_annotated"
        info = build_dir / "coverage.info"
        verilator_coverage = env_str("VERILATOR_COVERAGE", "verilator_coverage")
        self.require_coverage_version(verilator_coverage)
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
        print(f"Coverage data: {coverage_data}")
        print(f"Annotated report: {annotated}")
        print(f"LCOV data: {info}")

    @override
    def open_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str | None,
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
        config: str | None,
    ) -> None:
        info = build_dir / "coverage.info"
        require(info, self.coverage_hint(dut, config))
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
                "--fail-under-lines",
                env_str("COVERAGE_MIN_LINES", "90"),
                "--fail-under-branches",
                env_str("COVERAGE_MIN_BRANCHES", "90"),
                "--output-directory",
                str(html_dir),
                str(info),
            ],
            cwd=project_dir,
        )
        open_html(html_dir / "index.html", hint="Check the genhtml output above.")

    @override
    def prepare_waves(
        self,
        project_dir: Path,
        build_dir: Path,
        hdl_toplevel: str,
        sources_files: list[Path],
    ) -> None:
        if env_flag("NO_RTLBROWSE", default=False):
            return
        top = env_str("GTKWAVE_STEMS_TOP", hdl_toplevel)
        json_dir = build_dir / "rtlbrowse"
        verilator = env_str("VERILATOR", "verilator")
        defines = ["+define+ABV=1"] if env_flag("ABV", default=False) else []
        waivers = project_path_from_env(
            "VERILATOR_WAIVERS",
            project_dir,
            project_dir / "rtl" / "verilator_waivers.vlt",
        )
        waiver_args = [str(waivers)] if waivers.is_file() else []
        filelist_args = [arg for sources in sources_files for arg in ("-f", str(sources))]
        json_dir.mkdir(parents=True, exist_ok=True)
        run(
            [
                verilator,
                "-Wno-fatal",
                "--json-only",
                "--bbox-sys",
                "--timing",
                "--sv",
                "--top-module",
                top,
                "--Mdir",
                str(json_dir),
                *defines,
                *waiver_args,
                *filelist_args,
            ],
            cwd=project_dir,
        )
        print(f"Verilator hierarchy JSON: {json_dir / f'V{top}.tree.json'}")


class QuestaProfile(SimulatorProfile):
    name = "questa"
    wave_filename = "vsim.wlf"
    wave_env = "QUESTA_WAVE"
    supports_coverage = True
    supports_gui = True
    forces_ansi_on_tty = True

    @override
    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
        args.build_args.extend(["-mfcu", "-timescale", "1ns/1ps"])
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
    def report_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str | None,
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
        config: str | None,
    ) -> None:
        require(coverage_data, self.coverage_hint(dut, config))
        run([vsim_exe(), "-gui", "-viewcov", str(coverage_data)], cwd=build_dir)


class VcsProfile(SimulatorProfile):
    name = "vcs"
    wave_filename = "dump.fsdb"
    wave_env = "VCS_WAVE"
    supports_coverage = True

    @override
    def configure(self, cfg: RunConfig) -> SimArgs:
        args = super().configure(cfg)
        # cocotb's VCS runner passes no timescale, so VCS would default to 1 s
        # precision and reject the ns-scale clock; pin it explicitly.
        args.build_args.append("-timescale=1ns/1ps")
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
    def report_coverage(
        self,
        project_dir: Path,
        build_dir: Path,
        coverage_data: Path,
        *,
        dut: str,
        config: str | None,
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
        config: str | None,
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
    lines = dashboard_txt.read_text().splitlines()
    for i, line in enumerate(lines):
        if "Total Coverage Summary" in line:
            print("\n".join(lines[i : i + 3]))
            break


SIMULATORS: dict[str, SimulatorProfile] = {
    profile.name: profile for profile in (VerilatorProfile(), QuestaProfile(), VcsProfile())
}
