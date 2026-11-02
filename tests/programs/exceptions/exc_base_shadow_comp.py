class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, x: int) -> None:
        print([B.__init__(self, 99) for B in [1, 2]])
        print(str(self), repr(self))
        B.__init__(self, x + 1)


e = E(7)
print(str(e), repr(e))
