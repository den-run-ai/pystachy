"""Annotations for a library to port, from Pyrefly's inference, kept where Pystachy can use them.

usage: python3 -I tools/prepare_port.py infer [--policy templates|signatures|raw] [--untype]
           [--passes N] [--pyrefly EXE] SRC OUT
       python3 -I tools/prepare_port.py check [--ref REF] [--aot] [--stats] [--json OUT.json]
           LIBPATH WORKLOAD.py ...

infer: SRC is a library's package directory (or its one .py file); it is never changed. A copy,
OUT/pyrefly/NAME, gets Pyrefly's own annotations: `pyrefly infer` of version PYREFLY, with
CONFIG, for PASSES passes or until one changes nothing (each pass annotates what the one before
made checkable). Each annotation Pyrefly adds is a suggestion. OUT/NAME is SRC with the
suggestions the policy keeps, OUT/prepare.patch the diff from SRC to it, OUT/report.json each
suggestion, kept or dropped and why. OUT/NAME is for review: it changes nothing but annotations.

- templates (the default): a function with an unannotated parameter is a template in Pystachy,
  compiled for each call's argument types, so parameters stay unannotated. Pyrefly runs with
  --parameter-types=false, so that no return type it infers rests on a parameter type it guessed
  from the library's own calls. Its return types are kept where Pystachy supports them.
- signatures: parameters too, where supported.
- raw: Pyrefly's output as it is, for comparison.

Under templates and signatures, a suggestion is kept only where Pystachy has its type (docs/
language.md, Types): Any, object, unions other than T | None, bytes, iterators, generators,
tuple[T, ...], Callable[..., R], Literal and names that are not the library's classes are
dropped and reported. A function with no unannotated parameter (self and cls aside; also one with
none at all) returns None in Pystachy unless it is annotated, so such a function that returns a
value needs Pyrefly's return type: a "signatures" function without one keeps its parameters
unannotated, and one that had all its annotations before is reported as a blocker. CPython 3.13
evaluates a def's annotations when the def runs, so a class of the module that is not bound yet
(a method's own class, or one defined further on) is written as a string, `Self` as its class's
name, and a suggestion that needs a name the module has not bound by then is dropped. A class
body's variables get no annotation (it would make a dataclass field).

SRC's own annotations that Pystachy does not support are reported as blockers. With --untype, a
parameter's or return's is left out instead, before Pyrefly runs (which may then infer a type
there), so that the def becomes a template where Pystachy compiles one per call: Any, a union of
str | bytes | list, Callable[..., R]. But not __init__'s parameters (they would make the class a
class template: one specialization per argument type, a choice of design to make by hand) nor a
variable's (a field's annotation makes it a dataclass field).

check: LIBPATH is a directory on the module path that holds the library (OUT, for OUT/NAME). Each
WORKLOAD is a program that imports it, run with arguments a1 a2 and stdin WORKLOAD's .in (or
/dev/null) as tests/run.sh runs one: under CPython with REF on the path (default LIBPATH), the
reference; under CPython with LIBPATH where REF differs (annotations must not change what CPython
prints); and with `pystachy run`, and `pystachy build` with --aot. A compile error is classified
by what the port would need: an annotation, an annotation Pystachy supports, a module, one type
per value (where CPython's values of a name or an expression have several), or a language feature. --stats counts the template specializations (of the
4,096 one compilation may make) and the IR lines of each workload, compiled once more by
pystachy.py on CPython. Exit status 1 if any workload fails.
"""
import argparse
import ast
import difflib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
PYREFLY = "1.3.2"
CONFIG = 'preset = "default"\npython-version = "3.13"\n'

# docs/language.md, Types: what an annotation may name
SCALARS = {"int", "float", "bool", "str", "TextIO"}
GENERIC = {"list": 1, "List": 1, "set": 1, "Set": 1, "frozenset": 1, "FrozenSet": 1, "dict": 2, "Dict": 2,
           "Sequence": 1, "MutableSequence": 1, "MutableSet": 1, "Mapping": 2, "MutableMapping": 2}
WHY = {"Any": "Any", "object": "object", "bytes": "bytes", "bytearray": "bytes", "memoryview": "bytes",
       "complex": "complex", "Iterator": "an iterator", "Iterable": "an iterator", "Generator": "a generator",
       "AsyncIterator": "an iterator", "Awaitable": "async", "Coroutine": "async", "Literal": "Literal",
       "LiteralString": "LiteralString", "type": "type[...]", "Type": "type[...]", "NoReturn": "NoReturn",
       "Never": "NoReturn", "TypeGuard": "TypeGuard", "TypeIs": "TypeGuard"}
BUILTIN = {"int", "float", "bool", "str", "list", "dict", "set", "frozenset", "tuple", "type", "None", "object"}


# ---- annotation sites ----------------------------------------------------------------------------
# A site is (scope, kind, name): a parameter ("param", "*args" for a star one), a def's return
# ("return", ""), or the first binding of a variable in a scope ("var", x or self.x). A scope is a
# def's or class's qualified name; a def that repeats a name in its scope (a property's setter, the
# else branch's def) is NAME#2, and so on. A def decorated with @overload is left out: CPython
# replaces it with the def after it, and Pystachy drops it.

def index(tree):
    """{site: node} (the ast.arg, the def for its return, or the statement that binds a var site:
    an AnnAssign anywhere in the scope rather than an Assign), and {def's scope: (def, the name of
    the class whose body holds it, or "")}."""
    out, fns = {}, {}

    def visit(node, scope, cls, seen):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any((d.id if isinstance(d, ast.Name) else d.attr if isinstance(d, ast.Attribute) else "") == "overload"
                       for d in ch.decorator_list):
                    continue
                q = f"{scope}.{ch.name}" if scope else ch.name
                seen[q] = seen.get(q, 0) + 1
                q += f"#{seen[q]}" if seen[q] > 1 else ""
                fns[q] = (ch, cls)
                a = ch.args
                for p in a.posonlyargs + a.args + a.kwonlyargs:
                    out[(q, "param", p.arg)] = p
                for p in (a.vararg, a.kwarg):
                    if p:
                        out[(q, "param", "*" + p.arg)] = p
                out[(q, "return", "")] = ch
                visit(ch, q, "", {})
            elif isinstance(ch, ast.ClassDef):
                visit(ch, f"{scope}.{ch.name}" if scope else ch.name, ch.name, {})
            elif isinstance(ch, ast.AnnAssign):
                k = (scope, "var", ast.unparse(ch.target))
                if k not in out or isinstance(out[k], ast.Assign):
                    out[k] = ch
                visit(ch, scope, cls, seen)
            elif isinstance(ch, ast.Assign):
                for t in ch.targets:
                    if isinstance(t, (ast.Name, ast.Attribute)):
                        out.setdefault((scope, "var", ast.unparse(t)), ch)
                visit(ch, scope, cls, seen)
            elif not isinstance(ch, ast.Lambda):
                visit(ch, scope, cls, seen)

    visit(tree, "", "", {})
    return out, fns


def defs(tree):
    return index(tree)[0]


def annotation(node):
    if isinstance(node, ast.arg):
        return ast.unparse(node.annotation) if node.annotation else None
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ast.unparse(node.returns) if node.returns else None
    if isinstance(node, ast.AnnAssign):
        return ast.unparse(node.annotation)
    return None


def sites(src):
    """{site: its annotation's text, or None}."""
    return {k: annotation(n) for k, n in defs(ast.parse(src)).items()}


class Text:
    """Source text, with ast's positions (1-based lines, columns in UTF-8 bytes) as offsets in it."""

    def __init__(self, src):
        self.src = src
        self.lines = src.splitlines(keepends=True)
        self.starts = [0]
        for ln in self.lines:
            self.starts.append(self.starts[-1] + len(ln))

    def off(self, line, col):
        return self.starts[line - 1] + len(self.lines[line - 1].encode("utf-8")[:col].decode("utf-8", "replace"))


def header_end(text, fn):
    """The offset just after the ')' that closes fn's parameters."""
    start = text.off(fn.lineno, fn.col_offset)
    head = text.src[start:text.off(fn.body[0].lineno, fn.body[0].col_offset)]
    depth = 0
    for t in tokenize.generate_tokens(io.StringIO(head).readline):
        if t.type == tokenize.OP and t.string in ("(", ")"):
            depth += 1 if t.string == "(" else -1
            if depth == 0:  # (tokenize's columns count characters)
                return start + Text(head).starts[t.end[0] - 1] + t.end[1]
    raise ValueError(f"line {fn.lineno}: no parameter list")


def edit(src, changes):
    """src with each site's annotation set to changes[site] (None removes it), and [(site, why)]
    for the sites it could not edit."""
    text = Text(src)
    nodes = defs(ast.parse(src))
    edits, skipped = [], []
    for site, new in changes.items():
        n = nodes.get(site)
        if n is None:
            skipped.append((site, "no such site"))
        elif isinstance(n, ast.arg):
            # (PEP 8: a default's = has spaces around it after an annotation, and none without one)
            name_end = text.off(n.lineno, n.col_offset) + len(n.arg)
            if n.annotation is not None:
                a0 = text.off(n.annotation.lineno, n.annotation.col_offset)
                a1 = text.off(n.annotation.end_lineno, n.annotation.end_col_offset)
                eq = re.match(r"[ \t]*=[ \t]*", src[a1:])
                if new is not None:
                    edits.append((a0, a1, new))
                elif eq:
                    edits.append((name_end, a1 + eq.end(), "="))
                else:
                    edits.append((name_end, a1, ""))
            elif new is not None:
                eq = re.match(r"[ \t]*=[ \t]*", src[name_end:])
                edits.append((name_end, name_end + eq.end(), f": {new} = ") if eq else (name_end, name_end, ": " + new))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.returns is not None:
                r0 = text.off(n.returns.lineno, n.returns.col_offset)
                r1 = text.off(n.returns.end_lineno, n.returns.end_col_offset)
                edits.append((header_end(text, n), r1, "") if new is None else (r0, r1, new))
            elif new is not None:
                e = header_end(text, n)
                edits.append((e, e, " -> " + new))
        elif isinstance(n, ast.AnnAssign):
            a0 = text.off(n.annotation.lineno, n.annotation.col_offset)
            a1 = text.off(n.annotation.end_lineno, n.annotation.end_col_offset)
            if new is not None:
                edits.append((a0, a1, new))
            elif n.value is not None:
                edits.append((text.off(n.target.end_lineno, n.target.end_col_offset), a1, ""))
            else:
                skipped.append((site, "a declaration without a value"))
        elif new is not None:  # an Assign
            if len(n.targets) != 1:
                skipped.append((site, "a chained assignment"))
                continue
            t1 = text.off(n.targets[0].end_lineno, n.targets[0].end_col_offset)
            edits.append((t1, t1, ": " + new))
    for s, e, rep in sorted(edits, key=lambda x: -x[0]):
        src = src[:s] + rep + src[e:]
    ast.parse(src)  # (an edit that breaks the syntax is a bug here)
    return src, skipped


# ---- which suggestions Pystachy can use -----------------------------------------------------------

def unsupported(ann, classes, in_method, kind, fn="", typevars=()):
    """Why Pystachy has no such type, or "" where it has; classes: the library's class names, fn:
    the name of the def whose parameter or return it annotates, typevars: the module's TypeVars
    (a def's parameter or return that mentions one is unannotated to Pystachy, but __init__'s)."""
    try:
        e = ast.parse(ann, mode="eval").body
    except SyntaxError:
        return "not an expression"
    if kind != "return" and isinstance(e, ast.Constant) and e.value is None:
        return "None as a variable's type"
    if (kind == "return" and fn == "__iter__" and isinstance(e, ast.Subscript) and isinstance(e.value, ast.Name)
            and e.value.id in ("Iterator", "Iterable")):
        e = e.slice  # (__iter__'s Iterator[T], which iterates as a list's iterator does)
    if kind == "var" and isinstance(e, ast.Subscript) and isinstance(e.value, ast.Name) and e.value.id == "Final":
        e = e.slice  # (x: Final[T] is x: T)
    elif kind == "var" and isinstance(e, ast.Name) and e.id == "Final":
        return ""

    def why(e):
        if isinstance(e, ast.Constant):
            if e.value is None:
                return ""
            if isinstance(e.value, str):  # a forward reference
                return why(ast.parse(e.value, mode="eval").body)
            return "a constant"
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.BitOr):
            return union([e.left, e.right])
        if isinstance(e, ast.Attribute):
            return why(ast.Name(e.attr)) if isinstance(e.value, ast.Name) and e.value.id == "typing" else f"name {ast.unparse(e)}"
        if isinstance(e, ast.Name):
            n = e.id
            if n in WHY:
                return WHY[n]
            if n in SCALARS or n in classes or n == "None" or (n == "Self" and in_method):
                return ""
            if n in typevars:
                return "" if kind != "var" and fn != "__init__" else "a TypeVar (only a def's parameters and return, not __init__'s)"
            if n in GENERIC or n in ("tuple", "Tuple", "Callable"):
                return f"{n} without its item types" if n != "Callable" else "Callable without its signature"
            return f"name {n}, which is no class of the library (a TypeVar, an alias, another package's class)"
        if isinstance(e, ast.Subscript):
            base = e.value.attr if isinstance(e.value, ast.Attribute) else e.value.id if isinstance(e.value, ast.Name) else ""
            args = list(e.slice.elts) if isinstance(e.slice, ast.Tuple) else [e.slice]
            if base in WHY:
                return WHY[base]
            if base == "Optional":
                return union([args[0], ast.Constant(None)])
            if base == "Union":
                return union(args)
            if base in ("tuple", "Tuple"):
                if any(isinstance(a, ast.Constant) and a.value is Ellipsis for a in args):
                    return "tuple[T, ...] (a run-time length)"
                if len(args) > 9:
                    return "a tuple of more than 9 items"
                return next((w for w in map(why, args) if w), "")
            if base == "Callable":
                if isinstance(args[0], ast.Constant) and args[0].value is Ellipsis:
                    return "Callable[..., R]"
                return next((w for w in map(why, (args[0].elts if isinstance(args[0], ast.List) else []) + args[1:]) if w), "")
            if base in GENERIC:
                if len(args) != GENERIC[base]:
                    return f"{base} of {len(args)} item types"
                return next((w for w in map(why, args) if w), "")
            return f"{ast.unparse(e.value)}[...]"
        return f"an expression ({type(e).__name__})"

    def union(members):
        flat = []
        while members:
            m = members.pop()
            if isinstance(m, ast.BinOp) and isinstance(m.op, ast.BitOr):
                members += [m.left, m.right]
            elif not (isinstance(m, ast.Constant) and m.value is None):
                flat.append(m)
        if any(ast.unparse(m) == "str" for m in flat):  # (str | os.PathLike[str] is str)
            flat = [m for m in flat if not re.match(r"(os\.)?PathLike\b", ast.unparse(m))]
        if len({ast.unparse(m) for m in flat}) > 1:
            return "a union (Pystachy has T | None only)"
        return why(flat[0]) if flat else ""

    return why(e)


def module_names(tree):
    """{name: the line of its first module-level binding}, the classes the module defines, and the
    names it binds to a TypeVar."""
    bound, classes, typevars = {}, set(), set()
    for st in tree.body:
        names = []
        if isinstance(st, (ast.Import, ast.ImportFrom)):
            names = [(a.asname or a.name).split(".")[0] for a in st.names]
        elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [st.name]
            if isinstance(st, ast.ClassDef):
                classes.add(st.name)
        elif isinstance(st, (ast.Assign, ast.AnnAssign)):
            for t in st.targets if isinstance(st, ast.Assign) else [st.target]:
                names += [n.id for n in ast.walk(t) if isinstance(n, ast.Name)]
            f = st.value.func if isinstance(st.value, ast.Call) else None
            if f is not None and (f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else "") == "TypeVar":
                typevars.update(names)
        for n in names:
            bound.setdefault(n, st.lineno)
    return bound, classes, typevars


def at_def_time(ann, line, bound, own, cls):
    """ann as CPython can evaluate it where the def at line runs, with Self as cls: quoted whole
    where it names a class of the module (own) that is not bound by then (a quoted name inside a
    union would be a str | None, a TypeError), and None where it needs another name the module has
    not bound by then."""

    class Fix(ast.NodeTransformer):
        def visit_Name(self, n):
            return ast.Name(cls) if n.id == "Self" and cls else n

        def visit_Constant(self, n):  # (a forward reference: quoted again below where needed)
            return ast.parse(n.value, mode="eval").body if isinstance(n.value, str) else n

    e = Fix().visit(ast.parse(ann, mode="eval"))
    late = False
    for n in ast.walk(e):
        if isinstance(n, ast.Name) and n.id not in BUILTIN and (n.id == cls or bound.get(n.id, line) >= line):
            if n.id not in own:
                return None
            late = True
    return repr(ast.unparse(e)) if late else ast.unparse(e)


def returns_value(fn):
    """Whether fn's own body (not a nested def's or lambda's) returns a value other than None."""
    todo = list(fn.body)
    while todo:
        n = todo.pop()
        if isinstance(n, ast.Return) and n.value is not None and not (isinstance(n.value, ast.Constant) and n.value.value is None):
            return True
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            todo += list(ast.iter_child_nodes(n))
    return False


def functions(tree):
    return index(tree)[1]


def own_params(q, fn, in_class):
    """The sites of fn's parameters, but a method's self or cls."""
    a = fn.args
    ps = a.posonlyargs + a.args
    if in_class and ps and not any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in fn.decorator_list):
        ps = ps[1:]
    return [(q, "param", p.arg) for p in ps + a.kwonlyargs] + [(q, "param", "*" + p.arg) for p in (a.vararg, a.kwarg) if p]


def existing(src, classes):
    """{site: why} for the annotations src has that Pystachy does not support."""
    tree = ast.parse(src)
    fns = functions(tree)
    typevars = module_names(tree)[2]
    out = {}
    for site, ann in sites(src).items():
        if ann is not None:
            fn, cls = fns.get(site[0], (None, ""))
            why = unsupported(ann, classes, cls != "", site[1], fn.name if fn is not None and site[1] != "var" else "",
                              typevars)
            if why:
                out[site] = why
    return out


def decide(src, inferred, policy, classes):
    """The suggestions of one module to keep, {site: annotation}, and a row for each suggestion."""
    tree = ast.parse(src)
    before, after = sites(src), sites(inferred)
    bound, own, typevars = module_names(tree)
    nodes, fns = index(tree)
    rows, keep = [], {}
    for site, ann in after.items():
        if ann is None or site not in before or before[site] is not None:
            continue
        scope, kind, _ = site
        fn, cls = fns.get(scope, (None, ""))
        # where CPython evaluates it: a def's when the def runs, a module's or class body's variable's
        # at its statement, and a function's local variable's never
        line = fn.lineno if kind != "var" else 1 << 30 if fn is not None else nodes[site].lineno
        why = unsupported(ann, classes, cls != "", kind, fn.name if fn is not None else "", typevars)
        if not why and kind == "var" and scope and fn is None:
            why = "a class body's variable (an annotation makes a dataclass field)"
        if not why and kind == "param" and policy == "templates":
            why = "templates: parameters stay unannotated"
        written = None
        if not why:
            written = at_def_time(ann, line, bound, own, cls)
            if written is None:
                why = "needs a name the module has not bound where the def runs"
        row = {"site": list(site), "line": fn.lineno if fn is not None else 0, "pyrefly": ann, "kept": not why}
        if why:
            row["why"] = why
        else:
            keep[site] = written
            if written != ann:
                row["written"] = written
        rows.append(row)
    # a function with no unannotated parameter but self or cls returns None unless annotated
    for q, (fn, cls) in fns.items():
        ps = own_params(q, fn, cls != "")
        if not all(before.get(p) is not None or p in keep for p in ps):
            continue
        if before.get((q, "return", "")) is not None or (q, "return", "") in keep or not returns_value(fn):
            continue
        added = [p for p in ps if p in keep]
        for r in rows:
            if tuple(r["site"]) in added:
                del keep[tuple(r["site"])]
                r["kept"], r["why"] = False, "its def has no supported return type, so it stays a template"
                r.pop("written", None)
        if not added:
            rows.append({"site": [q, "return", ""], "line": fn.lineno, "pyrefly": after.get((q, "return", "")),
                         "kept": False, "blocker": True,
                         "why": "returns a value but has no return annotation, and no supported one from Pyrefly: "
                                "Pystachy reads it as returning None"})
    return keep, rows


# ---- infer --------------------------------------------------------------------------------------

def read(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        return f.read()


def modules(root):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d != "__pycache__")
        out += [os.path.relpath(os.path.join(dp, f), root) for f in sorted(fn) if f.endswith(".py")]
    return out


def run_pyrefly(exe, root, passes, params, imports):
    """pyrefly infer over root, in place; how many passes changed something."""
    try:
        got = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.split()
    except OSError:
        got = []
    if got[-1:] != [PYREFLY]:
        sys.exit(f"prepare_port.py: needs pyrefly {PYREFLY} (python3 -m pip install pyrefly=={PYREFLY}; "
                 f"--pyrefly EXE), found {' '.join(got) or 'none'} at {exe}")
    with open(os.path.join(root, "pyrefly.toml"), "w") as f:
        f.write(CONFIG)
    cmd = [exe, "infer", f"--parameter-types={'true' if params else 'false'}", "--return-types=true",
           "--containers=true", f"--imports={'true' if imports else 'false'}"]
    changed = 0
    for _ in range(passes):
        before = {m: read(os.path.join(root, m), "rb") for m in modules(root)}
        p = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        if p.returncode != 0:
            sys.exit(f"pyrefly infer failed:\n{p.stdout}{p.stderr}")
        if all(read(os.path.join(root, m), "rb") == b for m, b in before.items()):
            break
        changed += 1
    os.remove(os.path.join(root, "pyrefly.toml"))
    return changed


def infer(a):
    src, out = os.path.abspath(a.src), os.path.abspath(a.out)
    name = os.path.basename(src.rstrip("/"))
    if os.path.exists(out):
        sys.exit(f"{out}: exists")
    work, result = os.path.join(out, "pyrefly", name), os.path.join(out, name)
    for dst in (work, result):
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
    mods = modules(src) if os.path.isdir(src) else [""]
    texts = {m: read(os.path.join(src, m) if m else src) for m in mods}
    classes = {n.name for t in texts.values() for n in ast.walk(ast.parse(t)) if isinstance(n, ast.ClassDef)}
    # the annotations Pystachy does not support: blockers, or with --untype (a parameter's, a
    # return's) left out before Pyrefly runs, so that it may infer them again
    bad = {m: existing(t, classes) for m, t in texts.items()}
    base = dict(texts)
    untyped = a.untype and a.policy != "raw"
    # (not a variable's: a field's annotation makes it a dataclass field; nor __init__'s parameters,
    # which would make its class a class template, a choice of design: Parser(fn) of parsy)
    loose = {m: {s for s in bad[m] if s[1] != "var" and not (s[1] == "param" and re.sub(r"#\d+$", "", s[0]).endswith("__init__"))}
             for m in mods}
    if untyped:
        for m in mods:
            base[m] = edit(texts[m], {s: None for s in loose[m]})[0]
            with open(os.path.join(work, m) if m else work, "w", encoding="utf-8") as f:
                f.write(base[m])
    t0 = time.perf_counter()
    # (raw keeps the imports Pyrefly adds; the other policies write their own annotations, and no import)
    passes = run_pyrefly(a.pyrefly, os.path.dirname(work), a.passes, a.policy != "templates", a.policy == "raw")
    report = {"pyrefly": PYREFLY, "policy": a.policy, "untype": a.untype, "passes": passes,
              "pyrefly_s": round(time.perf_counter() - t0, 2), "modules": {}}
    patch = []
    for m in mods:
        text = texts[m]
        inferred = read(os.path.join(work, m) if m else work)
        nodes, old = defs(ast.parse(text)), sites(text)
        rows = [{"site": list(s), "line": nodes[s].lineno, "upstream": old[s], "why": why, "kept": False,
                 **({"untyped": True} if untyped and s in loose[m] else {"blocker": True})} for s, why in bad[m].items()]
        if a.policy == "raw":
            new = inferred
            rows += [{"site": list(s), "pyrefly": ann, "kept": True} for s, ann in sites(inferred).items()
                     if ann is not None and s in old and old[s] is None]
        else:
            keep, more = decide(base[m], inferred, a.policy, classes)
            new, skipped = edit(base[m], keep)
            rows += more + [{"site": list(s), "kept": False, "why": why} for s, why in skipped]
        with open(os.path.join(result, m) if m else result, "w", encoding="utf-8") as f:
            f.write(new)
        report["modules"][m or name] = rows
        rel = os.path.join(name, m) if m else name
        patch += difflib.unified_diff(text.splitlines(keepends=True), new.splitlines(keepends=True), "a/" + rel, "b/" + rel)
    with open(os.path.join(out, "prepare.patch"), "w", encoding="utf-8") as f:
        f.writelines(patch)
    with open(os.path.join(out, "report.json"), "w") as f:
        json.dump(report, f, indent=1)
    summary(report)


def summary(report):
    rows = [r for rs in report["modules"].values() for r in rs]
    sugg = [r for r in rows if r.get("pyrefly") and not r.get("blocker")]
    print(f"pyrefly {report['pyrefly']}: {report['passes']} pass(es) changed something, {report['pyrefly_s']} s; "
          f"policy {report['policy']}: kept {sum(1 for r in sugg if r['kept'])} of {len(sugg)} suggestions")
    for kind in ("param", "return", "var"):
        ks = [r for r in sugg if r["site"][1] == kind]
        if ks:
            print(f"  {kind:6} {sum(1 for r in ks if r['kept']):5} kept of {len(ks)}")

    def counts(title, rs):
        whys = {}
        for r in rs:
            w = re.sub(r"name \w+,", "name N,", r["why"])
            whys[w] = whys.get(w, 0) + 1
        for w, n in sorted(whys.items(), key=lambda x: -x[1]):
            print(f"  {title} {n:4}  {w}")

    counts("dropped", [r for r in sugg if not r["kept"]])
    counts("untyped", [r for r in rows if r.get("untyped")])
    blockers = [(m, r) for m, rs in report["modules"].items() for r in rs if r.get("blocker")]
    if blockers:
        print(f"  {len(blockers)} blocker(s): annotations Pystachy does not support, and defs it reads as returning None")
    for m, r in blockers:
        what = f"{r['site'][0]}()" if r["site"][1] != "var" else r["site"][2]
        if r["site"][1] == "param":
            what += f" parameter {r['site'][2]}"
        print(f"    {m}:{r['line']}: {what}: " + (f"{r['upstream']}: " if r.get("upstream") else "") + r["why"])


# ---- check --------------------------------------------------------------------------------------

def classify(err):
    """What a compile error asks of a port."""
    for name, pat in (("an annotation", r"annotate|without a return annotation|cannot infer the type|cannot infer what"),
                      ("an annotation Pystachy supports", r"unsupported type annotation|TypeVar"),
                      ("a module", r"module '[^']*' is not supported|unsupported module attribute"),
                      ("one type per value", r"expected \S+, got |may be None|None into|got None"),
                      ("a language feature", r"not supported")):
        if re.search(pat, err):
            return name
    return "other"


def run(cmd, env, stdin, timeout=900):
    t0 = time.perf_counter()
    with open(stdin) as fin:
        try:
            p = subprocess.run(cmd, env=env, stdin=fin, capture_output=True, text=True, errors="replace",
                               timeout=timeout, cwd=ROOT)
            out, err, code = p.stdout, p.stderr, p.returncode
        except subprocess.TimeoutExpired:
            out, err, code = "", "timeout", -1
    return out + f"[exit {code}]\n", err, round(time.perf_counter() - t0, 3)


def stats(prog, libpath):
    """[template specializations, IR lines] of prog, compiled by pystachy.py on CPython in this
    process (a child of check), or [-1, -1] if it does not compile."""
    sys.path.insert(0, ROOT)
    import pystachy
    sys.setrecursionlimit(pystachy.MAXNEST * 40)
    gens = []

    def compile_program(path, src, dirs):
        g = pystachy.Gen()
        gens.append(g)
        return g.program(pystachy.Loader(dirs).program(path, src))

    pystachy.SRC = prog
    dirs = [os.path.dirname(os.path.abspath(prog))] + libpath.split(":") + [os.path.join(ROOT, "lib")]
    try:
        with open(prog, encoding="latin-1") as f:
            ir = compile_program(prog, f.read(), dirs)
    except SystemExit:
        return [-1, -1]
    return [gens[0].template_instances, ir.count("\n")]


def check(a):
    lib = os.path.abspath(a.libpath)
    ref = os.path.abspath(a.ref) if a.ref else lib
    pys = ["./pystachy"] if os.path.exists(os.path.join(ROOT, "pystachy")) else [sys.executable, "pystachy.py"]
    rows = []
    for prog in map(os.path.abspath, a.workloads):
        stdin = prog[:-3] + ".in" if os.path.exists(prog[:-3] + ".in") else "/dev/null"
        row = {"workload": os.path.relpath(prog, ROOT)}
        env = dict(os.environ, PYTHONPATH=ref)
        env.pop("PYTHONUNBUFFERED", None)
        want, _, _ = run([sys.executable, prog, "a1", "a2"], env, stdin)
        if ref != lib:
            env["PYTHONPATH"] = lib
            row["cpython_same"] = run([sys.executable, prog, "a1", "a2"], env, stdin)[0] == want
        env = dict(os.environ, PYSTACHY_PATH=lib)
        got, err, row["jit_s"] = run([*pys, "run", prog, "a1", "a2"], env, stdin)
        errors = [x for x in err.splitlines() if ": error:" in x]
        row["jit"] = "compile error" if errors else "pass" if got == want else "differs"
        if errors:
            row["error"] = errors[0].replace(lib + "/", "")
            row["needs"] = classify(errors[0])
        if a.aot and not errors:
            fd, exe = tempfile.mkstemp()
            os.close(fd)
            _, err, row["aot_build_s"] = run([*pys, "build", prog, "-o", exe], env, "/dev/null")
            row["aot"] = "compile error"
            if ": error:" not in err and os.path.getsize(exe) > 0:
                row["aot_bytes"] = os.path.getsize(exe)
                row["aot"] = "pass" if run([exe, "a1", "a2"], dict(os.environ), stdin)[0] == want else "differs"
            os.remove(exe)
        if a.stats and not errors:
            p = subprocess.run([sys.executable, "-I", __file__, "_stats", prog, lib], capture_output=True, text=True)
            row["specializations"], row["ir_lines"] = json.loads(p.stdout.splitlines()[-1]) if p.returncode == 0 else [-1, -1]
        rows.append(row)
        print(f"{row['workload']}: " + ", ".join(f"{k} {v}" for k, v in row.items() if k != "workload"))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rows, f, indent=1)
    ok = all(r["jit"] == "pass" and r.get("aot", "pass") == "pass" and r.get("cpython_same", True) for r in rows)
    sys.exit(0 if ok else 1)


def main():
    if sys.argv[1:2] == ["_stats"]:  # (check's child)
        print(json.dumps(stats(sys.argv[2], sys.argv[3])))
        return
    ap = argparse.ArgumentParser(prog="prepare_port.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("infer")
    p.add_argument("--policy", choices=("templates", "signatures", "raw"), default="templates")
    p.add_argument("--passes", type=int, default=3)
    p.add_argument("--untype", action="store_true")
    p.add_argument("--pyrefly", default=shutil.which("pyrefly") or "pyrefly")
    p.add_argument("src")
    p.add_argument("out")
    p = sub.add_parser("check")
    p.add_argument("--ref")
    p.add_argument("--aot", action="store_true")
    p.add_argument("--stats", action="store_true")
    p.add_argument("--json")
    p.add_argument("libpath")
    p.add_argument("workloads", nargs="+")
    a = ap.parse_args()
    (infer if a.cmd == "infer" else check)(a)


if __name__ == "__main__":
    main()
