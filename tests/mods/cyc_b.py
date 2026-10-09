print("mods.cyc_b: start")
from . import cyc_a
print("mods.cyc_b: cyc_a.NEG is", cyc_a.NEG)  # (a constant read while cyc_a is being imported)
B = 100


def fb(n: int) -> int:
    return n * cyc_a.A


print("mods.cyc_b: end")
