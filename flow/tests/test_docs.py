"""Checks that the docs agree with the code and CI that they describe."""

import re
import tomllib
from pathlib import Path

import pytest

from flow import doctor
from flow.viewers import JSON2STEMS_GTKWAVE

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DOC = REPO_ROOT / "docs" / "tools.md"
DOCS = [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md", *sorted(REPO_ROOT.glob("docs/*.md"))]
# A Markdown link's target, as in [text](target).
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def prose(path: Path) -> str:
    """*path*'s Markdown without its fenced code blocks."""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"^```.*?^```", "", text, flags=re.MULTILINE | re.DOTALL)


def flattened(path: Path) -> str:
    """*path*'s text with each run of whitespace, such as a line break, as one space."""
    return " ".join(path.read_text(encoding="utf-8").split())


def anchors(path: Path) -> set[str]:
    """The anchors that GitHub gives *path*'s headings."""
    headings = re.findall(r"^#+\s+(.+?)\s*$", prose(path), re.MULTILINE)
    return {re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-") for heading in headings}


def verified_versions() -> dict[str, str]:
    """The verified environment in docs/tools.md, by lowercase tool name."""
    section = TOOLS_DOC.read_text(encoding="utf-8").split("## Verified environment", 1)[1]
    rows = re.findall(r"^\| ([^|]+?) \| ([^|]+?) \|$", section, re.MULTILINE)
    return {tool.lower(): version for tool, version in rows}


@pytest.mark.parametrize("pin", sorted(doctor.ci_pins()))
def test_verified_versions_are_the_ci_pins(pin: str) -> None:
    tool = pin.removesuffix("_VERSION").lower()
    documented = verified_versions().get(tool, "missing").removeprefix("v")
    assert documented == doctor.ci_pins()[pin], f"docs/tools.md: {tool} {documented}"


@pytest.mark.parametrize(
    "minimum",
    sorted(
        {tool.minimum for group in doctor.GROUPS for tool in group.tools if tool.minimum}
        | {JSON2STEMS_GTKWAVE}
    ),
)
def test_minimum_versions_are_documented(minimum: str) -> None:
    assert f"{minimum} or newer" in flattened(TOOLS_DOC)


def test_python_version_is_consistent() -> None:
    version = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    major, minor = (int(part) for part in version.split("."))
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["requires-python"] == f">={version},<{major}.{minor + 1}"
    tools_doc = flattened(TOOLS_DOC)
    assert f"pinned to `{version}`" in tools_doc
    assert f"move to Python {major}.{minor + 1} once" in tools_doc


@pytest.mark.parametrize("doc", DOCS, ids=[doc.relative_to(REPO_ROOT).as_posix() for doc in DOCS])
def test_relative_links_resolve(doc: Path) -> None:
    for target in LINK.findall(prose(doc)):
        if re.match(r"[a-z][a-z0-9+.-]*:", target):
            continue
        path, _, anchor = target.partition("#")
        linked = (doc.parent / path).resolve() if path else doc
        assert linked.exists(), f"{target} does not exist"
        if anchor:
            assert anchor in anchors(linked), f"{target} names no heading"


def test_agent_instructions_name_existing_docs() -> None:
    names = re.findall(r"`([\w./-]+\.md)`", (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    assert names
    assert [name for name in names if not (REPO_ROOT / name).is_file()] == []
