# pystachy: dynamic-any
# An Any value where a builtin method of a typed list, tuple or str takes an integer, and as
# enumerate()'s start: a bool counts as 0 or 1 and an object gives its __index__(), asked once
# every argument is evaluated; None is a str method's omitted bound; another value raises
# CPython's TypeError (#1395).
from typing import Any


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
t: Any = True
two: Any = Two(log)
one: Any = 1
none: Any = None
xs: list[int] = [10, 20, 30, 40, 50]
print(xs.pop(t), xs.pop(two), xs.pop(one), xs)
xs.insert(t, 7)
xs.insert(two, noted(log, 8))
print(xs, log)
ys: list[int] = [1, 2, 3, 1, 2, 3]
print(ys.index(3, t), ys.index(1, two), ys.index(2, one, two))
s = "abcabcabc"
print(s.find("c", t), s.find("c", two), s.find("a", one, none), s.find("a", none, two), s.count("b", t, two), s.index("b", two))
print(s.startswith("bc", t), s.endswith("ab", none, two), s.rfind("a", none, t))
print("x".center(two) + "|", "7".zfill(two), "a,b,c".split(",", t), "a b c".rsplit(None, one))
tup: tuple[int, ...] = (5, 6, 7, 5)
print(tup.index(5, t))
for bad in ["pop", "insert", "index", "find"]:
    text: Any = "text"
    try:
        if bad == "pop":
            xs.pop(text)
        elif bad == "insert":
            xs.insert(text, 1)
        elif bad == "index":
            ys.index(1, text)
        else:
            s.find("a", text)
    except TypeError as e:
        print(bad, "TypeError:", e)
try:
    xs.pop(none)
except TypeError as e:
    print("TypeError:", e)
print(log)
for k, ch in enumerate("ab", t):
    print(k, ch)
for k, ch in enumerate("ab", start=two):
    print(k, ch)
try:
    for k, ch in enumerate("ab", none):
        print(k, ch)
except TypeError as e:
    print("TypeError:", e)
print(log)
