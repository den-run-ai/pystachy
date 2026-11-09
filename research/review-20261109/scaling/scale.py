"""Compile-time scaling shapes not in tools/scaling.py. usage: scale.py [shape ...]"""
import subprocess, sys, time, os

P = __import__("os").environ.get("PYSTACHY", "./pystachy")  # the compiler under test


def specs(n):
    s = ["def ident(x):", "    return x", ""]
    for i in range(n):
        s += [f"class C{i}:", f"    def __init__(self) -> None:", f"        self.v = {i}", ""]
    s += ["t = 0"] + [f"t += ident(C{i}()).v" for i in range(n)] + ["print(t)"]
    return "\n".join(s)


def deep_hier(n):
    s = ["class B0:", "    def __init__(self) -> None:", "        self.v = 0", "    def f(self) -> int:", "        return 0", ""]
    for i in range(1, n):
        s += [f"class B{i}(B{i-1}):", "    def f(self) -> int:", f"        return super().f() + {i % 7}", ""]
    s += ["objs: list[B0] = [" + ", ".join(f"B{i}()" for i in range(0, n, max(1, n // 50))) + "]", "print(sum(o.f() for o in objs))"]
    return "\n".join(s)


def wide_hier(n):
    s = ["class Base:", "    def __init__(self, v: int) -> None:", "        self.v = v", "    def f(self) -> int:", "        return self.v", "    def __eq__(self, o: object) -> bool:", "        return isinstance(o, Base) and self.v == o.v", ""]
    for i in range(n):
        s += [f"class S{i}(Base):", "    def f(self) -> int:", f"        return self.v + {i}", ""]
    s += ["objs: list[Base] = [" + ", ".join(f"S{i}({i})" for i in range(n)) + "]", "t = 0", "for o in objs:", "    t += o.f()", "print(t, objs[0] == objs[1], str(objs[0])[:1])"]
    return "\n".join(s)


def closures(n):
    s = ["def outer(a: int) -> int:"]
    for i in range(n):
        s += ["    " + f"def g{i}(x: int) -> int:", "    " + f"    return x + a + {i}" + (f" + g{i-1}(x)" if i and i % 10 else "")]
    s += ["    return " + " + ".join(f"g{i}(1)" for i in range(0, n, max(1, n // 20))), "print(outer(2) % 1000)"]
    return "\n".join(s)


def lambdas(n):
    s = ["from typing import Callable", "fs: list[Callable[[int], int]] = ["] + [f"    lambda x: x + {i}," for i in range(n)] + ["]", "print(sum(f(1) for f in fs))"]
    return "\n".join(s)


def fstring(n):
    return "a = 3\nb = 'x'\nprint(len(f'" + "".join(f"{{a + {i}}}{{b}}" for i in range(n)) + "'))"


def concat(n):
    return "b = 'x'\nprint(len(" + " + ".join(f"b" if i % 2 else f"'s{i}'" for i in range(n)) + "))"


def binop(n):
    return "a = 3\nprint((" + " + ".join(f"a * {i % 7}" for i in range(n)) + ") % 1000)"


def dataclasses_(n):
    s = ["from dataclasses import dataclass", ""]
    for i in range(n):
        s += ["@dataclass(order=True)", f"class D{i}:", "    a: int", "    b: str = 'x'", ""]
    s += ["t = 0"] + [f"t += int(D{i}({i}) < D{i}({i + 1})) + int(D{i}(1) == D{i}(1)) + len(repr(D{i}(2)))" for i in range(n)] + ["print(t)"]
    return "\n".join(s)


def generators(n):
    s = []
    for i in range(n):
        s += [f"def g{i}(n: int):", "    for i in range(n):", f"        yield i + {i}", ""]
    s += ["t = 0"] + [f"t += sum(g{i}(3))" for i in range(n)] + ["print(t)"]
    return "\n".join(s)


def isinst(n):
    s = ["def f(x: int | str | float | None) -> int:", "    t = 0"]
    for i in range(n):
        s += [f"    if isinstance(x, {['int', 'str', 'float'][i % 3]}):", f"        t += {i}", "    elif x is None:", "        t -= 1"]
    s += ["    return t", "print(f(1) + f('a') + f(1.5) + f(None))"]
    return "\n".join(s)


def dictlit(n):
    return "d = {" + ", ".join(f"'k{i}': {i}" for i in range(n)) + "}\nprint(len(d), d['k1'])"


def listlit_str(n):
    return "xs = [" + ", ".join(f"'s{i}'" for i in range(n)) + "]\nprint(len(xs), xs[1])"


def methods(n):
    s = ["class C:", "    def __init__(self) -> None:", "        self.v = 1"]
    for i in range(n):
        s += [f"    def m{i}(self, x: int) -> int:", f"        return x + self.v + {i}" + (f" + self.m{i-1}(x)" if i and i % 10 else "")]
    s += ["c = C()", "t = 0"] + [f"t += c.m{i}(1)" for i in range(n)] + ["print(t % 1000)"]
    return "\n".join(s)


def unions_join(n):
    s = []
    for i in range(n):
        s += [f"v{i} = {i}"]
    s += ["def setall() -> None:"] + [f"    global v{i}" for i in range(n)] + [f"    v{i} = 's'" for i in range(n)] + ["setall()", "print(v0, v1)"]
    return "\n".join(s)


def nested_calls(n):
    s = ["def f(x: int) -> int:", "    return x + 1", "print(" + "f(" * n + "0" + ")" * n + ")"]
    return "\n".join(s)


def tuple_types(n):
    s = ["def first(t):", "    return t[0]", "t = 0"]
    for i in range(n):
        k = i % 8 + 1
        items = ", ".join(["1", "'a'", "1.5", "True"][(i >> j) % 4] for j in range(k))
        s += [f"t += len(str(first(({items},))))"]
    s += ["print(t)"]
    return "\n".join(s)


def elif_str(n):
    s = ["def f(s: str) -> int:"]
    for i in range(n):
        s += [f"    {'if' if i == 0 else 'elif'} s == 'k{i}':", f"        return {i}"]
    s += ["    return -1", "print(f('k5') + f('zz'))"]
    return "\n".join(s)


def prints(n):
    return "a = 1\nb = 'x'\n" + "\n".join(f"print(a + {i}, b, {i}.5)" for i in range(n))


def locals_(n):
    s = ["def f(a: int) -> int:"] + [f"    v{i} = a + {i}" if i == 0 else f"    v{i} = v{i-1} + {i % 3}" for i in range(n)] + [f"    return v{n-1}", "print(f(1))"]
    return "\n".join(s)


def optional_chain(n):
    s = ["class N:", "    def __init__(self, nxt: 'N | None') -> None:", "        self.nxt = nxt", "        self.v = 1", "", "def f(n: N | None) -> int:", "    t = 0"]
    for i in range(n):
        s += ["    if n is not None:", "        t += n.v", "        n = n.nxt"]
    s += ["    return t", "print(f(N(N(N(None)))))"]
    return "\n".join(s)


SHAPES = {"specs": specs, "deep_hier": deep_hier, "wide_hier": wide_hier, "closures": closures, "lambdas": lambdas, "fstring": fstring, "concat": concat,
          "binop": binop, "dataclasses": dataclasses_, "generators": generators, "isinst": isinst, "dictlit": dictlit, "listlit_str": listlit_str, "methods": methods,
          "unions_join": unions_join, "nested_calls": nested_calls, "tuple_types": tuple_types, "elif_str": elif_str, "prints": prints, "locals": locals_, "optional_chain": optional_chain}
NS = {"default": [200, 400, 800, 1600], "deep_hier": [100, 200, 400, 800], "nested_calls": [100, 200, 400, 800], "fstring": [100, 200, 400, 800], "isinst": [100, 200, 400, 800],
      "wide_hier": [100, 200, 400, 800], "specs": [100, 200, 400, 800]}


def run(shape, n):
    src = SHAPES[shape](n)
    path = f"s_{shape}_{n}.py"
    open(path, "w").write(src + "\n")
    best = None
    for _ in range(2):
        t0 = time.perf_counter()
        r = subprocess.run([P, "ir", path, "-o", "/dev/null"], capture_output=True, text=True, timeout=300)
        dt = time.perf_counter() - t0
        if r.returncode != 0:
            return None, (r.stderr.strip().split("\n") or [""])[0][:160]
        best = dt if best is None else min(best, dt)
    return best, ""


for shape in sys.argv[1:] or list(SHAPES):
    cells = []
    prev = None
    for n in NS.get(shape, NS["default"]):
        try:
            t, err = run(shape, n)
        except subprocess.TimeoutExpired:
            cells.append(f"N={n}: TIMEOUT>300s"); break
        if t is None:
            cells.append(f"N={n}: FAIL {err}"); break
        cells.append(f"N={n}: {t*1000:7.0f} ms" + (f" (x{t/prev:4.1f})" if prev else ""))
        prev = t
    print(f"{shape:15} " + "  ".join(cells), flush=True)
