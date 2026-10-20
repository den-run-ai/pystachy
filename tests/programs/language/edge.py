from __future__ import annotations

log: list[str] = []


def note(tag: str, result: bool) -> bool:
    log.append(tag)
    return result


# short-circuit evaluation order
if note("a", False) and note("b", True):
    pass
if note("c", True) or note("d", True):
    pass
x = note("e", False) or note("f", True)
print(log, x)

# comprehension variables do not leak; outer names are untouched
i = 100
squares = [i * i for i in range(4)]
pairs = [[i, j] for j in [7, 8]]
nested = [[k * m for k in range(3)] for m in range(1, 3)]
print(i, squares, pairs, nested)

# strings that stress IR escaping and byte-level behaviour
weird = 'quote " backslash \\ tab \t nl \n bell \x07 nul-free'
print(weird, len(weird), repr(weird))
print("héllo wörld ✓", len("abc"))
print("", "|", "".join([]), "x".join(["a"]), "-".join(list("abc")))
print("a", "b", "c", sep="")
print("a", "b", sep=", ", end=".\n")
print()

# tree of objects of the same class
class Tree:
    def __init__(self, label: str):
        self.label = label
        self.kids: list[Tree] = []
        self.parent: Tree | None = None

    def add(self, label: str) -> Tree:
        t = Tree(label)
        t.parent = self
        self.kids.append(t)
        return t

    def depth(self) -> int:
        d = 0
        p = self.parent
        while p is not None:
            d += 1
            p = p.parent
        return d

    def walk(self, out: list[str]) -> None:
        out.append("  " * self.depth() + self.label)
        for k in self.kids:
            k.walk(out)


root = Tree("root")
a = root.add("a")
a.add("a1").add("a1x")
root.add("b").add("b1")
lines: list[str] = []
root.walk(lines)
print("\n".join(lines))
root.kids[0].kids[0].label = "renamed"
print(root.kids[0].kids[0].label, root.kids[1].parent is root, a.kids[0].kids[0].depth())

# deep recursion and big lists
def depth_sum(n: int) -> int:
    return 0 if n == 0 else n + depth_sum(n - 1)


print(depth_sum(900))
big = list(range(200000))
print(len(big), big[-1], sum(big), big[1000:1003])
del big[0]
big.pop()
print(len(big), big[0], big[-1])

# integer extremes and literal forms
print(9223372036854775807, -9223372036854775808, 0x7FFFFFFFFFFFFFFF, 1_0_0)
mixed: list[float] = [1.0, -0.0, 2.5e-3, 1e100]
print(mixed, max(mixed), min(mixed), sorted(mixed))

# tuple returns with mixed types
def stats(xs: list[float]) -> tuple[float, float, int]:
    return min(xs), max(xs), len(xs)


lo, hi, n = stats([3.5, -1.25, 9.0])
print(lo, hi, n, stats([2.0]))
