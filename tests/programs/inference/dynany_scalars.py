# pystachy: dynamic-any
# Arithmetic, comparison, truth, conversion and formatting of Any values: each result's type
# follows the operands' types at run time, as CPython's does (int / int is a float, 2 ** -1 too).
from typing import Any


def show(label: str, v: Any) -> None:
    print(label, repr(v), type(v).__name__)


a: Any = 7
b: Any = 2
show("add", a + b)
show("sub", a - b)
show("mul", a * b)
show("div", a / b)
show("floordiv", a // b)
show("mod", a % b)
show("pow", a ** b)
show("negpow", b ** -1)
show("shl", a << b)
show("and", a & b)
show("or", a | b)
show("xor", a ^ b)
c: Any = 1.5
show("fadd", a + c)
show("fmul", c * 2)
show("fdiv", c / 0.5)
t: Any = True
show("bool+bool", t + t)
show("bool&bool", t & t)
show("bool|int", t | 4)
show("neg", -a)
show("negf", -c)
show("inv", ~a)

show("pos", +t)
s: Any = "ab"
show("cat", s + "cd")
show("rep", s * 3)
show("rep2", 2 * s)
show("eq", a == 7)
show("eqf", a == 7.0)
show("ne", a != b)
show("lt", a < c)
show("le", b <= 2.0)
show("strlt", s < "b")
print("truth", bool(a), bool(0 * a))
n: Any = None
show("none", n)
print(n is None, a is None, n is not None)
x: Any = 10
x += 5
show("iadd", x)
x *= 2.0
show("imul", x)
x = "s"
x += "t"
show("istr", x)
print(int(c), float(a), str(a) + "!", len(s))
print(f"{a} {c} {s} {n} {t}")
print(f"{a:>5}|{c:.3f}|{s!r}")
