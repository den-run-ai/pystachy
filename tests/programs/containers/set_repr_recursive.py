# a set or frozenset that the __repr__ of one of its elements prints again is set(...) or
# frozenset(...) there, as CPython's set_repr prints it (#1586): through an attribute, through a
# list between them, in str(), an f-string and print(); an element's __repr__ that raises leaves
# the set printable


class A:
    def __init__(self, name: str) -> None:
        self.name = name
        self.s: set[A] = set()
        self.f: frozenset[A] = frozenset()
        self.l: list[set[A]] = []
        self.fail = False

    def __repr__(self) -> str:
        if self.fail:
            raise ValueError("no repr of " + self.name)
        if len(self.l) > 0:
            return self.name + repr(self.l)
        if len(self.f) > 0:
            return self.name + repr(self.f)
        return self.name + repr(self.s)


a = A("a")
a.s.add(a)
print(repr(a.s))
print(a.s, str(a.s), f"{a.s}", [a.s], {1: a.s})
print(a)

b = A("b")
b.f = frozenset([b])
print(repr(b.f), b)

c = A("c")
c.l.append({c})
print(c.l, c)

d = A("d")
d.s.add(d)
d.fail = True
try:
    print(d.s)
except ValueError as e:
    print("ValueError", e)
d.fail = False
print(d.s, d.s)

e: set[A] = set()
print(e, frozenset(e), {1, 2}, frozenset(["x"]))
