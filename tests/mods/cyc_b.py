print("mods.cyc_b: start")
from . import cyc_a
B = 100


def fb(n: int) -> int:
    return n * cyc_a.A


print("mods.cyc_b: end")
