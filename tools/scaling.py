"""How compile time grows with the size of the program: generated programs, timed IR generation.

usage: python3 tools/scaling.py [-c LABEL=COMMAND]... [-s SHAPE,...] [-n N,...] [-r RUNS] [--ops] [--check] [--keep DIR]
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
  exits    one while True loop of N ifs, each breaking after an assignment to a new variable,
           with another new variable assigned before each if
  elifs    one function of an elif chain of N / 10 branches, whose else block assigns N new
           variables (N / 10: the CPython-hosted compiler's recursion stops at about 490)
  topelifs an elif chain of N / 10 branches in module code, before any call into user code
  comps    one function of N variables and N list comprehensions
  chain    one function that computes a dict key through N statements of 50 xors each, then
           tests and updates it (Gen.canon follows the key's chain of values)
  lookups  one function of N reads of a dict, each of another key (dictfuse's lookups that hold)
Each cell is the median of RUNS runs of "COMMAND ir main.py -o /dev/null" in seconds, startup
included; "x" is its growth from the previous N (2.0 is linear when N doubles, 4.0 quadratic).
--ops adds, for each COMMAND that runs a .py file (the CPython-hosted compiler), the number of
the compiler's source lines executed in all ("lines") and inside Gen.flow_program, the
definite-assignment pass ("flow"), and the items its calls of dict(), list(), tuple(), sorted()
and the copy() methods copy and those of list.index(), count(), insert() and remove() scan
("items", work a line count misses): counts that do not depend on the machine (sys.monitoring
counts them, so --ops needs Python 3.12 or later).
A compiler that fails shows "failed", and its last line of stderr follows the table.
--check makes the exit status 1 if a compiler fails, or if a count of --ops grows more than 1.1
times as fast as N (a superlinear pass): tests/verify.sh runs it on N = 500 and 1000.
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


def exits(n):
    src = ["def big(x: int) -> int:", "    while True:"]
    for i in range(n):
        src += [f"        w{i} = x", f"        if x == {i}:", f"            v{i} = w{i}", "            break"]
    src += ["        x += 1", "    return x", f"print(big({n // 2}))"]
    return {"main.py": src}


def elifs(n):
    src = ["def big(c: int) -> int:", "    if c == 0:", "        r = 0"]
    for i in range(1, n // 10):
        src += [f"    elif c == {i}:", f"        r = {i}"]
    src += ["    else:", "        r = -1"] + [f"        t{j} = c + {j}" for j in range(n)]
    src += ["    return r", "print(big(3), big(-5))"]
    return {"main.py": src}


def topelifs(n):
    src = ["import sys", "c = len(sys.argv)", "if c == 0:", "    r = 0"]
    for i in range(1, n // 10):
        src += [f"elif c == {i}:", f"    r = {i}"]
    src += ["else:", "    r = -1", "print(r)"]
    return {"main.py": src}


def comps(n):
    src = ["def big(c: int) -> int:", "    t = 0"] + [f"    v{i} = c + {i}" for i in range(n)]
    src += [f"    t += len([x + v{i} for x in range({i % 3})])" for i in range(n)]
    src += ["    return t", "print(big(1))"]
    return {"main.py": src}


def chain(n):
    src = ["def big(x: int) -> int:", "    d: dict[int, int] = {0: 1, 51: 2}", "    k = x"]
    src += ["    k = k ^ " + " ^ ".join(str(j) for j in range(1, 51))] * n
    src += ["    if k in d:", "        d[k] += 10", "    return d[0] + d[51]", "print(big(0))"]
    return {"main.py": src}



def lookups(n):
    src = ["def big(d: dict[str, int]) -> int:", "    t = 0"] + [f"    t += d['k{i}']" for i in range(n)]
    src += ["    return t", "d: dict[str, int] = {}", f"for i in range({n}):", "    d['k' + str(i)] = i", "print(big(d))"]
    return {"main.py": src}


SHAPES = {"funcs": funcs, "globals": globals_, "both": both, "long": long, "top": top, "classes": classes, "modules": modules,
          "fields": fields, "calls": calls, "imports": imports, "breaks": breaks, "exits": exits, "elifs": elifs,
          "topelifs": topelifs, "comps": comps, "chain": chain,
          "lookups": lookups}


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
    # and the items its calls of copying or scanning builtins go through
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
    n = {"lines": 0, "flow": 0, "items": 0}
    depth = [0]
    work = {id(f) for f in [dict, list, tuple, sorted, dict.copy, list.copy, list.index, list.count, list.insert, list.remove]}

    def line(c, _):
        if c.co_filename != script:
            return mon.DISABLE
        n["lines"] += 1
        if depth[0] > 0:
            n["flow"] += 1

    def call(c, _, f, arg0):
        # (a method's arg0 is the object it is called on)
        if c.co_filename != script:
            return mon.DISABLE
        if id(f) in work and hasattr(arg0, "__len__"):
            n["items"] += len(arg0)

    def enter(*_):
        depth[0] += 1

    def leave(*_):
        depth[0] -= 1

    mon.register_callback(tool, mon.events.LINE, line)
    mon.register_callback(tool, mon.events.CALL, call)
    mon.register_callback(tool, mon.events.PY_START, enter)
    mon.register_callback(tool, mon.events.PY_RETURN, leave)
    for c in flow:
        mon.set_local_events(tool, c, mon.events.PY_START | mon.events.PY_RETURN)
    mon.set_events(tool, mon.events.LINE | mon.events.CALL)
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
    comps, shapes, sizes, runs, want_ops, check, keep = [], list(SHAPES), [1000, 2000, 4000], 3, False, False, ""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--ops":
            want_ops = True
            i += 1
            continue
        if a == "--check":
            check = True
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
        head += f" {label} lines | x | flow | x | items | x |" if isops else f" {label} s | x |"
        rule += " ---: | ---: | ---: | ---: | ---: | ---: |" if isops else " ---: | ---: |"
    print(head)
    print(rule, flush=True)
    errors = {}
    fast = []
    with tempfile.TemporaryDirectory() as tmp:
        for s in shapes:
            prev = {}
            prevn = 0
            for n in sizes:
                prog = write(os.path.join(keep or tmp, f"{s}-{n}"), SHAPES[s](n))
                row = f"| {s} | {n} |"
                for k, (label, cmd, isops) in enumerate(cols):
                    r = ops(cmd, prog) if isops else timed(cmd, prog, runs)
                    if isinstance(r, str):
                        errors[(label, s)] = f"{label} on {s} {n}: {r}"
                        row += " failed | | | | | |" if isops else " failed | |"
                        prev.pop(k, None)
                        continue
                    vals = [r["lines"], r["flow"], r["items"]] if isops else [r]
                    for j, v in enumerate(vals):
                        grow = f"{v / prev[k][j]:.1f}" if k in prev and prev[k][j] > 0 else ""
                        row += f" {v} | {grow} |" if isops else f" {v:.3f} | {grow} |"
                        if isops and grow and v / prev[k][j] > 1.1 * n / prevn:
                            fast.append(f"{label} on {s}: {['lines', 'flow', 'items'][j]} grew {grow} times from N = {prevn} to {n}")
                    prev[k] = vals
                prevn = n
                print(row, flush=True)
    for e in errors.values():
        print(e)
    for e in fast:
        print(e)
    if check and (errors or fast):
        sys.exit(1)


if __name__ == "__main__":
    main()
