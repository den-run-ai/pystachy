class B(ValueError):
    def label(self, x: int) -> str:
        return "base " + str(x)


class Receiver:
    def label(self, e: B, x: int) -> str:
        return "shadow " + str(e) + " " + str(x)


class E(B):
    def probe(self, B: Receiver) -> str:
        return B.label(self, 99)


e = E(5)
print(e.probe(Receiver()), str(e), repr(e))
