"""How compile time grows with the size of the program: generated programs, timed IR generation.

usage: python3 tools/scaling.py [-c LABEL=COMMAND]... [-s SHAPE,...] [-n N,...] [-r RUNS] [--ops] [--keep DIR]
       (defaults: the checkout's -c "hosted=python3 pystachy.py" -c "native=./pystachy", every shape,
       -n 1000,2000,4000, -r 3)
Each shape is a family of programs whose size grows with N:
  funcs    N small annotated functions and 10 global variables
  globals  N global variables and 10 functions
  both     N functions and N global variables (function i reads global i)
  long     one function of N if statements, each assigning a new local variable
  top      N if statements in module code, each assigning a new global variable
  classes  N classes, each with an __init__ that sets two fields and a method
  modules  N imported modules, each with three functions and three globals
  fields   one class whose __init__ sets N fields and a method that reads them all
  calls    an imported module of N functions, each calling the one before it
  imports  N modules, each importing the one before it (the program imports them in order)
  breaks   one while True loop of N breaks, each after an assignment to a new variable
Each cell is the median of RUNS runs of "COMMAND ir main.py -o /dev/null" in seconds, startup
included; "x" is its growth from the previous N (2.0 is linear when N doubles, 4.0 quadratic).
--ops adds, for each COMMAND that runs a .py file (the CPython-hosted compiler), the number of
the compiler's source lines executed in all ("lines") and inside Gen.flow_program, the
definite-assignment pass ("flow"): counts that do not depend on the machine (sys.monitoring
counts them, so --ops needs Python 3.12 or later).
A compiler that fails shows "failed", and its last line of stderr follows the table.
--keep DIR writes the generated programs to DIR/SHAPE-N/ instead of a temporary directory.
"""
import json
import os
import shlex
import statistics
import subprocess
import sys
import tempfile
import time


def funcs(n):
    src = [f"g{j} = {j}" for j in range(10)]
    for i in range(n):
        src += [f"def f{i}(x: int) -> int:", f"    if x > g{i % 10}:", f"        return x + {i}", "    return x - 1"]
    src.append(f"print(f0(1) + f{n - 1}(20))")
    return {"main.py": src}


def globals_(n):
    src = [f"g{j} = {j}" for j in range(n)]
    for i in range(10):
        src += [f"def f{i}(x: int) -> int:", f"    if x > g{i * n // 10}:", f"        return x + {i}", "    return x - 1"]
    src.append(f"print(f0(1) + f9(20) + g{n - 1})")
    return {"main.py": src}


def both(n):
    src = [f"g{j} = {j}" for j in range(n)]
    for i in range(n):
        src += [f"def f{i}(x: int) -> int:", f"    if x > g{i}:", f"        return x + {i}", "    return x - 1"]
    src.append(f"print(f0(1) + f{n - 1}(20))")
    return {"main.py": src}


def long(n):
    src = ["def big(x: int) -> int:", "    v0 = x"]
    for i in range(1, n):
        src += [f"    if v{i - 1} > {i % 7}:", f"        v{i} = v{i - 1} - 1", "    else:", f"        v{i} = v{i - 1} + 2"]
    src += [f"    return v{n - 1}", "print(big(5))"]
    return {"main.py": src}


def top(n):
    src = ["v0 = 5"]
    for i in range(1, n):
        src += [f"if v{i - 1} > {i % 7}:", f"    v{i} = v{i - 1} - 1", "else:", f"    v{i} = v{i - 1} + 2"]
    src.append(f"print(v{n - 1})")
    return {"main.py": src}


def classes(n):
    src = []
    for i in range(n):
        src += [f"class C{i}:", "    def __init__(self, a: int):", "        self.a = a", f"        self.b = a + {i}",
                "    def get(self) -> int:", "        return self.a + self.b"]
    src.append(f"print(C0(1).get() + C{n - 1}(2).get())")
    return {"main.py": src}


def modules(n):
    out = {"main.py": [f"import m{i}" for i in range(n)] + [f"print(m0.f0(1) + m{n - 1}.f2(2))"]}
    for i in range(n):
        src = [f"k{j} = {i + j}" for j in range(3)]
        for j in range(3):
            src += [f"def f{j}(x: int) -> int:", f"    if x > k{j}:", f"        return x + {j}", "    return x - k0"]
        out[f"m{i}.py"] = src
    return out


def fields(n):
    src = ["class K:", "    def __init__(self, a: int):"] + [f"        self.f{i} = a + {i}" for i in range(n)]
    src += ["    def total(self) -> int:", "        t = 0"] + [f"        t += self.f{i}" for i in range(n)]
    src += ["        return t", "print(K(1).total())"]
    return {"main.py": src}


def calls(n):
    src = ["def f0(x: int) -> int:", "    return x"]
    for i in range(1, n):
        src += [f"def f{i}(x: int) -> int:", f"    return f{i - 1}(x) + 1"]
    return {"main.py": ["import lib", f"print(lib.f{n - 1}(1))"], "lib.py": src}


def imports(n):
    out = {"main.py": [f"import m{i}" for i in range(n)] + [f"print(m{n - 1}.f(1))"]}
    for i in range(n):
        out[f"m{i}.py"] = ([f"import m{i - 1}"] if i > 0 else []) + [f"k = {i}", "def f(x: int) -> int:", "    return x + k"]
    return out


def breaks(n):
    src = ["def big(x: int) -> int:", "    v0 = x", "    while True:"]
    for i in range(1, n):
        src += [f"        v{i} = v{i - 1} + 1", f"        if v{i} > {i % 7}:", "            break"]
    src += ["        break", "    return v0", "print(big(5))"]
    return {"main.py": src}


SHAPES = {"funcs": funcs, "globals": globals_, "both": both, "long": long, "top": top, "classes": classes, "modules": modules,
          "fields": fields, "calls": calls, "imports": imports, "breaks": breaks}


def write(d, files):
    os.makedirs(d, exist_ok=True)
    for name, src in files.items():
        with open(os.path.join(d, name), "w") as f:
            f.write("\n".join(src) + "\n")
    return os.path.join(d, "main.py")


def failed(p):
    lines = p.stderr.strip().splitlines()
    return lines[-1] if lines else f"exit status {p.returncode}"


def timed(cmd, prog, runs):
    # the median time in seconds, or why the compiler failed
    ts = []
    for _ in range(runs):
        t = time.perf_counter()
        p = subprocess.run(cmd + ["ir", prog, "-o", os.devnull], capture_output=True, text=True)
        ts.append(time.perf_counter() - t)
        if p.returncode != 0:
            return failed(p)
    return statistics.median(ts)


def ops(cmd, prog):
    # the hosted compiler run under count(): its counts come back in a temporary file
    script = next(a for a in cmd if a.endswith(".py"))
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--count", f.name, script, "ir", prog, "-o", os.devnull],
                           capture_output=True, text=True)
        if p.returncode != 0:
            return failed(p)
        return json.load(open(f.name))


def count(out, script, args):
    # run the compiler script with args, counting its executed lines (all, and inside flow_program)
    with open(script) as f:
        code = compile(f.read(), script, "exec")
    flow = []
    todo = [code]
    while todo:
        c = todo.pop()
        if c.co_qualname == "Gen.flow_program":
            flow.append(c)
        todo += [k for k in c.co_consts if hasattr(k, "co_code")]
    mon = sys.monitoring
    tool = mon.PROFILER_ID
    mon.use_tool_id(tool, "scaling")
    n = {"lines": 0, "flow": 0}
    depth = [0]

    def line(c, _):
        if c.co_filename != script:
            return mon.DISABLE
        n["lines"] += 1
        if depth[0] > 0:
            n["flow"] += 1

    def enter(*_):
        depth[0] += 1

    def leave(*_):
        depth[0] -= 1

    mon.register_callback(tool, mon.events.LINE, line)
    mon.register_callback(tool, mon.events.PY_START, enter)
    mon.register_callback(tool, mon.events.PY_RETURN, leave)
    for c in flow:
        mon.set_local_events(tool, c, mon.events.PY_START | mon.events.PY_RETURN)
    mon.set_events(tool, mon.events.LINE)
    sys.argv = [script] + args
    try:
        exec(code, {"__name__": "__main__", "__file__": script})
    finally:
        mon.set_events(tool, 0)
        with open(out, "w") as f:
            json.dump(n, f)


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["--count"]:
        return count(argv[1], argv[2], argv[3:])
    comps, shapes, sizes, runs, want_ops, keep = [], list(SHAPES), [1000, 2000, 4000], 3, False, ""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--ops":
            want_ops = True
            i += 1
            continue
        if i + 1 >= len(argv):
            sys.exit(__doc__)
        v = argv[i + 1]
        if a == "-c":
            label, _, cmd = v.partition("=")
            comps.append((label, shlex.split(cmd)))
        elif a == "-s":
            shapes = v.split(",")
        elif a == "-n":
            sizes = [int(x) for x in v.split(",")]
        elif a == "-r":
            runs = int(v)
        elif a == "--keep":
            keep = v
        else:
            sys.exit(__doc__)
        i += 2
    for s in shapes:
        if s not in SHAPES:
            sys.exit(f"unknown shape {s}: one of {', '.join(SHAPES)}")
    if not comps:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        comps = [("hosted", [sys.executable, os.path.join(root, "pystachy.py")]), ("native", [os.path.join(root, "pystachy")])]
    cols = []
    for label, cmd in comps:
        cols.append((label, cmd, False))
        if want_ops and any(a.endswith(".py") for a in cmd):
            cols.append((label, cmd, True))
    head = "| shape | N |"
    rule = "| --- | ---: |"
    for label, _, isops in cols:
        head += f" {label} lines | x | flow | x |" if isops else f" {label} s | x |"
        rule += " ---: | ---: | ---: | ---: |" if isops else " ---: | ---: |"
    print(head)
    print(rule, flush=True)
    errors = {}
    with tempfile.TemporaryDirectory() as tmp:
        for s in shapes:
            prev = {}
            for n in sizes:
                prog = write(os.path.join(keep or tmp, f"{s}-{n}"), SHAPES[s](n))
                row = f"| {s} | {n} |"
                for k, (label, cmd, isops) in enumerate(cols):
                    r = ops(cmd, prog) if isops else timed(cmd, prog, runs)
                    if isinstance(r, str):
                        errors[(label, s)] = f"{label} on {s} {n}: {r}"
                        row += " failed | | | |" if isops else " failed | |"
                        prev.pop(k, None)
                        continue
                    vals = [r["lines"], r["flow"]] if isops else [r]
                    for j, v in enumerate(vals):
                        grow = f"{v / prev[k][j]:.1f}" if k in prev and prev[k][j] > 0 else ""
                        row += f" {v} | {grow} |" if isops else f" {v:.3f} | {grow} |"
                    prev[k] = vals
                print(row, flush=True)
    for e in errors.values():
        print(e)


if __name__ == "__main__":
    main()
