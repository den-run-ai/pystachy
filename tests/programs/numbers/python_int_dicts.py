# pystachy: python-int
# Dicts whose values are ints hold ints past 64 bits: stores (subscripts, displays, comprehensions,
# setdefault(), update(), copies), reads (subscripts, get(), pop(), setdefault(), iteration,
# values()), augmented assignment, del, repr() and comparisons, also with dicts of floats and
# bools, and get() and pop() of a key that may be None or is a bool.
memo: dict[int, int] = {0: 0, 1: 1}


def fib(n: int) -> int:
    if n in memo:
        return memo[n]
    r = fib(n - 1) + fib(n - 2)
    memo[n] = r
    return r


print(fib(150), memo[100], max(memo.values()), len(memo))
big = 2 ** 64
d = {"a": big, "b": 1, "c": -big}
print(d, d["a"] * 2, d.get("c"), d.get("x", big + 1), d.get("b", 0))
d["b"] += big
d["a"] -= big
print(d["a"], d["b"], d)
counts: dict[str, int] = {}
for w in ["x", "y", "x"]:
    counts[w] = counts.get(w, 0) + big
print(counts, sum(counts.values()), sorted(counts.values()))
tally = {}
seen = {}
for w in ["x", "y", "x"]:
    tally[w] = tally.get(w, 0) + big
    seen.setdefault(w, -big)
    seen[w] -= 1
print(tally, seen)
print(d.setdefault("z", 3 * big), d.setdefault("z", 0), d.pop("z"), d.pop("q", -1), d.pop("c", 0))
sq = {k: k ** 30 for k in range(3)}
print(sq, sq == {0: 0, 1: 1, 2: 2 ** 30}, {1: big} == {1: big}, {1: big} == {1: big + 1}, {1: big} != {1: 0})
cubes = {k: big * k for k in range(3)}
names = {str(k): 2 ** (62 + k) for k in range(3)}
print(cubes, names, {k: (big if k else 1) for k in range(2)}, cubes[2] - cubes[1])
e = dict(d)
e.update({"w": big * big})
f = e.copy()
f["a"] = -1
print(e, f, e == f)
for k, v in e.items():
    print(k, v, v > 2 ** 63)
for v in e.values():
    print(v - 1)
print(list(e.values()), big in e.values(), (big + 1) in e.values(), [k for k in e if e[k] >= big])
del e["w"]
print(e, len(e), e.get("w"))
# bool keys of a dict of int keys, nested dicts, a field, a function that changes a dict, boxes
flags: dict[int, int] = {1: 5}
flags[True] += big
print(flags, flags[True], flags.get(1))
nested: dict[str, dict[str, int]] = {"x": {"y": big * 3}}
nested["x"]["z"] = nested["x"]["y"] // 3 + 1
print(nested, nested["x"]["z"] - big)


class Ledger:
    def __init__(self) -> None:
        self.totals: dict[str, int] = {}

    def add(self, k: str, v: int) -> None:
        self.totals[k] = self.totals.get(k, 0) + v


book = Ledger()
for i in range(3):
    book.add("a", big << i)
print(book.totals, book.totals["a"] == 7 * big)


def double(m: dict[str, int]) -> None:
    for k in m:
        m[k] *= 2


double(book.totals)
print(book.totals, book.totals.pop("a", None), book.totals.pop("a", None), book.totals)
z = {"p": -big, "q": 0}
print(z.get("p"), z.get("missing"), z.setdefault("q", big), z.setdefault("r", -2 ** 63), z)
z.clear()
z["s"] = big
print(z, -2 ** 63 in {"t": -2 ** 63}.values())
# get() and pop() of a key that may be None (an int or a bool) or is a bool, del, and dicts of
# floats and bools
opt: int | None = 1
nums = {1: big, 2: 3}
print(nums.get(opt, 0), nums.get(opt), nums.get(opt, None), nums.get(True, None), nums.get(True), nums.get(True, 7))
bopt: bool | None = True
bnone: bool | None = None
bfalse: bool | None = False
print(nums.get(bopt, 0), nums.get(bopt, -big), nums.get(bnone, 4), nums.get(bnone, -big), nums.get(bfalse, 6))
print(nums.get("x" == "y", None), nums.pop(True, None), nums, nums.pop(True, 9))
nums[1] = -big
del nums[2]
floats: dict[int, float] = {1: -1.8446744073709552e19}
flags2: dict[int, bool] = {1: True}
print(nums, nums == floats, floats == nums, nums == {1: -9.223372036854776e18}, nums != flags2, {1: -2 ** 63} == {1: -9.223372036854776e18})
