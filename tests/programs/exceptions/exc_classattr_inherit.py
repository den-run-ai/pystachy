# Class attributes of exception classes: a subclass shares those it inherits with its base (one
# variable, which the class body that binds it evaluates), read through either class and by the
# objects of both that have not assigned their own; a class body that binds one again (with or
# without the annotation, of the base's type) gives the subclass its own.
class E(Exception):
    log: list[str] = []
    reg: dict[str, int] = {}
    n: int = len("abc")
    t = (1, "a")
    count = 0
    level = 1
    name: str | None = None

    def record(self) -> None:
        self.log.append(str(self))


class S(E):
    pass


class T(E):
    level = 2
    name: str | None = "t"


class U(T):
    pass


print(S.log, S.n, S.t, S("x").log, S("y").n, S("z").t)
S.log.append("seen")
E.reg["a"] = 1
S.reg["b"] = 2
print(E.log, E.reg, S.log is E.log, S.reg is E.reg)
S("s1").record()
E("e1").record()
T("t1").record()
print(E.log, S.log, S("q").log, len(U.log))
E.count = 5
print(S.count, T.count, U.count, S("a").count, U("b").count)
E.count += 1
x: E = S("c")
print(E.count, S.count, x.count)
x.count = 9
print(x.count, S("d").count, E.count)
print(E.level, S.level, T.level, U.level, S("e").level, T("f").level, U("g").level)
y: E = U("h")
print(y.level, y.name, E("i").name, S.name, T.name, U.name)
try:
    raise U("u")
except E as z:
    print(type(z).__name__, z.level, z.name, z.n, z.t)


# a class variable that __init__ counts through the class, read by the objects that have not
# assigned their own (a new object has not: it reads the class's, also after it changes)
class Q(Exception):
    hits = 0
    names: list[str] = []
    label: str = "q" + "!"

    def __init__(self, msg: str) -> None:
        super().__init__(msg)
        Q.hits += 1
        self.names.append(msg)

    def bump(self) -> int:
        self.hits += 10
        return self.hits


class R(Q):
    pass


class W(R):
    label = "w"


q = Q("first")
Q.hits = 7
print(q.hits, Q("y").hits, Q.hits)
r = R("a")
w = W("b")
print(Q.hits, R.hits, W.hits, r.hits, w.hits, hasattr(r, "hits"))
print(r.bump(), r.hits, R.hits, w.hits, Q.hits)
Q.hits = 100
print(r.hits, w.hits, R("c").hits, W.hits)
print(Q.names, R.names is W.names, r.label, w.label, Q.label, R.label, W.label)
try:
    raise W("x")
except R as e:
    print(e.hits, e.label, e.names[-1], e.bump())
