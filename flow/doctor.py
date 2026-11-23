"""``make doctor``: the external tools that the flow runs, where they are, and their versions.

The report checks presence and versions only; whether a tool works with the flow
is what running the flow shows, as the report's last line says. Each tool is
located as the flow locates it, honoring its executable variable (e.g.
``VERILATOR``). A version older than the flow needs is an error, and so is a
missing tool that ``make test`` needs; only errors fail the report.
A tool that only other targets need is reported missing, with a reminder to run
``mise install`` when mise installs it. A tool that ``mise.toml`` pins is
"verified" at that version, which CI uses, and "untested" at any other; a
Verible other than CI's is a warning instead: Verible's formatting, and so
``make lint-sv``, can differ between versions. Any version of another tool, such
as Verilator, is "ok" when it is not older than the flow needs. The libraries
that Verilator's FST waveforms link, lz4 and zlib, are looked for as the C++
compiler finds them, and reported missing when it does not.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from flow.runner import PROJECT_DIR
from flow.simulators import VerilatorProfile, homebrew_lz4

MISE_CONFIG = PROJECT_DIR / "mise.toml"
# The first uv that reads the relative ``exclude-newer`` in pyproject.toml; older
# ones ignore the whole ``[tool.uv]`` table and relock without it.
UV_MINIMUM = "0.9.17"
# The Makefile rejects an older GNU Make, such as the 3.81 that macOS ships.
MAKE_MINIMUM = "4.0"
# A version as tools print it: 5.054, v0.0-4298-g085eef05, 12.1.627+89a2c9fe9, 2.6-11.g1ad5aed.
VERSION = re.compile(r"(?<!\S)v?(\d+(?:[.-]\d+)+\S*)")
VERSION_TIMEOUT_SECONDS = 30
# The C++ compiler that builds Verilator's models: OSS CAD Suite's verilated.mk names it.
CXX = "g++"


@dataclass(frozen=True)
class Tool:
    name: str
    # The environment variable that overrides the executable, as the flow reads it.
    variable: str = ""
    # Empty for a tool that is only located, such as a commercial one.
    version_args: tuple[str, ...] = ("--version",)
    # The tool's key in mise.toml, which pins the version that mise installs.
    mise: str = ""
    # Verify only an identical version string, since equal numbers are not enough.
    exact: bool = False
    minimum: str = ""
    minimum_for: str = ""


@dataclass(frozen=True)
class Check:
    # "verified", "untested", "ok", "missing", "warning" or "error"
    status: str
    tool: str
    version: str = ""
    path: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Group:
    title: str
    purpose: str
    tools: tuple[Tool, ...]
    required: bool = False
    # The checks of what is not an executable, such as a library that builds link.
    checks: tuple[Callable[[], Check], ...] = ()


def find_header(name: str, header: str, options: list[str], install: str) -> Check:
    """Whether the C++ compiler finds *header*, with *options*, as Verilator's builds do.

    *name* is what the report calls it, and *install* says how to install it.
    """
    try:
        result = subprocess.run(
            [CXX, *options, "-M", "-x", "c++", "-"],
            input=f"#include <{header}>\n",
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired, OSError:
        return Check("missing", name, detail=f"{CXX} did not run, so {header} was not looked for")
    if result.returncode != 0:
        return Check("missing", name, detail=f"{header} not found; {install}")
    headers = result.stdout.replace("\\\n", " ").split()
    return Check("ok", name, path=next((h for h in headers if Path(h).name == header), ""))


def check_lz4() -> Check:
    """Whether Verilator's FST builds find lz4, with Homebrew's on macOS.

    See :func:`flow.simulators.homebrew_lz4`.
    """
    lz4 = homebrew_lz4()
    options = [f"-I{lz4 / 'include'}"] if lz4 else []
    install = "run `brew install lz4`" if sys.platform == "darwin" else "install liblz4-dev"
    return find_header("lz4", "lz4.h", options, install)


def check_zlib() -> Check:
    """Whether Verilator's FST builds find zlib, which macOS's SDK has."""
    install = "run `xcode-select --install`" if sys.platform == "darwin" else "install zlib1g-dev"
    return find_header("zlib", "zlib.h", [], install)


GROUPS = (
    Group(
        "Tests",
        "make test",
        (
            Tool("uv", "UV", mise="uv", minimum=UV_MINIMUM, minimum_for="pyproject.toml"),
            Tool("make", mise="make", minimum=MAKE_MINIMUM, minimum_for="the Makefile"),
            Tool(
                "verilator",
                "VERILATOR",
                minimum=VerilatorProfile.minimum_version,
                minimum_for="the flow",
            ),
        ),
        required=True,
    ),
    Group(
        "Lint",
        "make lint-sv",
        (
            Tool(
                "verible-verilog-format",
                "VERIBLE_FORMAT",
                mise="github:chipsalliance/verible",
                exact=True,
            ),
            Tool(
                "verible-verilog-lint",
                "VERIBLE_LINT",
                mise="github:chipsalliance/verible",
                exact=True,
            ),
            Tool("slang", "SLANG"),
            Tool("slang-tidy", "SLANG_TIDY"),
        ),
    ),
    Group(
        "Coverage",
        "make coverage; genhtml for the HTML report",
        (
            Tool(
                "verilator_coverage",
                "VERILATOR_COVERAGE",
                minimum=VerilatorProfile.minimum_version,
                minimum_for="the flow",
            ),
            Tool("genhtml", "GENHTML", mise="github:linux-test-project/lcov"),
        ),
    ),
    Group(
        "Waveforms",
        "make waves; rtlbrowse for its RTLBrowse window, lz4 and zlib for Verilator's FST",
        (
            Tool("gtkwave", "GTKWAVE"),
            Tool("rtlbrowse", version_args=()),
        ),
        checks=(check_lz4, check_zlib),
    ),
    # Commercial tools are only located: their version commands may need a license.
    Group(
        "Questa",
        "SIM=questa",
        (Tool("vsim", "VSIM", version_args=()), Tool("vcover", "VCOVER", version_args=())),
    ),
    Group(
        "VCS",
        "SIM=vcs",
        (
            Tool("vcs", "VCS", version_args=()),
            Tool("urg", "URG", version_args=()),
            Tool("verdi", "VERDI", version_args=()),
        ),
    ),
)


def mise_pins(config: Path = MISE_CONFIG) -> dict[str, str]:
    """The versions in *config*'s ``[tools]``, by tool key, without a leading ``v``.

    A tool's version is a string, or the ``version`` of a table of its options. Only
    versions count, not requests such as ``latest``.
    """
    if not config.is_file():
        return {}
    tools = tomllib.loads(config.read_text(encoding="utf-8")).get("tools", {})
    pins: dict[str, str] = {}
    for key, value in tools.items():
        version = value.get("version") if isinstance(value, dict) else value
        if isinstance(version, str) and re.match(r"v?\d", version):
            pins[key] = version.removeprefix("v")
    return pins


def version_token(output: str) -> str:
    """The first version in *output*, without a leading ``v``, or ``""``."""
    match = VERSION.search(output)
    return match.group(1) if match else ""


def numbers(version: str) -> tuple[int, ...]:
    """*version*'s leading numbers without trailing zeros, so 2.6-0 and 2.6 are equal."""
    match = re.match(r"\d+(?:[.-]\d+)*", version)
    parts = [int(part) for part in re.split(r"[.-]", match.group(0))] if match else []
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def locate(tool: Tool) -> str | None:
    """*tool*'s executable as the flow would run it, or ``None``."""
    executable = (os.environ.get(tool.variable) if tool.variable else None) or tool.name
    return shutil.which(executable)


def run_version(executable: str, args: tuple[str, ...]) -> tuple[bool, str]:
    """Whether ``executable args`` succeeds, and its output."""
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {VERSION_TIMEOUT_SECONDS} s"
    except OSError as error:
        return False, str(error)
    return result.returncode == 0, f"{result.stdout}\n{result.stderr}".strip()


def check(tool: Tool, pins: Mapping[str, str], *, required: bool) -> Check:
    path = locate(tool)
    if path is None:
        override = os.environ.get(tool.variable) if tool.variable else None
        if override:
            detail = f"not found: {tool.variable}={override}"
        else:
            detail = "not found; run `mise install`" if tool.mise else "not found"
        return Check("error" if required else "missing", tool.name, detail=detail)
    if not tool.version_args:
        return Check("ok", tool.name, path=path)
    succeeded, output = run_version(path, tool.version_args)
    if not succeeded:
        command = shlex.join([tool.name, *tool.version_args])
        first_line = output.splitlines()[0] if output else "no output"
        detail = f"{command} failed: {first_line}"
        return Check("error" if required else "warning", tool.name, path=path, detail=detail)
    version = version_token(output)
    if not version:
        return Check("ok", tool.name, path=path, detail="no version reported")
    if tool.minimum and numbers(version) < numbers(tool.minimum):
        detail = f"{tool.minimum_for} needs {tool.minimum} or newer"
        return Check("error", tool.name, version, path, detail)
    pin = pins.get(tool.mise) if tool.mise else None
    if not pin:
        return Check("ok", tool.name, version, path)
    same = (version == pin) if tool.exact else (numbers(version) == numbers(pin))
    if same:
        return Check("verified", tool.name, version, path)
    if tool.exact:
        return Check("warning", tool.name, version, path, f"CI uses {pin}; formatting can differ")
    return Check("untested", tool.name, version, path, f"CI verifies {pin}")


def report(mise_config: Path = MISE_CONFIG) -> int:
    """Print the check of every tool, by group; return 1 when any is an error, else 0."""
    pins = mise_pins(mise_config)
    errors = 0
    for group in GROUPS:
        print(f"{group.title} ({group.purpose}):")
        results = [check(tool, pins, required=group.required) for tool in group.tools]
        for result in [*results, *(extra() for extra in group.checks)]:
            errors += result.status == "error"
            detail = f"({result.detail})" if result.detail else ""
            where = "  ".join(part for part in (result.path, detail) if part)
            line = f"  {result.status:<8}  {result.tool:<22}  {result.version:<18}  {where}"
            print(line.rstrip())
    print(
        "\nThis checks versions, not whether the tools work with the flow. After installing\n"
        "or updating one, run the flow with it: make lint, make test,\n"
        "make test WAVES=1 and make coverage."
    )
    if errors:
        print(f"{errors} error{'s' if errors > 1 else ''}.")
    return 1 if errors else 0
