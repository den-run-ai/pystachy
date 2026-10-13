# Class templates (M2): a class whose __init__ takes a parameter without an annotation makes each
# object of a specialization, whose fields are typed by the arguments of the call that makes it;
# calls whose fields get the same types share one
from typing import Callable


class Box:
    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v

    def __repr__(self) -> str:
        return "Box(" + repr(self.v) + ")"


a = Box(1)
b = Box("x")
c = Box(2)
print(a.v + 1, b.v.upper(), c.get(), a, b, [a, c])
print(isinstance(a, Box), isinstance(b, Box))


class A:
    # (the unannotated __init__ that tests/errors/no_annotation.py rejected before class templates)
    def __init__(self, x) -> None:
        self.x = x

    def m(self, y):
        return self.x + y


print(A(1).m(2), A("a").m("b"), A(1.5).m(1))


class Pair:
    made = 0  # (a class attribute: one for every specialization, as for CPython's one class)

    def __init__(self, a, b, tag: str = "p"):
        self.a = a
        self.b = b
        self.tag = tag
        self.n = len(tag)
        Pair.made += 1

    def swap(self):
        return Pair(self.b, self.a, self.tag)

    def first(self):
        return self.a

    def __eq__(self, other) -> bool:
        return self.a == other.a and self.b == other.b

    def __lt__(self, other) -> bool:
        return self.a < other.a

    def __len__(self) -> int:
        return 2

    def __repr__(self) -> str:
        return f"Pair({self.a!r}, {self.b!r}, {self.tag})"

    @staticmethod
    def of(x):
        return Pair(x, x)

    @classmethod
    def twin(cls, x):
        return cls(x, [x])


p = Pair(1, "one")
q = p.swap()
print(p, q, p.first() + 1, q.first().upper(), len(p), Pair.made)
print(sorted([Pair(3, "c"), Pair(1, "a"), Pair(2, "b")]), Pair(1, "a") == Pair(1, "a"), Pair(1, "a") == Pair(1, "b"))
print(Pair.of(2.5), Pair.twin("t"), p.of(7), Pair(b=2, a=1, tag="kw"), Pair(1, 2) == Pair(1.0, 2.0))


class Fn:
    # a function as an argument: the field has that function's type, a specialization per function
    def __init__(self, f):
        self.f = f

    def __call__(self, x):
        return self.f(x)


def twice(x: int) -> int:
    return 2 * x


print(Fn(lambda x: x + 1)(1), Fn(twice)(5), Fn(len)("abc"))


class Op:
    # a Callable annotation: any function of that shape, so one specialization for them all
    def __init__(self, f: Callable[[int], int], name):
        self.f = f
        self.name = name

    def run(self, x: int) -> str:
        return f"{self.name}({x}) = {self.f(x)}"


ops = [Op(lambda x: x * x, "square"), Op(twice, "twice"), Op(abs, "abs")]
print([o.run(-3) for o in ops])


class Holder:
    # an annotation that names a class template types nothing: Holder is one too
    def __init__(self, item: Pair, note):
        self.item = item
        self.note = note

    def show(self) -> str:
        return f"{self.item!r}/{self.note}"


def double(p: Pair) -> Pair:
    return Pair(p.a * 2, p.b * 2)


def describe(x) -> str:
    return "a Box" if isinstance(x, Box) else "a Pair" if isinstance(x, Pair) else "something else"


h = Holder(Pair(1, 2), "n")
h2 = Holder(Pair("x", "y"), 3)
print(h.show(), h2.show(), double(Pair(2, "ab")), isinstance(h.item, Pair))
x: Pair = Pair(5, 6)
print(x.first(), double(x), describe(Box(1)), describe(Pair(1, 2)), describe(3))


class Node:
    # a field annotated with the class itself: the same specialization, as typing.Self would be
    def __init__(self, value, next: "Node | None" = None):
        self.value = value
        self.next: "Node | None" = next

    def total(self):
        n: "Node | None" = self
        t = 0
        while n is not None:
            t += n.value
            n = n.next
        return t


lst = Node(1, Node(2, Node(3)))
print(lst.total(), lst.next.value if lst.next is not None else -1, Node(10).total(), Node("leaf").value)


class Wrap:
    # a field made by a class template's call is typed by that call
    def __init__(self, v):
        self.inner = Pair(v, [v])
        self.v = v


class Shelf:
    # (its __init__ is annotated, but makes an object of a class template: a template too)
    def __init__(self, b: int):
        self.box = Box(b)


w = Wrap(3)
print(w.inner, w.v, Wrap("s").inner.b, Shelf(2).box.v + 1)


class Bag:
    def __init__(self, *items):
        self.items = items
        self.size = len(items)


print(Bag(1, 2, 3).items, Bag("a", "b").items, Bag(4).size)


class Chain:
    # its __init__ makes another object of its argument types: of the specialization being made
    def __init__(self, n):
        self.n = n
        self.next = Chain(n - 1) if n > 0 else None

    def count(self) -> int:
        c = 0
        x = self
        while x is not None:
            c += 1
            x = x.next
        return c


class Tree:
    def __init__(self, v, depth: int):
        self.v = v
        self.kids = [Tree(v, depth - 1), Tree(v, depth - 1)] if depth > 0 else []


print(Chain(3).count(), Chain(0).count(), len(Tree("x", 2).kids), Tree(1.5, 1).kids[0].v)


class Scaled:
    # verbose is the constructor's alone: it changes no field's type, so it makes no layout
    def __init__(self, v, verbose):
        self.v = v
        if verbose:
            print("made", v)


objs = [Scaled(1, True), Scaled(2, 0), Scaled(3, "")]
print([o.v for o in objs])


class Builder:
    def __init__(self, sep):
        self.sep = sep
        self.parts: list[str] = []

    def add(self, x):
        self.parts.append(str(x))
        return self

    def build(self) -> str:
        return self.sep.join(self.parts)


print(Builder(", ").add(1).add("b").add(2.5).build(), Builder("-").add("x").build())


class Tally:
    # a default value is evaluated once, when the def runs: the objects of every specialization
    # share the list
    def __init__(self, v, seen: list[int] = []):
        seen.append(1)
        self.v = v
        self.seen = seen


t1 = Tally(1)
t2 = Tally("s")
t3 = Tally(2)
print(len(t1.seen), len(t2.seen), t1.seen is t3.seen, t1.seen is t2.seen)


class Den:
    # (no parameter: a template only because it makes an object of one, with no arguments)
    def __init__(self):
        self.box = Box(1)


class Room:
    def __init__(self, n):
        self.n = n
        self.den = Den()


print(Room(3).den.box.v, Room("x").n, Room(2.5).den.box.v + 1)


class Ping:
    # templates that make objects of each other with the same argument types: one Ping[int] and one
    # Pong[int], each holding the other's
    def __init__(self, v, depth):
        self.v = v
        self.pong = Pong(v, depth)


class Pong:
    def __init__(self, v, depth):
        self.v = v
        self.ping = Ping(v, depth - 1) if depth > 0 else None


pi = Ping(1, 2)
ps = Ping("s", 1)
print(pi.v, pi.pong.v, pi.pong.ping.pong.v, pi.pong.ping.pong.ping.pong.ping is None, ps.pong.ping.v, ps.pong.ping.pong.ping)


made = 0


def fresh() -> list[int]:
    global made
    made += 1
    return []


class Sack:
    # a specialization's methods share the default values of the template's, which the class
    # statement evaluates once: CPython's Sack.visit is one function, whatever the object's fields
    def __init__(self, value):
        self.value = value

    def visit(self, seen: list[int] = []) -> int:
        seen.append(1)
        return len(seen)

    def tally(self, acc: list[int] = fresh(), step=len("ab")) -> int:
        acc.append(step)
        return sum(acc)


g1 = Sack(1)
g2 = Sack("x")
print(g1.visit(), g2.visit(), g1.visit(), g2.visit(seen=[]))
print(g1.tally(), g2.tally(), g2.tally(step=10), g1.tally(), made)
