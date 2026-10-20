# Bound methods as values: o.m of an object (also self.m) and of a str, list, dict or file is the
# method bound to it, called later as o.m(...) would be; T.m read through builtin type T takes the
# value first (str.lower). They pass to templates, become Callables, and compare equal where they
# are one method of one object
from dataclasses import dataclass
from typing import Callable

from mods.shapes import Circle


class Acc:
    def __init__(self, base: int) -> None:
        self.base = base
        self.log: list[str] = []

    def add(self, x: int) -> int:
        self.log.append(f"add {x}")
        return self.base + x

    def twice(self) -> Callable[[int], int]:
        f = self.add
        return lambda x: f(f(x))


def apply(f, x):
    return f(x)


a = Acc(10)
b = Acc(100)
fa = a.add
print(fa(1), apply(a.add, 2), apply(b.add, 3), [g(4) for g in [a.add, b.add]])
print(a.twice()(1), a.log)
print(a.add.__name__, a.add.__qualname__, "".join.__name__, "".join.__qualname__, a.log.append.__qualname__)
print(fa == a.add, fa == b.add, fa != b.add)
cbs: list[Callable[[int], int]] = [a.add, lambda x: -x, abs]
print([c(-3) for c in cbs])
words = ["b", "A", "c"]
print(sorted(words, key=str.lower), str.lower("ABC"), str.join("+", words), "-".join(words), ", ".join(sorted(words)))
out: list[str] = []
put = out.append
put("x")
put("y")
d = {"k": 1}
get = d.get
print(out, get("k"), get("z"), get("z", 7))
up = "MiXed".lower
cnt = "banana".count
print(up(), cnt("a"), cnt("an"))
o: Acc | None = None
try:
    h = o.add
except AttributeError as e:
    print("AttributeError:", e)


class Late:
    def __init__(self) -> None:
        f = self.get
        try:
            print(f())
        except AttributeError as e:
            print("AttributeError:", e)
        self.v = 5

    def get(self) -> int:
        return self.v


print(Late().get())


@dataclass
class P:
    x: int

    def scaled(self, k: int) -> int:
        return self.x * k


ps = [P(1), P(2)]
print([p.scaled for p in ps][1](10))

c = Circle(2.0)
show = c.__repr__
print(show(), show.__qualname__)


class Button:
    def __init__(self, label: str) -> None:
        self.label = label
        self.on_click = self.default_click
        self.clicks = 0

    def default_click(self, n: int) -> str:
        self.clicks += n
        return f"{self.label} clicked {self.clicks}"


btn = Button("ok")
print(btn.on_click(2), btn.on_click(3))


def side() -> str:
    print("side")
    return "x"


# a method read through its type raises for None once the other arguments are evaluated
maybe_s: str | None = None
try:
    print(str.replace(maybe_s, side(), "y"))
except TypeError as e:
    print("TypeError:", e)
# list.sort and dict.update as values too
nums = [3, 1, 2]
sorter = nums.sort
sorter()
dd = {"a": 1}
upd = dd.update
upd({"b": 2})
srt = list.sort
srt(nums, reverse=True)
print(nums, dd)
