# set elements whose __eq__ changes the set an insertion is looking its key up in: it adds an
# element (into the dummy the insertion's probes passed, which the insertion must not then
# overwrite), adds and removes one, empties the set (with __eq__ True: the key counts as found,
# as CPython's set_add_entry has it, else the insertion starts again), keeps one element (the
# small table that CPython rebuilds in place), or raises; through s.add(), s.update(), s |= t,
# set displays, comprehensions and sets and frozensets built from lists that the __eq__ grows


log: list[str] = []


class E:
    # an element of hash h; once armed with a set and an action, its next __eq__ does the action
    # to the set, and once given a list to grow, it extends that list with extra
    def __init__(self, name: str, h: int) -> None:
        self.name = name
        self.h = h
        self.action = ""
        self.target: set["E"] | None = None
        self.extra: list["E"] = []
        self.grow: list["E"] | None = None

    def arm(self, action: str, target: set["E"], extra: list["E"]) -> None:
        self.action = action
        self.target = target
        self.extra = extra

    def __hash__(self) -> int:
        return self.h

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, E):
            return False
        log.append(f"{self.name}={other.name}")
        g = self.grow
        if g is not None:
            self.grow = None
            g.extend(self.extra)
        t = self.target
        act = self.action
        if t is None:
            return self.name == other.name
        self.target = None
        self.action = ""
        if act == "add":
            for x in self.extra:
                t.add(x)
        elif act == "addrm":
            for x in self.extra:
                t.add(x)
                t.discard(x)
        elif act == "rm":
            for x in self.extra:
                t.discard(x)
        elif act == "clear":
            t.clear()
        elif act == "clear-equal":
            t.clear()
            return True
        elif act == "keep":
            t.intersection_update([self])
        elif act == "raise":
            raise ValueError(f"__eq__ of {self.name}")
        return self.name == other.name

    def __repr__(self) -> str:
        return self.name


def show(label: str, s: set[E]) -> None:
    # the set as a loop sees it, the __eq__ calls since the last show, and its elements popped
    # one by one: as many as len() says
    print(label, len(s), list(s), log)
    log.clear()
    n = len(s)
    popped: list[str] = []
    while s and len(popped) <= n:
        popped.append(s.pop().name)
    print("  popped", len(popped) == n, sorted(popped))


def base(h: int) -> set[E]:
    # a and b of hash h, a then removed: its slot is a dummy that b's probes pass
    a = E("a", h)
    b = E("b", h)
    s = {a, b}
    s.discard(a)
    log.clear()
    return s


def elem(s: set[E], name: str) -> E:
    return [x for x in s if x.name == name][0]


for h in [1, 9, -3]:
    # s.add(c): b's __eq__ adds d, into a's dummy, which c's insertion passed
    s = base(h)
    elem(s, "b").arm("add", s, [E("d", h)])
    s.add(E("c", h))
    show(f"add/add {h}", s)
    # ... adds and removes d: the dummy stays one, c goes there
    s = base(h)
    elem(s, "b").arm("addrm", s, [E("d", h)])
    s.add(E("c", h))
    show(f"add/addrm {h}", s)
    # ... adds an element of another hash, d of this one, and removes b
    s = base(h)
    b = elem(s, "b")
    b.arm("add", s, [E("x", h + 1), E("d", h)])
    s.add(E("c", h))
    s.discard(b)
    show(f"add/add2 {h}", s)
    # ... removes b itself: the slot it compared changed, and c's insertion starts again
    s = base(h)
    b = elem(s, "b")
    b.arm("rm", s, [b])
    s.add(E("c", h))
    show(f"add/rm {h}", s)
    # ... empties the set, and c is not b: c is inserted into what is left
    s = base(h)
    elem(s, "b").arm("clear", s, [])
    s.add(E("c", h))
    show(f"add/clear {h}", s)
    # ... empties the set and says c is b: c counts as found, nothing is inserted
    s = base(h)
    elem(s, "b").arm("clear-equal", s, [])
    s.add(E("c", h))
    show(f"add/clear-equal {h}", s)
    # ... raises: c is not inserted, d (added before the raise) is
    s = base(h)
    elem(s, "b").arm("add", s, [E("d", h)])
    s.add(E("c", h))
    elem(s, "d").arm("raise", s, [])
    try:
        s.add(E("e", h))
    except ValueError as ex:
        print("ValueError", ex)
    show(f"add/raise {h}", s)

# a small set (8 slots) rebuilt in place: b's __eq__ keeps only b, which stays in its slot, and
# the insertion or lookup goes on (CPython's table is the same); in a larger table, which the
# rebuild makes small, it starts again; where b moves to another slot, too
for n in [0, 20]:
    b = E("b", 1)
    s = {b, E("e", 2)}
    for i in range(n):
        s.add(E(f"f{i}", 100 + i))
    log.clear()
    b.arm("keep", s, [])
    s.add(E("c", 1))
    show(f"add/keep {n}", s)
    b = E("b", 1)
    s = {b, E("e", 2)}
    for i in range(n):
        s.add(E(f"f{i}", 100 + i))
    log.clear()
    b.arm("keep", s, [])
    print(E("c", 1) in s, E("b", 1) in s, len(s), log)
    log.clear()
s = base(1)
elem(s, "b").arm("keep", s, [])
s.add(E("c", 1))
show("add/keep moved", s)
s = base(1)
elem(s, "b").arm("keep", s, [])
print(E("c", 1) in s, E("b", 1) in s, log)
log.clear()

# s.update() of a list and of a set, and s |= t, whose insertions run the __eq__ that grows s
s = base(5)
elem(s, "b").arm("add", s, [E("d", 5), E("y", 6)])
s.update([E("c", 5), E("b", 5), E("e", 5)])
show("update(list)", s)
s = base(5)
elem(s, "b").arm("add", s, [E("d", 5)])
t = {E("c", 5), E("e", 7)}
s.update(t)
show("update(set)", s)
s = base(5)
elem(s, "b").arm("addrm", s, [E("d", 5)])
s |= {E("c", 5), E("e", 7)}
show("|=", s)
s = base(5)
elem(s, "b").arm("raise", s, [])
try:
    s |= {E("c", 5)}
except ValueError as ex:
    print("ValueError", ex)
show("|= raise", s)
s = base(5)
elem(s, "b").arm("raise", s, [])
try:
    s.update([E("q", 6), E("c", 5), E("r", 7)])
except ValueError as ex:
    print("ValueError", ex)
show("update(list) raise", s)

# displays, comprehensions, set() and frozenset() of a list: the set being made is out of the
# __eq__'s reach, but the list it is made from grows, and the __eq__ of an element may raise
for mk in ["set", "frozenset", "comprehension", "display"]:
    p = E("p", 3)
    q = E("q", 3)
    xs = [p, q, E("p", 3)]
    p.grow = xs
    p.extra = [E("late", 3), E("q", 3), E("x", 4)]
    if mk == "set":
        r = set(xs)
    elif mk == "frozenset":
        r = set(frozenset(xs))
    elif mk == "comprehension":
        r = {x for x in xs if x.name != "x"}
    else:
        r = {p, q, E("late", 3), E("p", 3)}
    print(mk, len(xs), len(r), list(r), log)
    log.clear()
    p = E("p", 3)
    p.action = "raise"
    p.target = set()
    try:
        if mk == "set":
            r = set([p, E("q", 3), E("r", 3)])
        elif mk == "frozenset":
            r = set(frozenset([p, E("q", 3)]))
        elif mk == "comprehension":
            r = {x for x in [p, E("q", 3)]}
        else:
            r = {p, E("q", 3)}
        print(len(r))
    except ValueError as ex:
        print("ValueError", ex)
    print(log)
    log.clear()

# a set that the __eq__ of its elements adds to while a loop adds to it
acc: set[E] = set()
for rnd in range(3):
    a = E("a", rnd)
    b = E("b", rnd)
    acc = {a, b}
    acc.discard(a)
    b.arm("add", acc, [E("d", rnd), E("g", rnd)])
    for x in [E("c", rnd), E("c", rnd), E("b", rnd)]:
        acc.add(x)
    show(f"loop {rnd}", acc)
