# == and != with None: False and True for a number, bool, str or container (its other operand
# still evaluated, in order), None's own identity for an optional value, and the class's
# __eq__ or __ne__ where it defines one
from dataclasses import dataclass
from typing import NamedTuple


def val(x: int) -> int:
    print("val", x)
    return x


def fl() -> float:
    print("fl")
    return 2.5


class Plain:
    def __init__(self, v: int) -> None:
        self.v = v


class Eq:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, o: "Eq") -> bool:
        print("Eq.__eq__", o is None)
        return o is not None and self.v == o.v


class Ne:
    def __ne__(self, o: "Ne") -> bool:
        print("Ne.__ne__")
        return o is None


@dataclass
class D:
    a: int


class P(NamedTuple):
    x: int
    y: int


print(val(1) == None, None == val(2), val(3) != None, None != val(4))
print(fl() == None, None != fl())
print(True == None, None == False, 1.5 != None, None == 3, 3 == None, 0 != None)
print(9223372036854775807 == None, None != -9223372036854775807 - 1, float("nan") == None, "é☃𝄞" != None)
xs = [1]
print("" == None, None != "a", xs == None, None == {1: 2}, () != None, (1, "a") == None)
print(1 < val(5) == None, None == val(6) < 9, None != val(7) < 9, val(8) != None != val(9))
print(None == None == None, 1 != None != 2.0, None != None)
x: int | None = 4
print(x == None, None != x)
if x is not None:
    print(x == None, x != None, None == x)
x = None
print(x == None, None != x)
s: str | None = None
print(s == None, s != None)
n = 0
while n != None and n < 3:
    n += 1
print(n)
k = None
if k == None:
    print("k", k != None)
if n == None:
    print("never")
else:
    print("n", n)
p = Plain(1)
print(p == None, None == p, p != None, None != p)
e = Eq(1)
print(e == None, None == e, e != None, None != e)
q = Ne()
print(q == None, None == q, q != None, None != q)
print(D(1) == None, None != D(2), P(1, 2) == None, None != P(3, 4))
# outside a template's parameters == None compares (the branch it fails still gives the types)
names = ["a", "é"]
print([c for c in names if c == None], sum(1 for c in names if None == c), sum(1 for v in xs if v == None))
print([v for v in xs if v != None], [c for c in names if None is c])
out = []
for c in names:
    if c == None:
        out.append(c)
print(out)
