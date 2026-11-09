import sys

LOG: list[str] = []


def t(name: str, v: int) -> int:
    LOG.append(name)
    return v


def ts(name: str, v: str) -> str:
    LOG.append(name)
    return v


def tl(name: str, v: list[int]) -> list[int]:
    LOG.append(name)
    return v


def td(name: str, v: dict[str, int]) -> dict[str, int]:
    LOG.append(name)
    return v


def tb(name: str, v: bool) -> bool:
    LOG.append(name)
    return v


def f3(a: int, b: int = 10, *, c: int = 100) -> int:
    LOG.append(f"f3({a},{b},{c})")
    return a + b + c


class Obj:
    def __init__(self, name: str) -> None:
        self.name = name
        self.v = 0
        self.items: list[int] = [0, 0, 0, 0]

    def get(self, tag: str) -> "Obj":
        LOG.append(f"{self.name}.get({tag})")
        return self

    def __getitem__(self, i: int) -> int:
        LOG.append(f"{self.name}[{i}]")
        return self.items[i]

    def __setitem__(self, i: int, v: int) -> None:
        LOG.append(f"{self.name}[{i}]={v}")
        self.items[i] = v

    def __add__(self, o: "Obj") -> "Obj":
        LOG.append(f"{self.name}+{o.name}")
        return Obj(self.name + o.name)

    def __iadd__(self, o: "Obj") -> "Obj":
        LOG.append(f"{self.name}+={o.name}")
        self.name += o.name
        return self

    def __lt__(self, o: "Obj") -> bool:
        LOG.append(f"{self.name}<{o.name}")
        return self.name < o.name

    def __eq__(self, o: object) -> bool:
        if isinstance(o, Obj):
            LOG.append(f"{self.name}=={o.name}")
            return self.name == o.name
        return False

    def __bool__(self) -> bool:
        LOG.append(f"bool({self.name})")
        return self.name != ""


def flush(label: str) -> None:
    print(label, " ".join(LOG))
    LOG.clear()


def main(z: int) -> None:
    xs = [1, 2, 3, 4, 5]
    d = {"a": 1, "b": 2}
    # call arguments
    f3(t("a1", 1), t("a2", 2), c=t("a3", 3))
    flush("call")
    f3(c=t("k1", 1), a=t("k2", 2), b=t("k3", 3))
    flush("kwcall")
    # binary / compare
    r = t("l", 1) + t("m", 2) * t("r", 3) - t("s", 4) ** t("p", 2)
    flush(f"binop {r}")
    r2 = t("c1", 1) < t("c2", 2) < t("c3", 3) < t("c4", 0) < t("c5", 9)
    flush(f"chain {r2}")
    r3 = t("o1", 0) or t("o2", 0) or t("o3", 7) or t("o4", 8)
    flush(f"or {r3}")
    r4 = t("n1", 1) and t("n2", 0) and t("n3", 5)
    flush(f"and {r4}")
    r5 = t("y", 1) if tb("cond", z == 0) else t("n", 2)
    flush(f"cond {r5}")
    # subscripts / slices
    tl("list", xs)[t("idx", 1)] = t("val", 99)
    flush(f"setitem {xs}")
    tl("list", xs)[t("idx", 2)] += t("val", 1)
    flush(f"augitem {xs}")
    td("dict", d)[ts("key", "a")] += t("val", 10)
    flush(f"augdict {d}")
    r6 = tl("list", xs)[t("lo", 1) : t("hi", 4) : t("st", 2)]
    flush(f"slice {r6}")
    tl("list", xs)[t("lo", 0) : t("hi", 2)] = tl("rhs", [7, 8, 9])
    flush(f"setslice {xs}")
    del tl("list", xs)[t("di", 0)], tl("list2", xs)[t("dj", 0)]
    flush(f"del {xs}")
    # assignment targets
    a = b = t("chain", 5)
    flush(f"chainassign {a} {b}")
    xs[t("i1", 0)], xs[t("i2", 1)] = t("v1", 100), t("v2", 200)
    flush(f"tupleassign {xs}")
    i = 0
    i, xs[i] = 1, 55
    flush(f"i-then-xs {i} {xs}")
    xs[i], i = 66, 0
    flush(f"xs-then-i {i} {xs}")
    p, q = 1, 2
    p, q = q, p + q
    flush(f"swap {p} {q}")
    # displays
    r7 = [t("e1", 1), t("e2", 2), *tl("star", [3, 4]), t("e3", 5)]
    flush(f"listdisp {r7}")
    r8 = {ts("k1", "x"): t("v1", 1), ts("k2", "y"): t("v2", 2), ts("k3", "x"): t("v3", 3)}
    flush(f"dictdisp {r8}")
    r9 = {t("s1", 1), t("s2", 2), t("s3", 1)}
    flush(f"setdisp {sorted(r9)}")
    r10 = (t("t1", 1), t("t2", 2))
    flush(f"tupledisp {r10}")
    r11 = f"{t('f1', 1)}-{t('f2', 2):>{t('w', 3)}}-{ts('f3', 'z')!r}"
    flush(f"fstring {r11}")
    r12 = "%s-%s" % (t("p1", 1), t("p2", 2))
    flush(f"pct {r12}")
    r13 = "{}-{}".format(t("m1", 1), t("m2", 2))
    flush(f"format {r13}")
    # comprehension
    r14 = [t(f"body{x}", x) for x in tl("iter", [1, 2, 3]) if tb(f"if{x}", x != 2)]
    flush(f"comp {r14}")
    r15 = {ts(f"k{x}", str(x)): t(f"v{x}", x) for x in tl("iter", [1, 2])}
    flush(f"dictcomp {r15}")
    r16 = [(x, y) for x in tl("outer", [1, 2]) for y in tl(f"inner{x}", [10, 20]) if tb(f"c{x}{y}", True)]
    flush(f"nested {r16}")
    # objects
    o = Obj("o")
    o.get("a")[t("i", 1)] = o.get("b")[t("j", 2)] + t("k", 3)
    flush(f"objitem {o.items}")
    o.get("c")[t("i", 0)] += t("v", 5)
    flush(f"objaug {o.items}")
    o1 = Obj("x").get("1") + Obj("y").get("2")
    flush(f"objadd {o1.name}")
    o2 = Obj("p")
    o3 = o2
    o2 += Obj("q").get("r")
    flush(f"objiadd {o2.name} {o3.name} {o2 is o3}")
    r17 = Obj("a") < Obj("b") < Obj("c")
    flush(f"objchain {r17}")
    r18 = Obj("a") == Obj("a") != Obj("b")
    flush(f"objeqchain {r18}")
    r19 = Obj("") or Obj("z")
    flush(f"objor {r19.name}")
    o.get("x").v = t("attr", 4)
    flush(f"setattr {o.v}")
    o.get("y").v += t("attr", 4)
    flush(f"augattr {o.v}")
    # walrus, lambda defaults, conditional calls
    if (n := t("w1", 3)) > t("w2", 2) and (m := t("w3", n + 1)) > 3:
        flush(f"walrus {n} {m}")
    g = lambda u=t("default", 1): u + t("body", 1)
    flush("lambda-def")
    g()
    g(5)
    flush("lambda-call")
    print(t("pa", 1), t("pb", 2), sep=ts("sep", "-"), end=ts("end", "\n"))
    flush("print")
    r21 = max(t("x1", 3), t("x2", 9), t("x3", 5))
    flush(f"max {r21}")
    r22 = sorted([t("s1", 3), t("s2", 1)], key=lambda v: t(f"key{v}", -v), reverse=tb("rev", True))
    flush(f"sorted {r22}")
    r23 = xs[t("a", 0)] if t("b", 1) in tl("c", xs) else t("d", 0)
    flush(f"in {r23}")
    r24 = t("z1", 1) in tl("z2", [1]) in [tl("z3", [1])]
    flush(f"inchain {r24}")
    try:
        r25 = t("d1", 1) // t("d2", 0) + t("d3", 1)
    except ZeroDivisionError:
        flush("div0")
    try:
        xs[t("e1", 99)] = t("e2", 1)
    except IndexError:
        flush("idxerr")
    try:
        td("ed", d)[ts("ek", "zz")] += t("ev", 1)
    except KeyError:
        flush("keyerr")
    try:
        f3(t("g1", 1), t("g2", 2) // t("g3", 0), c=t("g4", 4))
    except ZeroDivisionError:
        flush("argerr")
    r26 = [t("r1", 1), t("r2", 2)][t("r3", 0)] + (t("r4", 1), t("r5", 2))[t("r6", 1)]
    flush(f"subdisp {r26}")
    s = "abc"
    r27 = ts("s1", s)[t("s2", 0)] + ts("s3", s).upper()[t("s4", 1) : t("s5", 3)] * t("s6", 2)
    flush(f"strops {r27}")
    r28 = ts("j1", ",").join([ts("j2", "a"), ts("j3", "b")])
    flush(f"join {r28}")
    r29 = td("g1", d).get(ts("g2", "q"), t("g3", 7))
    flush(f"get {r29}")
    r30 = td("sd1", d).setdefault(ts("sd2", "a"), t("sd3", 7))
    flush(f"setdefault {r30}")
    tl("ap1", xs).append(t("ap2", 3))
    tl("in1", xs).insert(t("in2", 0), t("in3", 3))
    tl("ex1", xs).extend(tl("ex2", [1]))
    flush(f"listmeth {xs}")
    r31 = range(t("ra", 0), t("rb", 10), t("rc", 3))[t("rd", 2)]
    flush(f"range {r31}")
    for v in range(t("fa", 0), t("fb", 2)):
        t(f"loop{v}", v)
    flush("forrange")
    for idx, v in enumerate(tl("en1", [5, 6]), t("en2", 10)):
        t(f"e{idx}{v}", v)
    flush("enumerate")
    for v1, v2 in zip(tl("z1", [1, 2]), tl("z2", [3, 4])):
        t(f"z{v1}{v2}", v1)
    flush("zip")
    r32 = sum(t(f"g{x}", x) for x in tl("gi", [1, 2])) + t("after", 0)
    flush(f"genexp {r32}")
    assert t("as1", 1) == 1, ts("as2", "msg")
    flush("assert")
    r33 = int(ts("c1", "5")) + float(ts("c2", "1.5")) + len(ts("c3", "ab"))
    flush(f"conv {r33}")
    r34 = t("is1", 1) == t("is2", 1) and (ts("x", "a") + ts("y", "b")) * t("n", 2) == ts("cmp", "abab")
    flush(f"mixed {r34}")
    r35 = -t("u1", 1) + ~t("u2", 2) + (not tb("u3", False))
    flush(f"unary {r35}")
    r36 = divmod(t("dm1", 7), t("dm2", 2)), pow(t("pw1", 2), t("pw2", 3), t("pw3", 5)), round(t("rd1", 5) / t("rd2", 2), t("rd3", 1))
    flush(f"builtins {r36}")
    r37 = abs(t("ab", -1)) if tb("t1", True) and not tb("t2", False) or tb("t3", True) else t("el", 0)
    flush(f"boolchain {r37}")


main(len(sys.argv) - 1)
