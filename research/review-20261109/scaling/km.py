import subprocess, time
P = __import__("os").environ.get("PYSTACHY", "./pystachy")  # the compiler under test


def km(k, m, override_one):
    s = ["class Base:", "    def __init__(self, v: int) -> None:", "        self.v = v"]
    for j in range(m):
        s += [f"    def m{j}(self, x: int) -> int:", f"        y = x + self.v + {j}", f"        if y % 3 == 0:", f"            y += self.hook()", f"        return y * 2 + len(str(y))"]
    s += ["    def hook(self) -> int:", "        return 1", ""]
    for i in range(k):
        s += [f"class S{i}(Base):", "    def hook(self) -> int:", f"        return {i + 2}", ""]
    s += ["objs: list[Base] = [" + ", ".join(f"S{i}({i})" for i in range(k)) + "]", "t = 0", "for o in objs:"]
    s += [f"    t += o.m{j}(1)" for j in range(m)]
    s += ["print(t)"]
    return "\n".join(s)


for k, m in [(10, 10), (20, 10), (40, 10), (10, 20), (10, 40), (40, 40)]:
    open("km.gen.py", "w").write(km(k, m, True) + "\n")
    t0 = time.perf_counter()
    r = subprocess.run([P, "ir", "km.gen.py", "-o", "km.ll"], capture_output=True, text=True)
    dt = time.perf_counter() - t0
    if r.returncode:
        print(k, m, "FAIL", r.stderr.split("\n")[0][:150]); continue
    ll = open("km.ll").read()
    defs = ll.count("\ndefine ")
    mdefs = sum(1 for line in ll.split("\n") if line.startswith("define") and ".m" in line.split("(")[0])
    print(f"K={k:3} subclasses x M={m:3} inherited methods: {dt*1000:6.0f} ms, {ll.count(chr(10)):7} IR lines, {defs:5} functions ({mdefs} method bodies; K*M = {k*m})")
