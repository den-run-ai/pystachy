# error: exc_base_shadow_unbound.py:9: error: local variable 'B' is read before its first assignment; declare it first (B: T)
class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, x: int) -> None:
        B.__init__(self, 99)
        B = x


E(5)
