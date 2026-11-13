# CPython's "__replace__ = replace" (a second name for a method, in the class body)
class P:
    def __init__(self, n: int) -> None:
        self.n = n

    def replace(self, n: int) -> "P":
        return P(n)

    __replace__ = replace

print(P(1).__replace__(2).n)
