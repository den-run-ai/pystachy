# error: inheritance_trait_of_primary.py:18: error: multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several
# A trait derives from a strict ancestor of the primary base: Trait(Primary) as a secondary base of
# Both(Primary, Trait) has no consistent method resolution order (CPython's TypeError).
class Root:
    def f(self) -> int:
        return 0


class Primary(Root):
    pass


class Trait(Primary):
    def f(self) -> int:
        return 1


class Both(Primary, Trait):
    pass


print(Both().f())
