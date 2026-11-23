# pystachy: dynamic-any
# pystachy: python-int
# In a module that promotes ints, divmod(), round() and hex() of Any values give and take ints
# past 64 bits, as CPython's do.
from typing import Any


def show(value: Any) -> None:
    print(value, type(value).__name__)


wide: Any = int("123456789012345678901234567890")
show(divmod(wide, 7))
show(divmod(wide, -wide))
show(divmod(9223372036854775807 + int("1"), 2))
show(divmod(wide, 2.0))
large: Any = 1e20
show(round(large))
show(round(-large / 4))
show(round(wide))
print(round(wide) is wide, round(wide, 5) is wide)
mid: Any = 123456
show(round(mid, -3))
for n in [-5, -29, -30, -31]:
    show(round(wide, n))
    show(round(-wide, n))
tie: Any = int("250000000000000000000")
print(round(tie, -20), round(tie + 10**20, -20), round(-tie, -20), round(tie, -19))
print(hex(wide), oct(-wide), bin(wide + 1))
try:
    infinite: Any = float("inf")
    print(round(infinite))
except OverflowError as error:
    print("OverflowError", error)
