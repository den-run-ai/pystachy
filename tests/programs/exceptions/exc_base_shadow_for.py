class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, x: int, doc: str) -> None:
        self.doc = doc
        for B in range(2):
            pass
        B.__init__(self, x)


e = E(5, "d")
print(str(e), repr(e), e.doc)
