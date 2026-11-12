"""``make doctor``: the external tools that the flow runs, where they are, and their versions.

The report checks presence and versions only; whether a tool works with the flow
is what running the flow shows, as the report's last line says. Each tool is
located as the flow locates it, honoring its executable variable (e.g.
``VERILATOR``). A version older than the flow needs is an error, and so is a
missing tool that ``make test`` needs; only errors fail the report.
A tool that only other targets need is reported missing, with a reminder to run
``mise install`` when mise installs it. The version that CI uses is "verified"
and any other "untested": ``mise.toml`` and ``.github/workflows/ci.yml`` pin
them. A Verible other than CI's is a warning instead: Verible's formatting, and
so ``make lint-sv``, can differ between versions.
"""

import os
import re
import shlex
import shutil
import subprocess
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from flow.runner import PROJECT_DIR
from flow.simulators import VerilatorProfile
from flow.viewers import JSON2STEMS_GTKWAVE

CI_WORKFLOW = PROJECT_DIR / ".github" / "workflows" / "ci.yml"
MISE_CONFIG = PROJECT_DIR / "mise.toml"
# The first uv that reads the relative ``exclude-newer`` in pyproject.toml; older
# ones ignore the whole ``[tool.uv]`` table and relock without it.
UV_MINIMUM = "0.9.17"
# A version as tools print it: 5.054, v0.0-4298-g085eef05, 12.1.627+89a2c9fe9, 2.6-11.g1ad5aed.
VERSION = re.compile(r"(?<!\S)v?(\d+(?:[.-]\d+)+\S*)")
VERSION_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Tool:
    name: str
    # The environment variable that overrides the executable, as the flow reads it.
    variable: str = ""
    # Empty for a tool that is only located, such as a commercial one.
    version_args: tuple[str, ...] = ("--version",)
    # The CI workflow's environment variable that pins the tool's version.
    pin: str = ""
    # The tool's key in mise.toml, which pins the version that mise installs.
    mise: str = ""
    # Verify only an identical version string, since equal numbers are not enough.
    exact: bool = False
    minimum: str = ""
    minimum_for: str = ""


@dataclass(frozen=True)
class Group:
    title: str
    purpose: str
    tools: tuple[Tool, ...]
    required: bool = False


GROUPS = (
    Group(
        "Tests",
        "make test",
        (
            Tool("uv", "UV", mise="uv", minimum=UV_MINIMUM, minimum_for="pyproject.toml"),
            Tool("make"),
            Tool(
                "verilator",
                "VERILATOR",
                pin="VERILATOR_VERSION",
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
            Tool("slang", "SLANG", pin="SLANG_VERSION"),
            Tool("slang-tidy", "SLANG_TIDY", pin="SLANG_VERSION"),
        ),
    ),
    Group(
        "Coverage",
        "make coverage; genhtml for the HTML report",
        (
            Tool(
                "verilator_coverage",
                "VERILATOR_COVERAGE",
                pin="VERILATOR_VERSION",
                minimum=VerilatorProfile.minimum_version,
                minimum_for="the flow",
            ),
            Tool("genhtml", "GENHTML", mise="github:linux-test-project/lcov"),
        ),
    ),
    Group(
        "Waveforms",
        f"make waves; RTLBrowse needs json2stems, from GTKWave {JSON2STEMS_GTKWAVE} or newer",
        (
            Tool("gtkwave", "GTKWAVE"),
            Tool("rtlbrowse", version_args=()),
            Tool("json2stems", "JSON2STEMS", version_args=()),
        ),
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


@dataclass(frozen=True)
class Check:
    # "verified", "untested", "ok", "missing", "warning" or "error"
    status: str
    tool: str
    version: str = ""
    path: str = ""
    detail: str = ""


def ci_pins(workflow: Path = CI_WORKFLOW) -> dict[str, str]:
    """The ``*_VERSION`` pins in *workflow*'s ``env``, without a leading ``v``.

    Only literal versions count, not expressions such as ``${{ env.X_VERSION }}``;
    the first definition of each wins.
    """
    if not workflow.is_file():
        return {}
    pins: dict[str, str] = {}
    for name, version in re.findall(
        r"^[ \t]+([A-Z0-9_]+_VERSION):[ \t]*[\"']?v?(\d[^\s\"']*)",
        workflow.read_text(encoding="utf-8"),
        re.MULTILINE,
    ):
        pins.setdefault(name, version)
    return pins


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
    key = tool.pin or tool.mise
    pin = pins.get(key) if key else None
    if not pin:
        return Check("ok", tool.name, version, path)
    same = (version == pin) if tool.exact else (numbers(version) == numbers(pin))
    if same:
        return Check("verified", tool.name, version, path)
    if tool.exact:
        return Check("warning", tool.name, version, path, f"CI uses {pin}; formatting can differ")
    return Check("untested", tool.name, version, path, f"CI verifies {pin}")


def report(workflow: Path = CI_WORKFLOW, mise_config: Path = MISE_CONFIG) -> int:
    """Print the check of every tool, by group; return 1 when any is an error, else 0."""
    pins = ci_pins(workflow) | mise_pins(mise_config)
    errors = 0
    for group in GROUPS:
        print(f"{group.title} ({group.purpose}):")
        for tool in group.tools:
            result = check(tool, pins, required=group.required)
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
