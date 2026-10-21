# error: a base that defines __init_subclass__ is not supported
# lib/random's Random keeps CPython's __init_subclass__(), which picks a subclass's _randbelow()
# from the methods it overrides: Pystachy compiles no subclass of Random (lib/README.md)
import random


class Dice(random.Random):
    def roll(self) -> int:
        return self.randint(1, 6)


print(Dice(3).roll())
