# An object with __index__ (an IntEnum member too) where a builtin method of a list, tuple or
# str takes an integer, and as enumerate()'s start: CPython asks it for its index once every
# argument is evaluated.
from enum import IntEnum


class Level(IntEnum):
    ONE = 1
    TWO = 2


class Two:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def __index__(self) -> int:
        self.log.append("index")
        return 2


def noted(log: list[str], v: int) -> int:
    log.append("arg")
    return v


log: list[str] = []
two = Two(log)
xs = [10, 20, 30, 40, 50]
print(xs.pop(Level.ONE), xs.pop(two), xs)
xs.insert(two, noted(log, 8))
xs.insert(Level.ONE, 7)
print(xs, log)
ys = [1, 2, 3, 1, 2, 3]
print(ys.index(3, Level.ONE), ys.index(1, two), ys.index(2, Level.ONE, two))
s = "abcabcabc"
print(s.find("c", Level.ONE), s.find("c", two), s.count("b", Level.ONE, two), s.index("b", two), s.startswith("bc", Level.ONE))
print("x".center(two) + "|", "7".zfill(Level.TWO), "a,b,c".split(",", Level.ONE))
tup: tuple[int, ...] = (5, 6, 7, 5)
print(tup.index(5, Level.ONE), tup.index(7, two))
for k, ch in enumerate("ab", Level.TWO):
    print(k, ch)
for k, ch in enumerate("ab", start=two):
    print(k, ch)
print(log)
