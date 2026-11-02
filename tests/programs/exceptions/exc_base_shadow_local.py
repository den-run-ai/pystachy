class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, x: int) -> None:
        B = x
        B.__init__(self, 99)


e = E(6)
print(str(e), repr(e))
