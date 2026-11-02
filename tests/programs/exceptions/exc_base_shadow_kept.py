class B(ValueError):
    def __init__(self, x: int) -> None:
        super().__init__(99)


class E(B):
    def __init__(self, B: int, doc: str) -> None:
        self.doc = doc
        B.__init__(self, 99)


def kept(doc: str) -> E:
    return E(5, doc)


e = kept("payload")
print(str(e), repr(e), e.doc)
