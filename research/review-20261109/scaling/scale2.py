import subprocess, sys, time
P = __import__("os").environ.get("PYSTACHY", "./pystachy")  # the compiler under test


def hier(n, eq, usecmp, usestr, loop):
    s = ["class Base:", "    def __init__(self, v: int) -> None:", "        self.v = v", "    def f(self) -> int:", "        return self.v"]
    if eq:
        s += ["    def __eq__(self, o: object) -> bool:", "        return isinstance(o, Base) and self.v == o.v"]
    s += [""]
    for i in range(n):
        s += [f"class S{i}(Base):", "    def f(self) -> int:", f"        return self.v + {i}", ""]
    s += ["objs: list[Base] = [" + ", ".join(f"S{i}({i})" for i in range(n)) + "]", "t = 0"]
    if loop:
        s += ["for o in objs:", "    t += o.f()"]
    s += ["print(t" + (", objs[0] == objs[1]" if usecmp else "") + (", str(objs[0])[:1]" if usestr else "") + ")"]
    return "\n".join(s)


def deep(n, sup):
    s = ["class B0:", "    def __init__(self) -> None:", "        self.v = 0", "    def f(self) -> int:", "        return 0", "    def g(self) -> int:", "        return self.v + 1", ""]
    for i in range(1, n):
        s += [f"class B{i}(B{i-1}):", "    def f(self) -> int:", f"        return {'super().f() + ' if sup else ''}{i % 7}", ""]
    s += [f"objs: list[B0] = [B0(), B{n-1}(), B{n//2}()]", "print(sum(o.f() + o.g() for o in objs))"]
    return "\n".join(s)


def closures(n, chain):
    s = ["def outer(a: int) -> int:"]
    for i in range(n):
        s += ["    " + f"def g{i}(x: int) -> int:", "    " + f"    return x + a + {i}" + (f" + g{i-1}(x)" if chain and i and i % 10 else "")]
    s += ["    return " + " + ".join(f"g{i}(1)" for i in range(0, n, max(1, n // 20))), "print(outer(2) % 1000)"]
    return "\n".join(s)


def gens(n, call):
    s = []
    for i in range(n):
        s += [f"def g{i}(n: int):", "    for i in range(n):", f"        yield i + {i}", ""]
    s += ["t = 0"] + ([f"t += sum(g{i}(3))" for i in range(n)] if call else [f"t += sum(g0(3))"]) + ["print(t)"]
    return "\n".join(s)


def run(label, mk, ns):
    cells = []; prev = None
    for n in ns:
        open("x.py", "w").write(mk(n) + "\n")
        best = 1e9; err = ""
        for _ in range(2):
            t0 = time.perf_counter()
            r = subprocess.run([P, "ir", "x.py", "-o", "x.ll"], capture_output=True, text=True, timeout=600)
            best = min(best, time.perf_counter() - t0)
            if r.returncode:
                err = r.stderr.strip().split("\n")[0][:110]; break
        if err:
            cells.append(f"N={n}: FAIL {err}"); break
        lines = sum(1 for _ in open("x.ll"))
        cells.append(f"N={n}: {best*1000:6.0f} ms, {lines} IR lines" + (f" (x{best/prev:.1f})" if prev else ""))
        prev = best
    print(f"{label:26} " + " | ".join(cells), flush=True)


run("wide: loop only", lambda n: hier(n, False, False, False, True), [200, 400, 800, 1600])
run("wide: +__eq__ defined", lambda n: hier(n, True, False, False, True), [200, 400, 800, 1600])
run("wide: +== used", lambda n: hier(n, True, True, False, True), [200, 400, 800, 1600])
run("wide: str() only", lambda n: hier(n, False, False, True, False), [200, 400, 800, 1600])
run("wide: no loop/no use", lambda n: hier(n, False, False, False, False), [200, 400, 800, 1600])
run("deep: super chain", lambda n: deep(n, True), [10, 20, 40, 80, 100])
run("deep: no super", lambda n: deep(n, False), [10, 20, 40, 80, 160, 320])
run("closures: independent", lambda n: closures(n, False), [200, 400, 800, 1600])
run("closures: chained", lambda n: closures(n, True), [200, 400, 800, 1600])
run("generators: all called", lambda n: gens(n, True), [200, 400, 800, 1600])
run("generators: one called", lambda n: gens(n, False), [200, 400, 800, 1600])
