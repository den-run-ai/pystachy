# error: exc_base_shadow_unsupported.py:9: error: 'list[int]' has no method '__init__'
class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, B: list[int]) -> None:
        B.__init__(self, 99)


E([5])
