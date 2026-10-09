"""Feature census: which of the Python features Pystachy cannot compile does each function use?

usage: python3 -I tools/census.py [PREFIX=]ROOT ... [--json OUT.json]
The census reads source with the ast module only (it never imports what it scans). Each
module-level function, each method, each class and each module's top-level code is a unit; a
unit's blockers are the syntactic features in it that Pystachy rejects or treats specially
(the names are explained in docs/stdlib.md). It is an upper bound on what compiles: a unit
without blockers can still fail type checking. docs/stdlib.md reports a run over CPython 3.13.
"""
import ast
import builtins
import json
import os
import sys

# pystachy.py's MODULES, and typing_extensions, which the compiler reads as typing
SUPPORTED_MODULES = {"sys", "os", "os.path", "math", "tempfile", "typing", "dataclasses", "__future__", "builtins", "time",
                     "errno", "typing_extensions"}
DYN = {"isinstance", "issubclass", "type", "getattr", "setattr", "hasattr", "delattr", "callable", "id", "hash",
       "vars", "dir", "globals", "locals", "eval", "exec", "compile", "super", "iter", "next", "object", "__import__",
       "memoryview", "bytearray", "bytes", "property", "staticmethod", "classmethod", "frozenset", "set", "map",
       "filter", "format", "hex", "oct", "bin", "complex", "slice", "tuple", "breakpoint", "help", "aiter", "anext"}
SUPPORTED_BUILTINS = {"print", "len", "str", "repr", "ascii", "int", "float", "bool", "ord", "chr", "abs", "min", "max",
                      "sum", "sorted", "list", "dict", "round", "divmod", "pow", "any", "all", "input", "open", "range",
                      "enumerate", "zip", "reversed", "exit", "quit"}
STR_METHODS = {"join", "split", "strip", "lstrip", "rstrip", "startswith", "endswith", "find", "rfind", "index", "rindex",
               "count", "replace", "upper", "lower", "isdigit", "isalpha", "isalnum", "isspace", "isupper", "islower",
               "ljust", "rjust", "append", "pop", "insert", "extend", "remove", "reverse", "copy", "clear", "get",
               "setdefault", "keys", "values", "items", "read", "readline", "readlines", "write", "writelines", "close",
               "flush", "hex", "is_integer", "sort"}
CONSUMERS = {"sum", "min", "max", "sorted", "list", "any", "all", "join", "extend"}


class Unit:
    def __init__(self, module, name, kind, line, nlines):
        self.module = module
        self.name = name
        self.kind = kind
        self.line = line
        self.nlines = nlines
        self.blockers = {}
        self.notes = {}

    def add(self, k, why=""):
        self.blockers[k] = self.blockers.get(k, 0) + 1

    def note(self, k):
        self.notes[k] = self.notes.get(k, 0) + 1


class Scan(ast.NodeVisitor):
    def __init__(self, u, params, method):
        self.u = u
        self.params = params
        self.method = method
        self.depth = 0

    def visit_Try(self, n):
        self.u.add("try")
        self.generic_visit(n)

    visit_TryStar = visit_Try

    def visit_Yield(self, n):
        self.u.add("yield")
        self.generic_visit(n)

    visit_YieldFrom = visit_Yield

    def visit_Lambda(self, n):
        self.u.add("lambda")
        self.generic_visit(n)

    def visit_FunctionDef(self, n):
        self.u.add("nested_def")
        self.generic_visit(n)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, n):
        self.u.add("nested_def")
        self.generic_visit(n)

    def visit_Nonlocal(self, n):
        self.u.add("nonlocal")

    def visit_Starred(self, n):
        self.u.add("starred")
        self.generic_visit(n)

    def visit_Set(self, n):
        self.u.add("set")
        self.generic_visit(n)

    def visit_SetComp(self, n):
        self.u.add("set")
        self.generic_visit(n)

    def visit_DictComp(self, n):
        self.u.add("dictcomp")
        self.generic_visit(n)

    def comp(self, n):
        if len(n.generators) > 1 or any(len(g.ifs) > 1 for g in n.generators):
            self.u.add("nested_comp")
        self.generic_visit(n)

    visit_ListComp = comp

    def visit_GeneratorExp(self, n):
        self.comp(n)

    def visit_For(self, n):
        if n.orelse:
            self.u.add("loop_else")
        self.generic_visit(n)

    def visit_While(self, n):
        if n.orelse:
            self.u.add("loop_else")
        self.generic_visit(n)

    visit_AsyncFor = visit_For

    def visit_Slice(self, n):
        if n.step is not None:
            self.u.add("slice_step")
        self.generic_visit(n)

    def visit_With(self, n):
        for it in n.items:
            e = it.context_expr
            if not (isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == "open"):
                self.u.add("with_nonfile")
        self.generic_visit(n)

    def visit_AsyncWith(self, n):
        self.u.add("async")
        self.generic_visit(n)

    def visit_Await(self, n):
        self.u.add("async")
        self.generic_visit(n)

    def visit_NamedExpr(self, n):
        self.u.add("walrus")
        self.generic_visit(n)

    def visit_Match(self, n):
        self.u.add("match")
        self.generic_visit(n)

    def visit_Constant(self, n):
        if isinstance(n.value, bytes):
            self.u.add("bytes")
        elif isinstance(n.value, complex):
            self.u.add("complex")
        elif isinstance(n.value, str) and any(ord(c) > 127 for c in n.value):
            self.u.note("non_ascii_str")
        elif isinstance(n.value, int) and not isinstance(n.value, bool) and abs(n.value) >= 2**63:
            self.u.add("bigint_literal")

    def visit_BinOp(self, n):
        if isinstance(n.op, ast.Mod) and (isinstance(n.left, (ast.Constant, ast.JoinedStr)) and isinstance(getattr(n.left, "value", ""), str)):
            self.u.add("percent_format")
        if isinstance(n.op, ast.MatMult):
            self.u.add("matmul")
        self.generic_visit(n)

    def visit_Import(self, n):
        for a in n.names:
            if a.name not in SUPPORTED_MODULES:
                self.u.add("import_other")

    def visit_ImportFrom(self, n):
        if n.level or n.module not in SUPPORTED_MODULES:
            self.u.add("import_other")

    def visit_Delete(self, n):
        for t in n.targets:
            if not isinstance(t, ast.Subscript):
                self.u.add("del_name")
        self.generic_visit(n)

    def visit_Raise(self, n):
        e = n.exc
        if isinstance(e, ast.Call):
            e = e.func
        if e is not None and not (isinstance(e, ast.Name) and isinstance(getattr(builtins, e.id, None), type)):
            self.u.add("raise_custom")
        self.generic_visit(n)

    def visit_Call(self, n):
        f = n.func
        for kw in n.keywords:
            if kw.arg is None:
                self.u.add("star_call")
            elif kw.arg == "key":
                self.u.add("first_class_fn")
        if isinstance(f, ast.Name):
            if f.id in self.params:
                self.u.add("first_class_fn")
            elif f.id in DYN:
                self.u.add("dyn:" + f.id)
            elif f.id in ("map", "filter"):
                self.u.add("first_class_fn")
        elif isinstance(f, ast.Attribute):
            if f.attr == "format" and isinstance(f.value, ast.Constant):
                self.u.add("str_format")
            elif f.attr in ("encode", "decode"):
                self.u.add("bytes")
            elif isinstance(f.value, ast.Name) and f.value.id in ("self", "cls"):
                pass
            elif f.attr not in STR_METHODS and not (isinstance(f.value, ast.Name) and f.value.id in ("math", "os", "sys", "_os", "_sys")):
                self.u.note("method:" + f.attr)
        # a function name passed as an argument
        for a in n.args:
            if isinstance(a, ast.Name) and a.id in self.u_funcs:
                self.u.add("first_class_fn")
        self.generic_visit(n)

    def visit_Name(self, n):
        if n.id in ("globals", "locals", "__dict__"):
            self.u.add("dyn:" + n.id)


def none_default(args):
    ds = args.defaults
    names = [a.arg for a in args.posonlyargs + args.args]
    out = []
    for name, d in zip(names[len(names) - len(ds):], ds):
        if isinstance(d, ast.Constant) and d.value is None:
            out.append(name)
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        if isinstance(d, ast.Constant) and d.value is None:
            out.append(a.arg)
    return out


def scan_fn(mod, fn, cls, funcs):
    u = Unit(mod, (cls + "." if cls else "") + fn.name, "method" if cls else "function", fn.lineno,
             (fn.end_lineno or fn.lineno) - fn.lineno + 1)
    a = fn.args
    params = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
    if isinstance(fn, ast.AsyncFunctionDef):
        u.add("async")
    if a.vararg or a.kwarg:
        u.add("star_params")
    if a.kwonlyargs:
        u.add("kwonly_marker")
    if a.posonlyargs:
        u.add("posonly_marker")
    plist = a.posonlyargs + a.args + a.kwonlyargs
    static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in fn.decorator_list)
    if cls and plist and not static:
        plist = plist[1:]  # self or cls: a static method has neither
    if any(p.annotation is None for p in plist):
        u.add("unannotated")
    if none_default(a):
        u.add("none_default")
    for d in fn.decorator_list:
        dn = d.id if isinstance(d, ast.Name) else (d.attr if isinstance(d, ast.Attribute) else "call")
        if cls and dn in ("staticmethod", "classmethod", "property"):
            u.add("deco:" + dn)
        elif dn != "dataclass":
            u.add("decorator")
    s = Scan(u, set(params), bool(cls))
    s.u_funcs = funcs
    for st in fn.body:
        s.visit(st)
    return u


def scan_module(path, modname):
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception as e:
        return None, [], str(e)
    funcs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    units = []
    top = Unit(modname, "<module>", "module", 1, len(src.splitlines()))
    s = Scan(top, set(), False)
    s.u_funcs = funcs
    for st in tree.body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            units.append(scan_fn(modname, st, "", funcs))
            for d in st.decorator_list:
                s.visit(d)
            for d in st.args.defaults:
                s.visit(d)
        elif isinstance(st, ast.ClassDef):
            cu = Unit(modname, st.name, "class", st.lineno, (st.end_lineno or st.lineno) - st.lineno + 1)
            if st.bases or st.keywords:
                bn = [ast.unparse(b) for b in st.bases]
                if bn != ["object"] or st.keywords:
                    cu.add("inherit")
            for d in st.decorator_list:
                dn = d.id if isinstance(d, ast.Name) else (d.attr if isinstance(d, ast.Attribute) else "call")
                if dn != "dataclass":
                    cu.add("class_decorator")
            cs = Scan(cu, set(), False)
            cs.u_funcs = funcs
            for b in st.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    units.append(scan_fn(modname, b, st.name, funcs))
                elif isinstance(b, ast.AnnAssign) or (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant)) or isinstance(b, ast.Pass):
                    if isinstance(b, ast.AnnAssign) and b.value is not None:
                        cs.visit(b.value)
                else:
                    cu.add("class_body_stmt")
                    cs.visit(b)
            units.append(cu)
        elif isinstance(st, ast.If) and ast.unparse(st.test) in ("__name__ == '__main__'", '__name__ == "__main__"'):
            top.note("main_guard")
        elif isinstance(st, ast.Try) and all(isinstance(x, (ast.Import, ast.ImportFrom)) for x in st.body) and \
                all(h.type is not None and ast.unparse(h.type) in ("ImportError", "ModuleNotFoundError") for h in st.handlers):
            top.note("accel_import")
        else:
            s.visit(st)
    return top, units, ""


def walk(root, prefix):
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in ("test", "tests", "__pycache__", "idlelib", "tkinter", "turtledemo",
                                                  "site-packages", "dist-packages", "lib2to3", "ensurepip", "venv"))
        for f in sorted(fn):
            if f.endswith(".py"):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, root)[:-3].replace(os.sep, ".")
                if rel.endswith(".__init__"):
                    rel = rel[:-9]
                out.append((p, prefix + rel))
    return out


def main():
    roots = [a for a in sys.argv[1:] if not a.startswith("--")]
    js = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else ""
    if js in roots:
        roots.remove(js)
    rows = []
    for r in roots:
        prefix = ""
        if "=" in r:
            prefix, r = r.split("=", 1)
            prefix += ":"
        for p, m in walk(r, prefix):
            top, units, err = scan_module(p, m)
            if top is None:
                rows.append({"module": m, "error": err})
                continue
            for u in [top] + units:
                rows.append({"module": u.module, "name": u.name, "kind": u.kind, "line": u.line, "lines": u.nlines,
                             "blockers": u.blockers, "notes": u.notes})
    if js:
        json.dump(rows, open(js, "w"), indent=0)
    print(len(rows), "units")


main()
