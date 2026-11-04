class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, x: int, doc: str) -> None:
        self.doc = doc
        ys = [(B := y) for y in [1, 2]]
        print(ys)
        B.__init__(self, x)


e = E(5, "d")
print(str(e), repr(e), e.doc)
