# Live references compare and hash as their referents do (CPython's weakref_richcompare
# and weakref_hash). Every referent stays alive: each function reads its referents last, as
# a native local is a root only until its last use (a CPython local's reference lasts to the
# end of its scope), so ref(x) of an x read nowhere after could be cleared at once.
import re
import _ast
from _weakref import ReferenceType, ref


class Item:
    def __init__(self, value: int):
        self.value = value


class Sub(Item):
    pass


class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def __eq__(self, other: "Point") -> bool:
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))


class Unhashable:
    def __init__(self, x: int):
        self.x = x

    def __eq__(self, other: "Unhashable") -> bool:
        return self.x == other.x


def names() -> None:
    item = Item(1)
    r = ref(item)
    print(type(r).__name__, type(r).__qualname__, type(r).__module__)
    print(ref.__name__, ReferenceType.__name__, isinstance(r, ref), isinstance(r, ReferenceType))
    # CPython's reference has no attributes of its own: no fields, no __dict__
    print(hasattr(r, "_handle"), hasattr(r, "_hash"), hasattr(r, "__dict__"), hasattr(r, "__weakref__"))
    print(hasattr(r, "__call__"), hasattr(r, "__hash__"), hasattr(r, "__class_getitem__"))
    # __init__ checks its arguments and leaves the reference to its first referent
    other = Item(2)
    r.__init__(other)
    r.__init__(other, None)
    print(r() is item, r() is other)


def maybe(flag: bool, item: Item) -> ReferenceType[Item] | None:
    return ref(item) if flag else None


def identity_equality() -> None:
    a = Item(1)
    b = Item(1)
    ra = ref(a)
    twin = ref(a)
    rb = ref(b)
    # Item has object's identity equality and hash
    print(ra == twin, ra != twin, ra == rb, ra != rb, ra == ra, ra != ra)
    print(hash(ra) == hash(a), hash(twin) == hash(ra), hash(ra) == hash(ra))
    refs = {ra, twin, rb}
    print(len(refs), ra in refs, ref(b) in refs)
    counts: dict[ReferenceType[Item], int] = {}
    for r in [ra, rb, twin, ra]:
        counts[r] = counts.get(r, 0) + 1
    print(counts[ref(a)], counts[ref(b)])
    # an optional reference compares with None as CPython's does: never equal
    some = maybe(True, a)
    none = maybe(False, a)
    print(some == None, some != None, none == None, none != None, None == some, None != some)
    print("kept", a.value + b.value)


def value_equality() -> None:
    p = Point(1, 2)
    q = Point(1, 2)
    s = Point(2, 1)
    rp = ref(p)
    rq = ref(q)
    rs = ref(s)
    print(rp == rq, rp != rq, rp == rs, rp != rs)
    print(hash(rp) == hash(rq), hash(rp) == hash((1, 2)), hash(rs) == hash((2, 1)))
    table: dict[ReferenceType[Point], str] = {rp: "p", rs: "s"}
    print(table[rq], table[ref(s)], len(table))
    # the hash is computed once: a later change of the referent does not change it
    before = hash(rp)
    p.x = 5
    print(hash(rp) == before, hash(rp) == hash(p), rp == rq)
    u = Unhashable(1)
    ru = ref(u)
    print(ru == ref(u))
    try:
        print(hash(ru))
    except TypeError as e:
        print("TypeError", e)
    print("kept", p.x + q.x + s.x + u.x)


def reprs() -> None:
    item = Item(1)
    r = ref(item)
    text = repr(r)
    print(re.sub("0x[0-9a-f]+", "ADDR", text), str(r) == text)
    addrs = re.findall("0x[0-9a-f]+", text)
    print(len(addrs), addrs[0] != addrs[1], addrs[1] in repr(item))
    base: Item = Sub(2)
    print(re.sub("0x[0-9a-f]+", "ADDR", repr(ref(base))))
    node = _ast.Constant(1)
    print(re.sub("0x[0-9a-f]+", "ADDR", repr(ref(node))))
    print(re.sub("0x[0-9a-f]+", "ADDR", repr(node)), type(node).__module__)
    print("kept", item.value + base.value, node.value)


names()
identity_equality()
value_equality()
reprs()
