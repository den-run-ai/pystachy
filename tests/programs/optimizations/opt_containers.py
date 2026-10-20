# Optional items in lists, dicts and tuples, optional fields and globals: printed, compared,
# searched and sorted as CPython does
from dataclasses import dataclass


@dataclass
class Entry:
    name: str
    note: str | None = None
    tags: list[str] | None = None


class Box:
    label: str | None = None

    def __init__(self, items: list[int] | None = None):
        self.items = items

    def size(self) -> int:
        return len(self.items) if self.items is not None else -1


current: str | None = None


def set_current(s: str | None) -> None:
    global current
    current = s


def main() -> None:
    xs: list[str | None] = ["b", None, "a", None]
    print(xs, len(xs), xs[1], xs[0], None in xs, "a" in xs, "z" in xs, xs.count(None), xs.index(None), xs.index("a"))
    xs.remove(None)
    xs.append(None)
    xs.insert(0, "c")
    print(xs, xs == ["c", "b", "a", None, None], xs != ["c"], xs.pop(), xs)
    present = [x for x in xs if x is not None]
    present.sort()
    print(present, sorted(present, reverse=True), min(present), max(present))
    ys: list[str | None] = ["a", None]
    zs: list[str | None] = ["a", "b"]
    print(ys == zs, zs < ["a", "c"], ys < ["b"], ys == ["a", None])
    d: dict[str, str | None] = {"a": "x", "b": None}
    d["c"] = None
    d["d"] = "y"
    print(d, d["b"], d.get("a", "dflt"), d.get("q", "dflt"), "b" in d, len(d))
    for k, v in d.items():
        print(k, v, v is None)
    print(d == {"a": "x", "b": None, "c": None, "d": "y"}, d.pop("b"), d)
    t: tuple[str | None, int] = ("a", 1)
    t2: tuple[str | None, int] = (None, 2)
    print(t, t2, t == t2, t < ("b", 0), t2 == (None, 2), [t, t2])
    a, n = t2
    print(a, n)
    nested: list[list[int] | None] = [[1], None, []]
    print(nested, [len(v) for v in nested if v is not None], nested[0] == [1], nested[1] is None)
    e1 = Entry("one")
    e2 = Entry("two", "a note", ["t"])
    e3 = Entry("one")
    print(e1, e2, e1 == e3, e1 == e2, repr(e2.note), e1.note is None)
    e1.note = "set"
    e1.tags = []
    print(e1, e1 == e3)
    b = Box()
    print(b.label, b.items, b.size(), Box([1, 2]).size())
    b.label = "lbl"
    print(b.label, b.label.upper())
    print(current)
    set_current("now")
    print(current, current == "now")
    set_current(None)
    print(current)


main()
