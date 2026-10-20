# sum(), min() and max() of a generator expression or of range(), zip(), map(), ... take the items
# as they come (#88): what they return, the order in which the iterator is made, sum's start is
# evaluated and the items are produced, what an item that raises stops, and the errors.
import math


def it(xs: list[int]) -> list[int]:
    print("iterable made")
    return xs


def start(v: int) -> int:
    print("start evaluated")
    return v


def item(x: int) -> int:
    print("item", x)
    return x


class Pair:
    def __init__(self, a: int, b: str) -> None:
        self.a = a
        self.b = b

    def __lt__(self, other: "Pair") -> bool:
        return self.a < other.a

    def __gt__(self, other: "Pair") -> bool:
        return self.a > other.a


xs = [3, -1, 4, 1, -5, 9, 2, 6]
fs = [0.1] * 10
words = ["pear", "fig", "apple", "kiwi"]
flags = [True, False, True, True]

print(sum(x for x in xs), sum(x * x for x in xs if x > 0), sum(range(10)), sum(range(10, 0, -3)))
print(sum(f for f in fs), sum(x / 10 for x in range(10)), sum(f for f in [1e100, 1.0, -1e100, 1.0]))
print(sum((x for x in xs), 100), sum((x for x in xs), 0.5), sum((f for f in fs), 5), sum((f for f in fs), 0.25))
print(sum(b for b in flags), sum((b for b in flags), 1.5), sum(map(abs, xs)), sum(filter(None, xs)))
print(sum(x for x in range(0)), sum((f for f in fs if f > 1.0), 2.0), sum((x for x in range(0)), 7))
print(sum(f for f in [math.inf, 1.0]), sum(f for f in [math.inf, -math.inf]), sum(f for f in [math.nan, 1.0]))
print(sum((f for f in [2.0**53, 1.0, 1.0]), 0), sum(f for f in [1e16, 1.0, -1e16]))

print(max(x for x in xs), min(x for x in xs), max(range(5)), min(range(5, 0, -2)), max(x % 7 for x in range(100)))
print(max(f for f in [0.5, 2.5, -1.0]), min(f * 2 for f in fs), max(w for w in words), min(w.upper() for w in words))
print(max(b for b in flags), min(b for b in flags), max(len(w) for w in words), min(map(abs, xs)))
print(max(f for f in [math.nan, 1.0, 2.0]), max(f for f in [1.0, math.nan, 2.0]), min(f for f in [3.0, math.nan, 1.0]))
print(max(enumerate(words)), min(zip(xs, words)), max((x, -x) for x in xs))
print(max(Pair(x, str(x)) for x in xs).b, min(Pair(x, w) for x, w in zip(xs, words)).b)
print(max((w for w in words), key=len), min((x for x in xs), key=abs))
print(sum(max(y for y in range(x)) for x in range(1, 6)), [min(c for c in w) for w in words])

for name in ["max", "min"]:
    try:
        print(max(x for x in range(0)) if name == "max" else min(x for x in xs if x > 100))
    except ValueError as e:
        print("ValueError:", e)

# the iterator is made, then the start evaluated, then the items produced, one at a time
print(sum((item(x) for x in it([1, 2, 3])), start(10)))
print(max(item(x) for x in it([2, 7, 1])), min(item(x) for x in it([5, 4])))

# an item that raises stops the reduction there: the items after it are never produced
try:
    print(sum(item(12 // (2 - x)) for x in range(4)))
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
try:
    print(max(item(12 // (2 - x)) for x in range(4)))
except ZeroDivisionError as e:
    print("ZeroDivisionError:", e)
