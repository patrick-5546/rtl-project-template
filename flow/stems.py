# Ported from GTKWave's json2stems (contrib/json2stems/json2stems.cc in GTKWave
# 3.3.125 and newer), which carries this notice:
#
# Copyright (c) 2025 Leon Wandruschka.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
"""The stems that GTKWave's RTLBrowse reads, from Verilator's design tree.

RTLBrowse finds each module's source, and each instance's module, in a stems
file. :func:`write_stems` writes it from the JSON design tree that Verilator
writes with ``--json-only``, one line per module and per instance:

    ++ module <module> file <path> lines <first> - <last>
    ++ comp <instance> type <module> parent <module>

It ports GTKWave's ``json2stems``, which only GTKWave 3 ships, so that RTLBrowse
works with any GTKWave. Its stems are json2stems' except that they leave out the
modules that Verilator makes itself, such as ``$unit`` and ``__Vconstpool``:
their file is ``<built-in>``, which RTLBrowse cannot open, and GTKWave 4's
RTLBrowse opens the first module at startup.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

# The file of the modules that Verilator makes itself.
BUILT_IN = "<built-in>"
# A location's first and last lines, after its file: "6:8,6:11" in "g,6:8,6:11".
LINES = re.compile(r"(\d+):\d+,(\d+):\d+")


def stems(meta: Mapping[str, Any], tree: Mapping[str, Any]) -> str:
    """The stems of Verilator's design *tree*, whose source files *meta* lists.

    An instance whose module is not in the tree has the type ``UNKNOWN``.
    """
    paths = {
        file_id: file["realpath"]
        for file_id, file in meta.get("files", {}).items()
        if "filename" in file
    }
    modules = tree.get("modulesp", [])
    names = {
        module["addr"]: module["name"] for module in modules if {"addr", "name"} <= module.keys()
    }
    lines: list[str] = []
    for module in modules:
        if not {"name", "loc"} <= module.keys():
            continue
        name = module["name"]
        file_id, _, location = module["loc"].partition(",")
        path = paths.get(file_id)
        if path == BUILT_IN:
            continue
        if path is not None:
            match = LINES.match(location)
            first, last = (int(match[1]), int(match[2])) if match else (0, 0)
            lines.append(f"++ module {name} file {path} lines {first} - {last}\n")
        lines.extend(
            f"++ comp {cell['name']} type {names.get(cell.get('modp'), 'UNKNOWN')} parent {name}\n"
            for cell in module.get("stmtsp", [])
            if cell.get("type") == "CELL" and "name" in cell
        )
    return "".join(lines)


def write_stems(tree_meta: Path, tree_json: Path, path: Path) -> None:
    """Write to *path* the stems of the design tree in Verilator's *tree_json*.

    *tree_meta* is the ``.tree.meta.json`` that Verilator writes beside it.
    """
    meta = json.loads(tree_meta.read_text(encoding="utf-8"))
    tree = json.loads(tree_json.read_text(encoding="utf-8"))
    path.write_text(stems(meta, tree), encoding="utf-8")
