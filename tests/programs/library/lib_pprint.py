# pprint (lib/pprint.py): pformat(), pprint(), pp(), saferepr(), isreadable(), isrecursive() and
# PrettyPrinter on values of static types, with CPython's output: tuples of items of several
# types, objects, sets, sorted and unsorted dicts, the options and the streams.
import io
import sys
import pprint


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return "Point(%d, %d)" % (self.x, self.y)


class Opaque:
    def __repr__(self) -> str:
        return "<Opaque>"


class Ranked:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return "Ranked(%d)" % self.n

    def __lt__(self, other: "Ranked") -> bool:
        return self.n > other.n

    def __hash__(self) -> int:
        return self.n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ranked) and other.n == self.n


# heterogeneous tuples of one to seventeen items
print(pprint.pformat((1,)))
print(pprint.pformat((1, "a")))
print(pprint.pformat((1, "a", 2.5, None, True), width=10))
print(pprint.pformat((1, "a", 2.5, None, True, b"x", [1], {"k": 2}), width=12))
print(pprint.pformat((1, "a", 2.5, None, True, b"x", [1], {"k": 2}, (3,)), width=12))
t9 = (1, "a", 2.5, None, True, b"x", [1], {"k": 2}, (3,))
print(pprint.pformat(t9, width=30, compact=True))
print(pprint.pformat(t9))
print(pprint.pformat(t9, depth=1))
print(pprint.saferepr(t9), pprint.isreadable(t9))
# runtime-length tuples
rt = tuple([i * 3 for i in range(40)])
print(pprint.pformat(rt, width=30, compact=True))
print(pprint.pformat(tuple(["only"]), width=3))
ts: list[tuple[str, int]] = [("alpha", 1), ("beta", 22), ("gamma", 333)]
print(pprint.pformat(ts, width=14))
# objects
pts = [Point(i, i * i) for i in range(6)]
print(pprint.pformat(pts, width=30))
print(pprint.pformat({"p": Point(1, 2)}), pprint.isreadable(Point(1, 2)), pprint.isreadable(Opaque()))
print(pprint.isreadable([Opaque()]), pprint.isreadable({"k": [Opaque()]}), pprint.isreadable((1, Opaque())))
print(pprint.pformat({Ranked(1): "one", Ranked(3): "three", Ranked(2): "two"}))
print(pprint.pformat({Ranked(1), Ranked(3), Ranked(2)}, width=5))
# unions and optionals
mixed: list[int | str] = [1, "two", 3, "four"]
print(pprint.pformat(mixed, width=8))
opt: list[str | None] = ["a", None, "c"]
print(pprint.pformat(opt, width=6))
print(pprint.pformat({(2, "b"): [1], (1, "z"): [2], (1, "a"): [3]}))
print(pprint.pformat({b"b": 1, b"a": 2}))
print(pprint.pformat({"b", "a", "c"}, width=5), pprint.pformat(frozenset({"b", "a"}), width=5))
# options
d = {"zeta": [1, 2, 3], "alpha": [4, 5, 6], "mid": [7]}
print(pprint.pformat(d, width=20))
print(pprint.pformat(d, width=20, sort_dicts=False))
print(pprint.pformat(d, width=20, indent=3))
print(pprint.pformat(d, width=20, indent=0))
print(pprint.pformat(d, width=22, compact=True))
print(pprint.pformat([[1, [2, [3, [4]]]]] if False else [[[[1]]]], depth=2))
print(pprint.pformat({"a": {"b": {"c": {"d": 1}}}}, depth=2))
print(pprint.pformat([10000000, -2000000, 300], underscore_numbers=True))
print(pprint.pformat({"n": 1234567, "big": 9007199254740993}, underscore_numbers=True, width=10))
print(pprint.pformat([True, False], underscore_numbers=True))
# streams
pprint.pprint(d, width=20)
pprint.pp(d, width=20)
pprint.pp({"b": 1, "a": 2})
pprint.pprint({"b": 1, "a": 2})
buf = io.StringIO()
pprint.pprint(d, buf, 2, 25)
pprint.pp(d, buf, width=18)
pprint.pprint(d, stream=buf, compact=True, width=30)
print(buf.getvalue(), end="")
printer = pprint.PrettyPrinter(indent=2, width=24, stream=buf)
printer.pprint(["x" * 10, "y" * 10, "z" * 10])
print(printer.pformat(d))
print(printer.isreadable(d), printer.isrecursive(d), printer.format(d, {}, 0, 0))
print(printer.format([[1]], {}, 1, 0), printer.format(Opaque(), {}, None, 0))
print(buf.getvalue().count("\n"))
p0 = pprint.PrettyPrinter()
p0.pprint({"k": [1, 2]})
pprint.pprint({"k": 1}, sys.stdout)
print(pprint.saferepr({"b": [1], "a": [2]}), pprint.saferepr("s"), pprint.saferepr(1.5))
