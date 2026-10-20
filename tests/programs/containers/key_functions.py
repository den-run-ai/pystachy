# key= of sorted(), list.sort(), min() and max(), with a function of the program or a builtin: the
# keys are computed in order, and the sort compares them as CPython does (stably, reverse= too)
import math


def second(p):
    return p[1]


def neg(x):
    return -x


def lower(s: str) -> str:
    return s.lower()


def parity(n):
    return n % 2


def by_len_then_text(s):
    return (len(s), s)


class Box:
    def __init__(self, v: int) -> None:
        self.v = v

    def __lt__(self, o: "Box") -> bool:
        return self.v < o.v

    def __gt__(self, o: "Box") -> bool:
        return self.v > o.v

    def __repr__(self) -> str:
        return f"Box({self.v})"


def boxed(n):
    return Box(n % 5)


words = ["pear", "Fig", "banana", "apple", "Kiwi", "fig"]
print(sorted(words, key=len), sorted(words, key=lower), sorted(words, key=len, reverse=True))
print(sorted(words, key=by_len_then_text), sorted(words, reverse=True, key=lower))
pairs = [("a", 3), ("b", 1), ("c", 3), ("d", 2), ("e", 1)]
print(sorted(pairs, key=second), sorted(pairs, key=second, reverse=True))
nums = [5, 3, 8, 1, 9, 2, 7, 4, 6, 0]
print(sorted(nums, key=neg), sorted(nums, key=parity), sorted(nums, key=parity, reverse=True))
print(sorted(range(10), key=parity), sorted((n * n for n in range(-3, 4)), key=neg))
print(sorted([2.5, -1.0, 0.5], key=abs), sorted(["b", "A", "c"], key=str), sorted([3, 1, 2], key=None))
print(sorted(nums, key=boxed))
xs = list(words)
xs.sort(key=lower)
print(xs)
xs.sort(key=len, reverse=True)
print(xs)
ys = [3, -4, 1, -2]
ys.sort(key=abs)
print(ys)
ys.sort(key=None, reverse=True)
print(ys)
print(min(words, key=len), max(words, key=len), min(pairs, key=second), max(pairs, key=second))
print(min(nums, key=neg), max(nums, key=parity), min([2.5, -3.0, 1.0], key=abs), max("hello", key=ord))
print(min(3, -7, 5, key=abs), max("ab", "c", "def", key=len), min(4, 9, key=neg), max(Box(1), Box(4), key=repr))
print(min((n for n in [4, 8, 2]), key=neg), max(range(5), key=parity), min({"x": 3, "y": 1}, key=lower))
empty: list[str] = []
print(sorted(empty, key=len), min([1], key=math.sqrt), max(nums, key=boxed))
long = list(range(200))
long.sort(key=parity)
print(long[:5], long[100:105])
print(sorted(long, key=neg)[:3])
