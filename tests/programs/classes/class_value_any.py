# type[object] (and type alone) holds the class object of any ordinary class: unrelated classes
# share registries, dict keys and isinstance() tests, and type(x) of a union's object is one.
class A:
    def __init__(self) -> None:
        self.tag = "a"


class B(A):
    pass


class C:
    def __init__(self, n: int = 0) -> None:
        self.n = n


class Registry:
    def __init__(self) -> None:
        self.kinds: list[type] = []
        self.names: dict[type[object], str] = {}
        self.last: type | None = None

    def add(self, k: type[object], name: str) -> None:
        self.kinds.append(k)
        self.names[k] = name
        self.last = k


def kind(x: A | C) -> type:
    return type(x)


def describe(k: type[object]) -> str:
    return f"{k.__name__}/{k.__qualname__}/{k.__module__}"


r = Registry()
r.add(A, "first")
r.add(C, "second")
r.add(B, "third")
print(r.kinds, r.names, r.last, len(r.names))
print([describe(k) for k in r.kinds], r.names[C], r.names.get(B), A in r.names, kind(C()) in r.names)
print(kind(A()), kind(B()) is B, kind(C()) is C, kind(C()) == kind(C(1)), kind(A()) != kind(B()))
for x in [A(), B()]:
    print([isinstance(x, k) for k in r.kinds], [issubclass(type(x), k) for k in r.kinds])
c: A | C = C(3)
print([isinstance(c, k) for k in r.kinds], [issubclass(k, A) for k in r.kinds], [issubclass(k, C) for k in r.kinds])
names: set[type] = {A, C, B}
table: dict[type, int] = {A: 1, C: 2}
print(sorted([k.__name__ for k in names]), table[type(c)], hash(kind(c)) == hash(C))
mixed = [A, C]
mixed.append(B)
print(mixed, mixed.index(C), B in mixed, mixed.count(A))
pick: type = A if len(mixed) > 5 else C
print(pick, pick is C, str(pick), repr(pick), f"{pick}")
none: type | None = None
print(none, none is None, r.last is not None, r.last == B)
handlers: dict[type, str] = {A: "handle A", C: "handle C"}
objs: list[A | C] = [A(), C(), B()]
for obj in objs:
    print(handlers.get(type(obj), "no handler"))
k2: type[A] = B
top: type = k2
print(top, top is B, isinstance(B(), top), isinstance(A(), top))


class Holder:
    def __init__(self) -> None:
        self.k: type = A
        self.seen: set[type] = set()

    def swap(self) -> None:
        self.k = C if self.k is A else A
        self.seen.add(self.k)


def choose(n: int):
    if n == 0:
        return A
    if n == 1:
        return C
    return B


def name_of(k: type = A) -> str:
    if k is A:
        return "the A"
    elif k is C:
        return "the C"
    return k.__name__


h = Holder()
h.swap()
h.swap()
h.swap()
print(h.k, sorted(k.__name__ for k in h.seen), len(h.seen))
print([choose(n) for n in range(3)], [name_of(choose(n)) for n in range(3)], name_of())
print(sorted([C, B, A], key=lambda k: k.__name__), max([A, C], key=lambda k: k.__name__))
pairs: list[tuple[type, int]] = [(A, 1), (C, 2)]
for k, n in pairs:
    print(k.__name__, n, k == A, k != C)
by_name: dict[str, type] = {k.__name__: k for k in [A, B, C]}
print(by_name["B"], by_name["C"] is C, issubclass(by_name["B"], A), issubclass(by_name["C"], A))
