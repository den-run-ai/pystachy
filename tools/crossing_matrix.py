#!/usr/bin/env python3
"""The crossing matrix: which kinds of value enter Any, object, a protocol and a closed union,
and which convert between them.

Each cell (a column of COLUMNS, a row of ROWS) is one small program: it stores the value and then
takes one aspect per statement (shows it, compares it, tests its identity, asks callable(),
calls a protocol method, narrows it with isinstance() and uses it, changes it through its typed
name and shows it again). CPython runs the program and so does the compiler. A statement that the
compiler rejects is recorded with its message and left out, and the program is tried again, so
that one limit does not hide the others. Then the supported rows of a column are put in one
program, the column's differential test, which must compile as the cells' own programs did: what
a store holds alone it holds next to the column's other values. A cell or a column whose output
differs from CPython's, or a column that rejects what its cells accept, is a bug: nothing is
written and the tool fails.

tools/crossing_matrix.json records every cell. From it come the table in docs/dynamic-any.md
(between the two marker comments), one differential test per column
(tests/programs/inference/crossing_COLUMN.py: one function per supported row, its statements
those of the cell's program) and one rejection test per statement that a cell leaves out
(tests/errors/inference/crossing_COLUMN_ROW.py for a value the column does not hold,
crossing_COLUMN_ROW_ASPECT.py for an operation it does not take). So every cell is a test of the
suite: a "yes" must print what CPython prints, a "no" must be rejected with its message, and a
change to either fails until this tool writes the cell again.
tools/test_crossing_matrix.py, which needs no compiler, checks that the four agree.

usage: tools/crossing_matrix.py --compiler ./pystachy [--python python3.13] [--jobs N]
                                (--write | --check) [--work DIR]
  --write  probe every cell and write the JSON file, the tests and the table (record the
           tests' .out afterwards: PYTHON=python3.13 tests/record.sh NAME)
  --check  probe every cell and compare with the JSON file: exit 1 where a cell changed
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = "tools/crossing_matrix.json"
DOC = "docs/dynamic-any.md"
PROGRAMS = "tests/programs/inference"
ERRORS = "tests/errors/inference"
START = "<!-- crossing matrix: written by tools/crossing_matrix.py --write -->"
END = "<!-- end of the crossing matrix -->"

PIECES = {
    "P": '''
class P:
    def __init__(self, v: int) -> None:
        self.v = v

    def describe(self) -> str:
        return "P" + str(self.v)

    def get(self) -> int:
        return self.v

    def __repr__(self) -> str:
        return "P(" + str(self.v) + ")"


class Q(P):
    def describe(self) -> str:
        return "Q" + str(self.v)
''',
    "D": '''
@dataclasses.dataclass
class D:
    a: int
    b: str

    def describe(self) -> str:
        return "D" + str(self.a)
''',
    "N": '''
class N(NamedTuple):
    a: int
    b: str

    def describe(self) -> str:
        return "N" + str(self.a)
''',
    "Color": '''
class Color(enum.Enum):
    RED = 1
    BLUE = 2

    def describe(self) -> str:
        return "Color" + str(self.value)
''',
    "Oops": '''
class Oops(Exception):
    def describe(self) -> str:
        return "Oops " + str(self)
''',
    "T": '''
class T:
    def __init__(self, item):
        self.item = item

    def describe(self) -> str:
        return "T" + repr(self.item)

    def __repr__(self) -> str:
        return "T(" + repr(self.item) + ")"
''',
    "helper": '''
def helper(n: int) -> int:
    return n + 1
''',
    "gen": '''
def gen():
    yield 1
    yield 2
''',
}
PROTOCOL = '''
class Described(Protocol):
    def describe(self) -> str: ...
'''
IMPORTS = {"D": "import dataclasses", "N": "from typing import NamedTuple", "Color": "import enum"}

# name, title in the table, pieces, setup line, expression, isinstance type ("" for none),
# statement run once narrowed, whether print(x) is the same in every run, the union column's
# annotation ("" for none), a change through the typed name ("" for none)
ROWS = [
    ("none", "`None`", "", "", "None", "", "", True, "int | None", ""),
    ("bool", "`bool`", "", "", "True", "bool", "print(not x)", True, "bool | str", ""),
    ("int", "`int`", "", "", "41", "int", "print(x + 1)", True, "int | str", ""),
    ("float", "`float`", "", "", "2.5", "float", "print(x * 2)", True, "float | str", ""),
    ("complex", "`complex`", "", "", "(1 + 2j)", "complex", "print(x.real)", True, "complex | str", ""),
    ("str", "`str`", "", "", "'text'", "str", "print(x.upper())", True, "str | int", ""),
    ("bytes", "`bytes`", "", "", "b'by'", "bytes", "print(x.hex())", True, "bytes | int", ""),
    ("list", "`list[int]`", "", "v: list[int] = [1, 2]", "v", "list", "print(len(x), x[0])", True, "list[int] | int", "v.append(9)"),
    ("dict", "`dict[str, int]`", "", "v: dict[str, int] = {'a': 1}", "v", "dict", "print(len(x), x['a'])", True, "dict[str, int] | int", "v['z'] = 9"),
    ("set", "`set[int]`", "", "v: set[int] = {3}", "v", "set", "print(len(x), 3 in x)", True, "set[int] | int", "v.add(9)"),
    ("frozenset", "`frozenset[int]`", "", "v = frozenset([3])", "v", "frozenset", "print(len(x), 3 in x)", True, "frozenset[int] | int", ""),
    ("tuple", "`tuple[int, str]`", "", "v = (1, 's')", "v", "tuple", "print(len(x), x[0])", True, "tuple[int, str] | int", ""),
    ("vartuple", "`tuple[int, ...]`", "", "v: tuple[int, ...] = (1, 2, 3)", "v", "tuple", "print(len(x), x[0])", True, "tuple[int, ...] | int", ""),
    ("range", "`range`", "", "", "range(3)", "range", "print(len(x))", True, "range | int", ""),
    ("instance", "object of a class", "P", "", "P(1)", "P", "print(x.v, x.describe())", True, "P | int", ""),
    ("subclass", "object of a subclass", "P", "", "Q(2)", "P", "print(x.v, x.describe())", True, "P | int", ""),
    ("dataclass", "dataclass object", "D", "", "D(1, 'b')", "D", "print(x.a, x.describe())", True, "D | int", ""),
    ("namedtuple", "`NamedTuple` object", "N", "", "N(1, 'b')", "N", "print(x.a, x.describe())", True, "N | int", ""),
    ("enum", "enum member", "Color", "", "Color.RED", "Color", "print(x.name, x.describe())", True, "Color | int", ""),
    ("exception", "built-in exception", "", "", "ValueError('bad')", "ValueError", "print(str(x))", True, "ValueError | int", ""),
    ("userexception", "exception of a program class", "Oops", "", "Oops('bad')", "Oops", "print(x.describe())", True, "Oops | int", ""),
    ("template", "object of a class template", "T", "", "T('s')", "T", "print(x.describe())", True, "", ""),
    ("class", "class", "P", "", "P", "type", "print(x.__name__)", True, "", ""),
    ("function", "function", "helper", "", "helper", "", "", False, "", ""),
    ("boundmethod", "bound method", "P", "p = P(5)", "p.get", "", "", False, "", ""),
    ("lambda", "lambda", "", "", "(lambda: 1)", "", "", False, "", ""),
    ("generator", "generator", "gen", "", "gen()", "", "", False, "", ""),
]
IMPLEMENTS = ["instance", "subclass", "dataclass", "namedtuple", "enum", "userexception", "template"]
# name, title in the table
COLUMNS = [
    ("any", "`Any`"),
    ("object", "`object`"),
    ("protocol", "protocol"),
    ("union", "closed union"),
    ("object_to_any", "`object` → `Any`"),
    ("any_to_object", "`Any` → `object`"),
    ("union_to_object", "union → `object`"),
    ("union_to_any", "union → `Any`"),
    ("protocol_to_object", "protocol → `object`"),
    ("protocol_to_any", "protocol → `Any`"),
]
PRAGMA = ["any", "object_to_any", "any_to_object", "union_to_any", "protocol_to_any"]
ASPECTS = {
    "store": "stored",
    "convert": "converted",
    "show": "`print()`, `repr()`, `bool()`",
    "equal": "`==`, `!=`",
    "identity": "`is`",
    "callable": "`callable()`",
    "method": "a protocol method",
    "narrow": "`isinstance()` narrowing",
    "alias": "a change through the typed name",
}
# what a diagnostic's text loses to name its limit: the value's own spelling, and where the
# table of a value's operations was asked for
NORMAL = [
    (r" \(making the table of .*", ""),
    (r"^expected \S+, got .*?: ", ""),
    (r"^an? \S+ value cannot become an Any value", "cannot become an Any value"),
    (r"^an? \S+ cannot become an Any value", "cannot become an Any value"),
    (r"^an? .*? as an Any value is not supported yet", "as an Any value is not supported yet"),
    (r"^an exception object \(.*?\) as Any", "an exception object as Any"),
    (r"^\S+ in a closed union is not supported", "in a closed union is not supported"),
    (r"^'object' object has no method '.*?'", "'object' object has no method"),
    (r": call it, or store .*", ""),
]


def row_of(name):
    for r in ROWS:
        if r[0] == name:
            return r
    raise SystemExit("unknown row " + name)


def cell(column, row):
    # the annotation of x and the annotation x is converted to ("" for none), or None for no cell
    name, union = row[0], row[8]
    if column == "object":
        return "object", ""
    if column == "any":
        return "Any", ""
    if column == "protocol":
        return ("Described", "") if name in IMPLEMENTS else None
    if column == "union":
        return (union, "") if union else None
    if column == "object_to_any":
        return "object", "Any"
    if column == "any_to_object":
        return "Any", "object"
    if column == "union_to_object":
        return (union, "object") if union else None
    if column == "union_to_any":
        return (union, "Any") if union else None
    if column == "protocol_to_object":
        return ("Described", "object") if name in IMPLEMENTS else None
    if column == "protocol_to_any":
        return ("Described", "Any") if name in IMPLEMENTS else None
    raise SystemExit("unknown column " + column)


def parts(column, row, pick="pick"):
    # the cell's statements as (aspect, lines), in order
    name, _, pieces, setup, expr, typ, use, shown, union, change = row
    ann, conv = cell(column, row)
    var = "y" if conv else "x"
    store = []
    if setup:
        store.append("    " + setup)
    store.append(f"    x: {ann} = {pick}({expr})" if column.startswith("union") else f"    x: {ann} = {expr}")
    out = [("store", store)]
    if conv:
        out.append(("convert", [f"    y: {conv} = x"]))
    if shown:
        out.append(("show", [f"    print({var})", f"    print(repr({var}), bool({var}))"]))
    out.append(("equal", [f"    print({var} == {var}, {var} != {var})"]))
    out.append(("identity", [f"    print({var} is {var}, {var} is not {var})"]))
    out.append(("callable", [f"    print(callable({var}))"]))
    if ann == "Described" and not conv:
        out.append(("method", [f"    print({var}.describe())"]))
    if typ:
        u = use if var == "x" else use.replace("(x", "(" + var).replace(" x", " " + var)
        out.append(("narrow", [f"    if isinstance({var}, {typ}):", "        " + u, "    else:", "        print('not narrowed')"]))
    if change:
        out.append(("alias", ["    " + change, f"    print({var})"]))
    return out


def header(column, rows):
    # the lines before the functions of a program that holds rows of column
    lines = []
    if column in PRAGMA:
        lines.append("# pystachy: dynamic-any")
    imports = []
    pieces = []
    anns = []
    for row in rows:
        ann, conv = cell(column, row)
        anns += [ann, conv]
        for p in row[2].split():
            if p not in pieces:
                pieces.append(p)
    if "Any" in anns:
        imports.append("from typing import Any")
    if "Described" in anns:
        imports.append("from typing import Protocol")
    for p in pieces:
        if p in IMPORTS:
            imports.append(IMPORTS[p])
    lines += sorted(set(imports))
    body = ""
    for p in pieces:
        body += "\n" + PIECES[p]
    if "Described" in anns:
        body += "\n" + PROTOCOL
    return lines, body


def text(column, row, dropped):
    # one cell's program, and the aspect of each of its lines
    ann, _ = cell(column, row)
    lines, body = header(column, [row])
    where = {}
    if column.startswith("union"):
        # (a union that cannot hold the value is rejected where pick names it: the store's limit)
        at = len("\n".join(lines + [body.rstrip("\n")]).split("\n")) if lines or body.strip() else 0
        body += f"\n\ndef pick(v: {ann}) -> {ann}:\n    return v\n"
        for i in range(at, at + 5):
            where[i + 1] = "store"
    lines.append(body.rstrip("\n"))
    lines += ["", "", "def main() -> None:"]
    for aspect, ls in parts(column, row):
        if aspect in dropped:
            continue
        for line in ls:
            lines.append(line)
            where[len("\n".join(lines).split("\n"))] = aspect
    lines += ["", "", "main()"]
    return "\n".join(lines) + "\n", where


def asked_by(op, dropped):
    # the aspect whose statement asked for entry op of a value's table, if it is not dropped yet
    if "==" in op or "!=" in op:
        a = "equal"
    elif " is " in op:
        a = "identity"
    elif "isinstance" in op or "narrowing" in op:
        a = "narrow"
    elif "callable" in op:
        a = "callable"
    elif "repr" in op or "str" in op or "truth" in op or "bool" in op:
        a = "show"
    else:
        a = ""
    return "" if a in dropped else a


def limit(message):
    # a diagnostic without the value's own spelling: what names its limit
    for pat, to in NORMAL:
        message = re.sub(pat, to, message)
    hint = message.find(" (", 24)  # (advice in parentheses after the limit itself)
    return (message if hint < 0 else message[:hint]).strip()


def run(compiler, python, path, src):
    # ("same", "", 0), ("rejected", message, line) or ("wrong", detail, 0) for program src
    env = dict(os.environ)
    env["PYSTACHY_HOME"] = os.path.dirname(os.path.abspath(compiler))
    for k in ["PYSTACHY_PATH", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM"]:
        env.pop(k, None)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    want = subprocess.run([python, path], capture_output=True, text=True, timeout=120)
    if want.returncode != 0:
        return "wrong", "CPython fails: " + (want.stderr.strip().splitlines() or [""])[-1], 0
    got = subprocess.run([os.path.abspath(compiler), "run", path], capture_output=True, text=True, timeout=600, env=env)
    if got.returncode == 0 and got.stdout == want.stdout and got.stderr == want.stderr:
        return "same", "", 0
    m = re.search(r"\.py:(\d+): error: (.*)", got.stderr)
    if m is None or got.stdout != "":
        return "wrong", "differs from CPython: " + ((got.stdout + got.stderr).strip().splitlines() or [""])[-1][:200], 0
    return "rejected", m.group(2), int(m.group(1))


def blamed(aspect, message, dropped):
    # the aspect a rejection reported at a statement of aspect is about: a store or a conversion
    # makes the table of the value's operations, each asked for by a later statement
    t = re.search(r"making the table of .*? \(for (.*?)\), converted at", message)
    if t and aspect in ("store", "convert"):
        return asked_by(t.group(1), dropped) or aspect
    return aspect


def probe(compiler, python, work, column, row):
    # one cell: ["yes", {aspect: message}], ["no", aspect, message] or ["wrong", detail]
    path = os.path.join(work, f"{column}__{row[0]}.py")
    dropped = {}
    for _ in range(len(ASPECTS) + 1):
        src, where = text(column, row, dropped)
        how, message, line = run(compiler, python, path, src)
        if how == "same":
            return ["yes", dropped]
        if how == "wrong":
            return ["wrong", message]
        aspect = blamed(where.get(line, ""), message, dropped)
        if aspect == "" or aspect in dropped:
            return ["wrong", "rejected outside the cell's statements: " + message[:200]]
        if aspect in ("store", "convert"):
            return ["no", aspect, message]
        dropped[aspect] = message
    return ["wrong", "too many attempts"]


def probe_together(compiler, python, work, column, rows):
    # the column's program, which holds every row its cells accept with the statements they
    # accept: "" where it prints what CPython prints, else why the column is wrong (a rejection
    # here is of values that each compile alone)
    if not any(held(v) for v in rows.values()):
        return ""
    src, where = program_text(column, rows)
    how, message, line = run(compiler, python, os.path.join(work, f"crossing_{column}.py"), src)
    if how == "same":
        return ""
    if how == "wrong":
        return message
    name, aspect = where.get(line, ("", ""))
    return f"rejected only next to the column's other values (at {name or 'no row'}, {aspect or 'no statement'}): " + message[:300]


def probe_all(compiler, python, work, jobs):
    todo = [(c[0], r) for c in COLUMNS for r in ROWS if cell(c[0], r) is not None]
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futures = {ex.submit(probe, compiler, python, work, c, r): (c, r[0]) for c, r in todo}
        for f in concurrent.futures.as_completed(futures):
            c, r = futures[f]
            out.setdefault(c, {})[r] = f.result()
    cells = {c[0]: {r[0]: out[c[0]][r[0]] for r in ROWS if r[0] in out.get(c[0], {})} for c in COLUMNS}
    if not any(v[0] == "wrong" for rows in cells.values() for v in rows.values()):
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
            futures = {ex.submit(probe_together, compiler, python, work, c, rows): c for c, rows in cells.items()}
            for f in concurrent.futures.as_completed(futures):
                if f.result() != "":
                    cells[futures[f]][" together"] = ["wrong", f.result()]
    return cells


def limits_of(cells):
    # {limit text: [aspect, a sample message, [cell, ...]]}, in the matrix's order
    out = {}
    for c, rows in cells.items():
        for r, v in rows.items():
            for aspect, message in rejected(v):
                out.setdefault(limit(message), [aspect, message, []])[2].append(c + "__" + r)
    return out


def rejection_path(column, row, v, aspect):
    return f"{ERRORS}/crossing_{column}_{row}{'' if v[0] == 'no' else '_' + aspect}.py"


def rejections(cells):
    # {test path: [cell, aspect, the message its first line expects]} of what the cells reject
    out = {}
    for c, rows in cells.items():
        for r, v in rows.items():
            for aspect, message in rejected(v):
                out[rejection_path(c, r, v, aspect)] = [c + "__" + r, aspect, expected(message)]
    return out


def held(v):
    # whether a cell's row is in its column's program
    return v[0] == "yes"


def program_text(column, rows):
    # the differential test of a column, one function per row it holds, and the (row, aspect)
    # of each line
    names = [r for r, v in rows.items() if held(v)]
    lines, body = header(column, [row_of(n) for n in names])
    head = [
        f"# crossing matrix (tools/crossing_matrix.py), column {column}: each kind of value that",
        "# this storage holds, one function per row of the table in docs/dynamic-any.md; a statement",
        "# that the compiler rejects for a row is left out (the table's notes name it)",
    ]
    if lines and lines[0].startswith("# pystachy:"):
        head = [lines[0]] + head
        lines = lines[1:]
    out = head + lines
    out += body.rstrip("\n").split("\n") if body.strip() else []
    where = {}
    if column.startswith("union"):
        for n in names:
            ann, _ = cell(column, row_of(n))
            out += ["", "", f"def pick_{n}(v: {ann}) -> {ann}:", "    return v"]
            where[len(out) - 1] = (n, "store")
            where[len(out)] = (n, "store")
    for n in names:
        out += ["", "", f"def cross_{n}() -> None:"]
        for aspect, ls in parts(column, row_of(n), "pick_" + n):
            if aspect not in rows[n][1]:
                for line in ls:
                    out.append(line)
                    where[len(out)] = (n, aspect)
    out += ["", ""]
    out += [f"cross_{n}()" for n in names]
    return "\n".join(out) + "\n", where


def expected(message):
    # the part of a diagnostic that a cell's rejection test expects, which the compiler prints
    # as it is: the limit's own text where the message holds it, else the message without where
    # its table was made and without the advice after it (limit() drops a name inside it)
    lim = limit(message)
    if lim in message:
        return lim
    message = re.sub(r" \(making the table of .*", "", message)
    hint = message.find(" (", 24)
    return (message if hint < 0 else message[:hint]).strip()


def rejected(v):
    # [(aspect, message)] of what a cell rejects
    return [(v[1], v[2])] if v[0] == "no" else list(v[1].items()) if v[0] == "yes" else []


def rejection_text(where, aspect, expect):
    # the rejection test of a cell: its program up to the rejected statement
    column, name = where.split("__")
    row = row_of(name)
    what = "not " + ASPECTS[aspect] if aspect in ("store", "convert") else "without " + ASPECTS[aspect]
    note = f"# crossing matrix (tools/crossing_matrix.py), column {column}, row {name}: {what}"
    ann, _ = cell(column, row)
    lines, body = header(column, [row])
    if column.startswith("union"):
        body += f"\n\ndef pick(v: {ann}) -> {ann}:\n    return v\n"
    out = ["# error: " + expect, note] + lines + [body.rstrip("\n"), "", "", "def main() -> None:"]
    last = "convert" if aspect == "store" and any(a == "convert" for a, _ in parts(column, row)) else aspect
    for a, ls in parts(column, row):
        # (a value that is stored only to be converted is rejected where it is stored, for the
        # conversion after it)
        if a in ("store", "convert") or a == aspect:
            out += ls
        if a == last:
            break
    out += ["", "", "main()"]
    return "\n".join(out) + "\n"


def table(data):
    # the table's lines and its notes
    limits = data["limits"]
    first = {}  # (the rejection test of each limit's first cell)
    for c, rows in data["cells"].items():
        for r, v in rows.items():
            for aspect, message in rejected(v):
                first.setdefault(limit(message), rejection_path(c, r, v, aspect))
    notes = []

    def note(lim):
        if lim not in notes:
            notes.append(lim)
        return str(notes.index(lim) + 1)

    out = ["| Value | " + " | ".join(t for _, t in COLUMNS) + " |", "| --- |" + " --- |" * len(COLUMNS)]
    for row in ROWS:
        line = "| " + row[1] + " |"
        for c, _ in COLUMNS:
            v = data["cells"].get(c, {}).get(row[0])
            if v is None:
                line += " |"
            elif v[0] == "yes":
                refs = ",".join(note(limit(m)) for m in v[1].values())
                yes = f"[yes](../{PROGRAMS}/crossing_{c}.py)" if held(v) else "yes"
                line += " " + yes + (f"<sup>{refs}</sup>" if refs else "") + " |"
            else:
                line += f" no<sup>{note(limit(v[2]))}</sup> |"
        out.append(line)
    out.append("")
    for i, lim in enumerate(notes):
        aspect = limits[lim]["aspect"]
        # (a value that a column does not hold is rejected where it is stored or where it is
        # converted, as the cells of one limit may differ)
        what = "not held" if aspect in ("store", "convert") else "without " + ASPECTS[aspect]
        n = len(limits[lim]["cells"])
        tests = f"[error test](../{first[lim]})" + ("" if n == 1 else f", one of {n}")
        out.append(f"{i + 1}. {what}: \"{lim}\" ({tests}).")
    return out


def generated(data):
    # {path: text} of the tests this tool writes
    out = {}
    for c, _ in COLUMNS:
        if any(held(v) for v in data["cells"].get(c, {}).values()):
            out[f"{PROGRAMS}/crossing_{c}.py"] = program_text(c, data["cells"][c])[0]
    for path, (where, aspect, expect) in data["tests"].items():
        out[path] = rejection_text(where, aspect, expect)
    return out


def write(data):
    with open(os.path.join(ROOT, DATA), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    keep = generated(data)
    for d in [PROGRAMS, ERRORS]:
        for n in sorted(os.listdir(os.path.join(ROOT, d))):
            if n.startswith("crossing_") and f"{d}/{n[: n.rfind('.')]}.py" not in keep:
                os.remove(os.path.join(ROOT, d, n))  # (a column or a limit that is gone)
    for path, text_ in keep.items():
        with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
            f.write(text_)
    with open(os.path.join(ROOT, DOC), encoding="utf-8") as f:
        doc = f.read()
    if START not in doc or END not in doc:
        raise SystemExit(f"{DOC}: the markers of the crossing matrix are missing")
    before, rest = doc.split(START, 1)
    _, after = rest.split(END, 1)
    doc = before + START + "\n" + "\n".join(table(data)) + "\n" + END + after
    with open(os.path.join(ROOT, DOC), "w", encoding="utf-8") as f:
        f.write(doc)


def build(cells):
    limits = {}
    for lim, (aspect, _, where) in limits_of(cells).items():
        limits[lim] = {"aspect": aspect, "cells": where}
    return {"cells": cells, "limits": limits, "tests": rejections(cells)}


def summary(v):
    # what --check compares of a cell
    if v is None:
        return None
    if v[0] == "no":
        return ["no", limit(v[2])]
    return ["yes", sorted(limit(m) for m in v[1].values())]


def rejects(compiler, path, expect):
    # whether the compiler rejects the rejection test at path with the message it expects
    env = dict(os.environ)
    env["PYSTACHY_HOME"] = os.path.dirname(os.path.abspath(compiler))
    got = subprocess.run([os.path.abspath(compiler), "ir", path], capture_output=True, text=True, timeout=600, env=env)
    return got.returncode == 1 and expect in got.stderr


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--compiler", required=True)
    ap.add_argument("--python", default="python3")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--work", default="")
    how = ap.add_mutually_exclusive_group(required=True)
    how.add_argument("--write", action="store_true")
    how.add_argument("--check", action="store_true")
    a = ap.parse_args()
    work = a.work or tempfile.mkdtemp(prefix="crossing.")
    os.makedirs(work, exist_ok=True)
    cells = probe_all(a.compiler, a.python, work, a.jobs)
    wrong = [(c, r, v[1]) for c, rows in cells.items() for r, v in rows.items() if v[0] == "wrong"]
    for c, r, why in wrong:
        print(f"WRONG {c}/{r.strip()}: {why} (program: {os.path.join(work, ('crossing_' + c if r.startswith(' ') else c + '__' + r) + '.py')})")
    if wrong:
        return 1
    data = build(cells)
    if a.write:
        write(data)
        with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as ex:
            ok = list(ex.map(lambda item: rejects(a.compiler, os.path.join(ROOT, item[0]), item[1][2]), data["tests"].items()))
        bad = [path for path, good in zip(data["tests"], ok, strict=True) if not good]
        for t in bad:
            print(f"WRONG {t}: not rejected with the message it expects")
        print(f"wrote {DATA}: {len(data['limits'])} limits, {len(data['tests'])} rejection tests; record the differential tests' .out with tests/record.sh")
        return 1 if bad else 0
    with open(os.path.join(ROOT, DATA), encoding="utf-8") as f:
        old = json.load(f)
    changed = 0
    for c, rows in cells.items():
        for r, v in rows.items():
            was = summary(old["cells"].get(c, {}).get(r))
            if summary(v) != was:
                changed += 1
                print(f"CHANGED {c}/{r}: recorded {was}, now {summary(v)}")
    print(f"{sum(len(rows) for rows in cells.values())} cells, {changed} changed")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
