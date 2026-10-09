print("mods.cyc_a: start")
A = 1
NEG = -1
from . import cyc_b


def fa(n: int) -> int:
    return n + cyc_b.B


AB = cyc_b.fb(10)
print("mods.cyc_a: end", AB)
