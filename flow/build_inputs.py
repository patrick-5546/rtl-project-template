"""The files a build reads, so that ``REBUILD=0`` notices when they change.

cocotb decides whether a VCS build is current from ``simv``'s timestamp and the
``sources`` it is given, which leave out the RTL that ``-f`` filelists name, and
Questa compiles with ``-incr`` whatever changed. :func:`filelist_dependencies`
follows the filelists to that RTL and the files it includes, and
:func:`files_digest` digests their content for the build record.
"""

import hashlib
import os
import re
import shlex
from pathlib import Path

_INCLUDE_RE = re.compile(r'^\s*(?:`include|#\s*include)\s+"([^"]+)"', re.MULTILINE)
# Preserve paths and escapes when stripping whitespace-delimited // comments.
_FILELIST_COMMENT_RE = re.compile(r"""("(?:\\.|[^"\\])*"|'[^']*'|\\.)|(?<!\S)//.*""")
_HDL_SUFFIXES = {".v", ".vh", ".sv", ".svh"}


def _resolve_path(value: str, *, relative_to: Path, project_dir: Path) -> Path:
    expanded = Path(os.path.expandvars(Path(value).expanduser()))
    if expanded.is_absolute():
        return expanded.resolve()
    local = (relative_to / expanded).resolve()
    return local if local.exists() else (project_dir / expanded).resolve()


def filelist_dependencies(filelists: list[Path], project_dir: Path) -> list[Path]:
    """The *filelists*, the files they name, and the files those include.

    Follows ``-f``/``-F`` filelists, ``-v`` library files and ``-y`` library
    directories, expands environment variables such as ``${PROJECT_ROOT}``, and
    finds quoted ``include`` files beside each source or on its ``+incdir+``
    directories.
    """
    dependencies: set[Path] = set()
    include_dirs: list[Path] = []
    sources: list[Path] = []
    pending = list(filelists)

    def add_source(value: str, *, relative_to: Path) -> None:
        source = _resolve_path(value, relative_to=relative_to, project_dir=project_dir)
        dependencies.add(source)
        if source.suffix.lower() in _HDL_SUFFIXES:
            sources.append(source)

    def add_library_dir(value: str, *, relative_to: Path) -> None:
        directory = _resolve_path(value, relative_to=relative_to, project_dir=project_dir)
        dependencies.add(directory)
        if directory.is_dir():
            for source in directory.iterdir():
                if source.is_file() and source.suffix.lower() in _HDL_SUFFIXES:
                    dependencies.add(source.resolve())
                    sources.append(source.resolve())

    while pending:
        filelist = pending.pop()
        if filelist in dependencies:
            continue
        dependencies.add(filelist)
        if not filelist.is_file():
            continue
        for line_number, raw in enumerate(
            filelist.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            line = _FILELIST_COMMENT_RE.sub(r"\1", raw).strip()
            if not line or line.startswith("#"):
                continue
            fields = iter(shlex.split(line, comments=True))
            for field in fields:
                if field.startswith("+incdir+"):
                    include_dirs.extend(
                        _resolve_path(value, relative_to=filelist.parent, project_dir=project_dir)
                        for value in field.removeprefix("+incdir+").split("+")
                        if value
                    )
                elif field in {"-f", "-F", "-v", "-y"}:
                    value = next(fields, None)
                    if not value:
                        raise ValueError(f"{filelist}:{line_number}: {field} requires a path")
                    if field in {"-f", "-F"}:
                        pending.append(
                            _resolve_path(
                                value, relative_to=filelist.parent, project_dir=project_dir
                            )
                        )
                    elif field == "-v":
                        add_source(value, relative_to=filelist.parent)
                    else:
                        add_library_dir(value, relative_to=filelist.parent)
                elif field.startswith(("-f", "-F")) and len(field) > 2:
                    pending.append(
                        _resolve_path(
                            field[2:], relative_to=filelist.parent, project_dir=project_dir
                        )
                    )
                elif field.startswith("-y") and len(field) > 2:
                    add_library_dir(field[2:], relative_to=filelist.parent)
                elif not field.startswith(("+", "-")):
                    add_source(field, relative_to=filelist.parent)

    dependencies.update(include_dependencies(sources, include_dirs))
    return sorted(dependencies)


def include_dependencies(sources: list[Path], include_dirs: list[Path]) -> list[Path]:
    """*sources* and the files they quote-include, recursively."""
    dependencies: set[Path] = set(sources)
    pending_sources = list(sources)
    scanned: set[Path] = set()
    while pending_sources:
        source = pending_sources.pop()
        if source in scanned or not source.is_file():
            continue
        scanned.add(source)
        for include in _INCLUDE_RE.findall(source.read_text(encoding="utf-8", errors="replace")):
            candidates = [source.parent / include, *(path / include for path in include_dirs)]
            resolved = next((path.resolve() for path in candidates if path.is_file()), None)
            if resolved is not None and resolved not in dependencies:
                dependencies.add(resolved)
                pending_sources.append(resolved)
    return sorted(dependencies)


def files_digest(paths: list[Path]) -> str:
    """A digest of each of *paths* and its content; a missing file counts too."""
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(b"path\0")
        digest.update(str(path).encode())
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
        digest.update(b"\0")
    return digest.hexdigest()
