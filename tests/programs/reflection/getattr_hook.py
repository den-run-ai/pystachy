# __getattr__ (#1536): CPython calls it for an attribute that ordinary lookup does not find, so a
# read of a name the class lacks is a call of it with that name, also inside the class's methods.
# A field, a class attribute, a method and a property never reach it, and its AttributeError is
# the read's.
from typing import Callable


class Conf:
    limit = 7

    def __init__(self) -> None:
        self.data = {"port": 80, "depth": 3}
        self.calls = 0
        self.host = "local"
        self.first = self.port
        print("init", self.first, self.depth)

    def __getattr__(self, name: str) -> int:
        self.calls += 1
        if name not in self.data:
            raise AttributeError(f"no setting {name!r}")
        return self.data[name]

    @property
    def twice(self) -> int:
        return 2 * self.port

    def total(self) -> int:
        return self.port + self.depth + self.limit

    def describe(self) -> str:
        return f"{self.host}:{self.port}/{self.depth}"


c = Conf()
print(c.port)
print(c.port + c.depth * 2, -c.depth, c.port // 7, abs(c.depth - 5))
print(c.host, c.limit, c.first, c.calls)
print(c.twice, c.total(), c.describe())
print(f"{c.port:>5}|{c.depth!r}|{c.port + 1}")
print("{0.port}/{0.host}/{0.depth}".format(c), "%d" % c.port, str(c.depth) + "!")
print(c.calls)
try:
    print(c.missing)
except AttributeError as e:
    print("AttributeError:", e)
print(c.calls)
xs = [c.port, c.depth]
print(xs, sum(xs), {c.depth: c.port}, (c.port, c.host))
print(c.port if c.depth > 2 else c.depth, c.depth == 3, c.port in xs)
total = 0
while c.depth < 6:
    c.data["depth"] += 1
    total += c.depth
print(total, [c.port + i for i in range(2)], c.__getattr__("port"))
read = lambda: c.depth
print(read(), sorted([Conf(), c], key=lambda x: x.depth)[0].depth)


class Ops:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def __getattr__(self, name: str) -> Callable[[int], int]:
        self.seen.append(name)
        if name == "double":
            return lambda x: 2 * x
        if name == "neg":
            return lambda x: -x
        raise AttributeError(name)


def arg(ops: Ops, x: int) -> int:
    ops.seen.append("arg")
    return x


# the attribute is found, by the method, before the call's arguments are evaluated
o = Ops()
print(o.double(21), o.neg(5))
f = o.double
print(f(4), o.seen)
print(o.double(arg(o, 3)), o.seen)
try:
    o.nope(arg(o, 1))
except AttributeError as e:
    print("AttributeError:", e)
print(o.seen)


class Strict:
    def __init__(self) -> None:
        self.x = 1

    def __getattr__(self, name: str) -> int:
        raise AttributeError(f"Strict has no {name}")


s = Strict()
print(s.x)
try:
    print(s.y)
except AttributeError as e:
    print("AttributeError:", e)


class Tree:
    def __init__(self, label: str) -> None:
        self.label = label

    def __getattr__(self, name: str) -> "Tree":
        return Tree(self.label + "." + name)


print(Tree("root").a.b.c.label)


class Words:
    def __getattr__(self, name: str) -> str:
        return name.upper()

    def shout(self) -> str:
        return self.hello + "!"


w = Words()
print(w.abc, w.shout(), w.a + w.b, len(w.xyz), w.q == "Q", w.q.lower())


class Maybe:
    def __init__(self) -> None:
        self.known = {"a": 1}

    def __getattr__(self, name: str) -> int | None:
        return self.known.get(name)


m = Maybe()
print(m.a, m.b, m.a is None, m.b is None)
v = m.a
if v is not None:
    print(v + 1)


class Mixed:
    def __getattr__(self, name: str) -> list[str]:
        return [name, name]


class Flags:
    def __getattr__(self, name: str) -> bool:
        return name.startswith("is_")


class Half:
    def __getattr__(self, name: str) -> float:
        return len(name) / 2


class Quiet:
    def __getattr__(self, name: str) -> None:
        print("asked", name)


print(Mixed().ab, Flags().is_ok, Flags().other, Half().abc, Quiet().thing)
