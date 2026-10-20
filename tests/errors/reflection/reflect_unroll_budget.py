# error: reflect_unroll_budget.py:11: error: unrolling this loop over 20 attribute names would compile its body 400 times, more than the budget of 256 copies
# Nested loops over constant names multiply their copies; the budget bounds them
class P:
    def __init__(self) -> None:
        self.a = 1


names = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t"]
p = P()
for x in names:
    for y in names:
        print(hasattr(p, x), hasattr(p, y))
