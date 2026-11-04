class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(x)


class E(B):
    def __init__(self, x: int, doc: str) -> None:
        self.doc = doc
        if x < 0:
            B = 3
        B.__init__(self, x)


try:
    e = E(5, "d")
    print(str(e), repr(e), e.doc)
except UnboundLocalError as error:
    print("UnboundLocalError:", error)

e = E(-5, "d")
print(str(e), repr(e), e.doc)
