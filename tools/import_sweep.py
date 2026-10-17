"""Try to compile 'import M' for every module of a Python standard library with Pystachy.

usage: python3 tools/import_sweep.py [-j N] [--metadata META.json] [COMPILER] [LIBDIR] [OUT.json]
       (defaults: ./pystachy, the running CPython's stdlib directory, build/import-sweep.json)
       python3 tools/import_sweep.py --overlay [COMPILER] LIBDIR DIR
       python3 tools/import_sweep.py --stubs [-j N] [--only NAME,...] [LIBDIR] [OUT.json]
Each module is compiled (pystachy ir) in a program of its own, with LIBDIR on PYSTACHY_PATH; the
JSON maps each module to "OK", the compiler's error or a timeout, and a summary groups the errors.
-j runs N compilations at a time (default: the number of CPUs).
--metadata writes a separate provenance/counts JSON; the result JSON format is unchanged.
An import result means compilation to IR, not execution or full module compatibility.

PYSTACHY_PATH comes before the lib/ beside the compiler, so LIBDIR's own re, heapq, functools ...
would hide the modules lib/ has in their place. PYSTACHY_PATH is therefore a directory of symbolic
links to the entries of LIBDIR, less the modules and packages whose names lib/ has, and the sweep
leaves those out (the JSON names lib/'s module that replaces each). --overlay makes that directory
as DIR, for 'PYSTACHY_PATH=DIR pystachy run prog.py' (DIR's symbolic links are made anew).

--stubs measures what the modules built into CPython that Pystachy lacks keep from importing: it
stands a stub in for each of them that some module imports without a fallback (outside a try
statement whose except clause for ImportError goes on), or for those --only names. A stub binds
the names the running CPython's module has: its functions, which raise NotImplementedError, its
classes, its exception classes and its constants. The sweep then compiles with this checkout's
CPython-hosted compiler, whose list of such modules leaves the stubs' names out, and reports the
stubs each importing module needs: a module that needs only one stub would import once Pystachy
had that module, as far as its import goes.
"""
import argparse
import ast
import builtins
import collections
import concurrent.futures
import hashlib
import importlib
import json
import math
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
import time

TIMEOUT = 120  # seconds per module
STUB_TIMEOUT = 600  # (the CPython-hosted compiler is slower)
SKIP = ("test", "tests", "idlelib", "tkinter", "turtledemo", "site-packages", "dist-packages", "lib2to3", "ensurepip", "venv", "__pycache__")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the CPython-hosted compiler, without the names of PYSTACHY_SWEEP_STUBS among the modules built into
# CPython, which it would not load from a file
HOSTED = """import os, sys
sys.path.insert(0, os.environ["PYSTACHY_SWEEP_ROOT"])
from src.pystachy_compiler import specs
for n in os.environ["PYSTACHY_SWEEP_STUBS"].split():
    specs.CBUILTIN.pop(n, None)
sys.argv[0] = os.path.join(os.environ["PYSTACHY_SWEEP_ROOT"], "pystachy.py")
from src.pystachy_compiler.driver import main
main()
"""


def modules(lib):
    out = []
    for dp, dn, fn in os.walk(lib):
        dn[:] = sorted(d for d in dn if d not in SKIP and not d.startswith("."))
        for f in sorted(fn):
            if not f.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), lib)[:-3].replace(os.sep, ".")
            if rel.endswith(".__init__"):
                rel = rel[:-9]
            if rel.endswith("__main__") or rel.startswith("__") or "-" in rel:
                continue
            out.append(rel)
    return out


def home_of(pys):
    # the compiler's home, found as it finds it
    home = os.getenv("PYSTACHY_HOME", "")
    if home == "":
        home = os.path.dirname(pys)
        if not os.path.exists(os.path.join(home, "runtime.c")):
            home = os.path.dirname(home)
    return home


def ported(pys):
    # the modules and packages of the lib/ beside the compiler
    lib = os.path.join(home_of(pys), "lib")
    names = set()
    for e in os.listdir(lib) if os.path.isdir(lib) else []:
        if e.endswith(".py"):
            names.add(e[:-3])
        elif os.path.exists(os.path.join(lib, e, "__init__.py")):
            names.add(e)
    return names


def overlay(lib, names, out):
    # out: a symbolic link to each entry of lib, less the modules and packages called names
    os.makedirs(out, exist_ok=True)
    for e in os.listdir(out):
        if not os.path.islink(os.path.join(out, e)):
            sys.exit(f"{out} holds {e}, which is not a symbolic link")
        os.unlink(os.path.join(out, e))
    for e in sorted(os.listdir(lib)):
        if (e[:-3] if e.endswith(".py") else e) not in names:
            os.symlink(os.path.join(os.path.abspath(lib), e), os.path.join(out, e))


def fallback(t):
    # whether try statement t goes on where its body raises ImportError: an except clause that
    # catches it and does more than raise another exception
    for h in t.handlers:
        caught = [x.id for x in (h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]) if isinstance(x, ast.Name)] if h.type else []
        catches = h.type is None or {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"} & set(caught)
        if catches and not (len(h.body) == 1 and isinstance(h.body[0], ast.Raise)):
            return True
    return False


def needed(files, names):
    # files maps module names to their files. The modules of names that each module imports outside
    # a try statement with a fallback for ImportError; and those of all of them, each with the names
    # such from-imports take from it (None: all, for an import of the module or of *)
    take = {}
    by = {}

    def visit(node, guarded, mine):
        for child in ast.iter_child_nodes(node):
            g = guarded or (isinstance(node, ast.Try) and child in node.body and fallback(node))
            if isinstance(child, ast.Import) and not g:
                for a in child.names:
                    if a.name.split(".")[0] in names:
                        take[a.name.split(".")[0]] = None
                        mine.add(a.name.split(".")[0])
            elif isinstance(child, ast.ImportFrom) and not g and child.level == 0 and child.module:
                m = child.module.split(".")[0]
                if m in names:
                    mine.add(m)
                    if m not in take or take[m] is not None:
                        taken = [a.name for a in child.names]
                        take[m] = None if "*" in taken or m != child.module else take.get(m, set()) | set(taken)
            visit(child, g, mine)

    for m, f in files.items():
        try:
            with open(f, encoding="utf-8") as src:
                tree = ast.parse(src.read())
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            continue
        by[m] = set()
        visit(tree, False, by[m])
    return take, by


def literal(v):
    if isinstance(v, bool) or v is None or isinstance(v, (str, bytes)):
        return True
    if isinstance(v, int):
        return -2**63 <= v < 2**63
    if isinstance(v, float):
        return math.isfinite(v)
    if isinstance(v, (tuple, frozenset)):
        return all(literal(x) for x in v) and type(v) in (tuple, frozenset)
    return False


def stub(name, only):
    # the source of a stub of the module called name, as the running CPython has it: of the names
    # in only, or of all its names (only None)
    m = importlib.import_module(name)
    out = [f'"""A stub of {name} (tools/import_sweep.py --stubs): its functions raise NotImplementedError."""']
    for a in sorted(dir(m)):
        if a.startswith("__") or (only is not None and a not in only):
            continue
        v = getattr(m, a)
        if isinstance(v, type) and issubclass(v, BaseException):
            # (also an alias of a builtin exception class, as _thread.error is RuntimeError, which
            # Pystachy has no value of)
            base = next(b for b in v.__mro__[int(getattr(builtins, v.__name__, None) is not v):] if getattr(builtins, b.__name__, None) is b)
            out.append(f"class {a}({base.__name__}):\n    pass")
        elif isinstance(v, type):
            out.append(f"class {a}:\n    def __init__(self, *args, **kwargs):\n        raise NotImplementedError('{name}.{a}')")
        elif callable(v):
            out.append(f"def {a}(*args, **kwargs):\n    raise NotImplementedError('{name}.{a}')")
        elif literal(v):
            out.append(f"{a} = {v!r}" if not isinstance(v, frozenset) else f"{a} = frozenset({tuple(sorted(v, key=repr))!r})")
    return "\n\n\n".join(out) + "\n"


def compile_one(cmd, env, d, m, timeout, stubs):
    # m's import program compiled in directory d: "OK", the error or a timeout; with stubs, also the
    # modules it loads, which the IR has the init functions of
    prog = os.path.join(d, "prog.py")
    ll = os.path.join(d, "prog.ll")
    with open(prog, "w") as f:
        f.write(f"import {m}\n")
    try:
        p = subprocess.run(cmd + ["ir", prog, "-o", ll if stubs else os.devnull], capture_output=True, text=True,
                           env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"timeout: no result after {timeout} s", []
    if p.returncode != 0:
        err = p.stderr.strip().splitlines()
        return (err[-1] if err else f"exit {p.returncode}"), []
    if not stubs:
        return "OK", []
    with open(ll) as f:
        return "OK", re.findall(r"^define internal void @init\.([^\s(]+)\(", f.read(), re.M)


def source_git(path):
    # This describes the selected source tree, not which source built a native compiler.
    def git(*args):
        return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True,
                              check=True, timeout=10).stdout.strip()

    try:
        return {"root": git("rev-parse", "--show-toplevel"), "revision": git("rev-parse", "HEAD"),
                "dirty": bool(git("status", "--porcelain", "--untracked-files=normal"))}
    except (OSError, subprocess.SubprocessError):
        return {"root": os.path.abspath(path), "revision": None, "dirty": None}


def compiler_sha256(path):
    if not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def counts(res, left):
    excluded = set(left)
    included = [v for m, v in res.items() if m not in excluded]
    ok = sum(v.startswith("OK") for v in included)
    timeout = sum(v.startswith("timeout:") for v in included)
    return {"total": len(res), "included": len(included), "excluded": len(excluded),
            "ok": ok, "error": len(included) - ok - timeout, "timeout": timeout,
            "ok_without_stubs": sum(v == "OK" for v in included)}


def write_json(path, value):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(value, f, indent=1, sort_keys=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--overlay"]:
        parser = argparse.ArgumentParser(usage="%(prog)s --overlay [COMPILER] LIBDIR DIR")
        parser.add_argument("args", nargs="*")
        args = parser.parse_args(argv[1:]).args
        if len(args) not in (2, 3):
            parser.error("--overlay requires [COMPILER] LIBDIR DIR")
        if not os.path.isdir(args[-2]):
            parser.error(f"stdlib directory does not exist: {args[-2]}")
        if os.path.realpath(args[-2]) == os.path.realpath(args[-1]):
            parser.error("overlay directory must differ from the stdlib directory")
        overlay(args[-2], ported(os.path.abspath(args[0] if len(args) == 3 else "./pystachy")), args[-1])
        return
    parser = argparse.ArgumentParser(usage="%(prog)s [--stubs [--only NAME,...]] [-j N] [--metadata META.json] [COMPILER] [LIBDIR] [OUT.json]")
    parser.add_argument("--stubs", action="store_true")
    parser.add_argument("--only", default=None)
    parser.add_argument("--metadata", help="write provenance and counts to this separate JSON file")
    parser.add_argument("-j", type=int, default=os.cpu_count() or 1)
    parser.add_argument("args", nargs="*")
    options = parser.parse_args(argv)
    if options.j < 1:
        parser.error("-j must be at least 1")
    if options.only is not None:
        if not options.stubs:
            parser.error("--only requires --stubs")
        if not all(n.isidentifier() for n in options.only.split(",")):
            parser.error("--only requires comma-separated module names")
    if len(options.args) > (2 if options.stubs else 3):
        parser.error("too many positional arguments")
    args = options.args
    if options.stubs:
        args = [os.path.join(ROOT, "pystachy.py")] + args
    pys = os.path.abspath(args[0] if len(args) > 0 else "./pystachy")
    lib = os.path.abspath(args[1] if len(args) > 1 else sysconfig.get_paths()["stdlib"])
    out = args[2] if len(args) > 2 else "build/import-sweep.json"
    if not os.path.isfile(pys):
        parser.error(f"compiler file does not exist: {pys}")
    if not options.stubs and not os.access(pys, os.X_OK):
        parser.error(f"compiler is not executable: {pys}")
    if not os.path.isdir(lib):
        parser.error(f"stdlib directory does not exist: {lib}")
    if not out or (options.metadata is not None and not options.metadata):
        parser.error("output paths must not be empty")
    for output_path in (out, options.metadata):
        if output_path is not None and (os.path.isdir(output_path) or os.path.realpath(output_path) == os.path.realpath(pys)):
            parser.error(f"output must be a file path different from the compiler: {output_path}")
    if options.metadata and os.path.realpath(out) == os.path.realpath(options.metadata):
        parser.error("--metadata must differ from the result JSON path")
    start = time.monotonic()
    metadata = None
    if options.metadata:
        metadata = {"schema_version": 1, "mode": "stubs" if options.stubs else "import",
                    "python": {"executable": sys.executable, "version": sys.version,
                               "implementation": sys.implementation.name},
                    "stdlib": lib,
                    "compiler": {"path": pys, "sha256": compiler_sha256(pys),
                                 "kind": "hosted_entrypoint" if options.stubs else "executable"},
                    "source_git": source_git(ROOT if options.stubs else home_of(pys)),
                    "source_git_caveat": "The selected source tree is not proof of which source built the compiler file.",
                    "scope": "Compilation of isolated imports to IR; no runtime or full module compatibility check.",
                    "workers": options.j, "result_path": os.path.abspath(out)}
    names = ported(pys)
    res = {}
    left = []
    todo = []
    for m in modules(lib):
        if m.split(".")[0] in names:
            res[m] = "left out: lib/ has " + m.split(".")[0]
            left.append(m)
        else:
            todo.append(m)
    stubs = []
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "path")
        overlay(lib, names, path)
        env = dict(os.environ, PYSTACHY_PATH=path)
        cmd = [pys]
        timeout = TIMEOUT
        if options.stubs:
            sys.path.insert(0, ROOT)
            from src.pystachy_compiler import specs
            missing = {n for n in specs.CBUILTIN if n not in getattr(specs, "STANDINS", {})}
            if options.only is not None and set(options.only.split(",")) - missing:
                parser.error("--only contains modules not eligible for stubbing: " +
                             ", ".join(sorted(set(options.only.split(",")) - missing)))
            files = {}
            for m in todo:
                f = os.path.join(lib, m.replace(".", os.sep))
                files[m] = f + ".py" if os.path.exists(f + ".py") else os.path.join(f, "__init__.py")
            libdir = os.path.join(home_of(pys), "lib")
            for dp, dn, fn in os.walk(libdir):
                for f in fn:
                    if f.endswith(".py"):
                        m = os.path.relpath(os.path.join(dp, f), libdir)[:-3].replace(os.sep, ".")
                        files[m[:-9] if m.endswith(".__init__") else m] = os.path.join(dp, f)
            take, by = needed(files, missing)
            stubs = sorted(set(options.only.split(",")) & missing) if options.only else sorted(take)
            os.makedirs(os.path.join(d, "stubs"))
            for s in stubs:
                with open(os.path.join(d, "stubs", s + ".py"), "w") as f:
                    f.write(stub(s, None if options.only else take[s]))
            env = dict(env, PYSTACHY_PATH=os.path.join(d, "stubs") + ":" + path, PYSTACHY_SWEEP_ROOT=ROOT,
                       PYSTACHY_SWEEP_STUBS=" ".join(stubs))
            cmd = [sys.executable, "-c", HOSTED]
            timeout = STUB_TIMEOUT
            print(f"stubs for {len(stubs)} modules built into CPython: {' '.join(stubs)}\n")
        with concurrent.futures.ThreadPoolExecutor(options.j) as pool:
            jobs = {}
            for i, m in enumerate(todo):
                os.makedirs(os.path.join(d, f"job{i}"))
                jobs[m] = pool.submit(compile_one, cmd, env, os.path.join(d, f"job{i}"), m, timeout, stubs)
            for m in todo:
                text, loaded = jobs[m].result()
                # (the stubs it needs: those that a module it loads imports without a fallback)
                used = sorted({s for x in loaded for s in by.get(x, ())} & set(stubs)) if stubs else []
                res[m] = f"OK (stubs: {' '.join(used)})" if used else text.replace(path + "/", lib + "/").replace(d + "/", "")
    write_json(out, res)
    if metadata is not None:
        metadata.update({"counts": counts(res, left), "duration_s": time.monotonic() - start,
                         "timeout_s": timeout, "stubs": stubs,
                         "overlay": {"policy": "Exclude top-level names supplied by the compiler home lib/; prefer those ports.",
                                     "compiler_home": os.path.abspath(home_of(pys)),
                                     "ported_names": sorted(names), "excluded_modules": sorted(left),
                                     "skipped_directories": list(SKIP),
                                     "module_filter": "Python .py files except __main__, top-level __* names and names containing '-'."}})
        write_json(options.metadata, metadata)
    ok = sorted(m for m, v in res.items() if v.startswith("OK"))
    print(f"{len(ok)} of {len(res) - len(left)} modules import{' with the stubs' if stubs else ''}: {' '.join(ok)}\n")
    if left:
        print(f"{len(left)} left out, as lib/ has {', '.join(sorted(names & {m.split('.')[0] for m in left}))}: {' '.join(sorted(left))}\n")
    if stubs:
        need = {m: v[len("OK (stubs: "):-1].split() for m, v in res.items() if v.startswith("OK (stubs: ")}
        print(f"{len(ok) - len(need)} of them need no stub. The stubs the others need (modules needing it; needing only it):")
        rows = [(s, sum(s in n for n in need.values()), sum(n == [s] for n in need.values())) for s in stubs]
        for s, total, alone in sorted(rows, key=lambda r: (-r[2], -r[1], r[0])):
            if total:
                print(f"{total:5} {alone:5}  {s}")
        print()
    why = collections.Counter()
    for m, v in res.items():
        if not v.startswith("OK") and m not in left:
            msg = v.split("error: ", 1)[-1]
            if msg.startswith("timeout: "):
                msg = "timeout"
            if "is not supported: it is not a builtin module" in msg or "is not supported: it is built into CPython" in msg:
                msg = "imports the missing module " + msg.split("'")[1]
            why[msg[:100]] += 1
    for k, n in why.most_common(30):
        print(f"{n:5}  {k}")


if __name__ == "__main__":
    main()
