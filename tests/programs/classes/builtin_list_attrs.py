# A list subclass with attributes, a class attribute, a property and __str__ alone (repr() is
# list's), and one with __slots__: the attributes live after the list's header, so they survive
# every list operation, and the objects are unhashable, as lists are.


class Rows(list[str]):
    kind = "rows"

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.count = 0

    def add(self, row: str) -> "Rows":
        self.append(row)
        self.count += 1
        return self

    @property
    def last(self) -> str:
        return self[-1] if self else ""

    def __str__(self) -> str:
        return self.name + ":" + ",".join(self)


class Slotted(list[int]):
    __slots__ = ("label",)

    def __init__(self, label: str) -> None:
        self.label = label


r = Rows("r").add("a").add("b")
print(r, repr(r), r.last, r.count, r.kind, Rows.kind, r.name, f"{r}|{r!r}", "%s %r" % (r, r))
print(hasattr(r, "name"), hasattr(r, "missing"), getattr(r, "count"), type(r).__name__, r.__class__.__name__)
print(isinstance(r, Rows), isinstance(r, list), isinstance(r, str), type(r) is Rows, type(r) == list)
setattr(r, "count", 10)
print(r.count)
s = Slotted("s")
s.extend([3, 4])
print(s, s.label, len(s), hasattr(s, "__dict__"))
store = {"a": r, "b": Rows("q")}
pairs = [(r, 1), (Rows("z").add("y"), 2)]
print(store["a"].count, [str(v) for v in store.values()], [str(p[0]) for p in pairs], pairs[1][0].last)
try:
    print({r})
except TypeError as e:
    print("TypeError", e)
print(r == ["a", "b"], r.count == 10, r.index("b"), r.pop(), r, len(r))
r.clear()
print(r, bool(r), r.last == "", r.name)
