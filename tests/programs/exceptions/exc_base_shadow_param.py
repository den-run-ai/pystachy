class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, B: int) -> None:
        B.__init__(self, 99)


e = E(5)
print(str(e), repr(e))
