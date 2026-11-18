# error: reflected operator methods are not supported (V ** W calls W.__rpow__)
# A right operand that may be of a subclass with its own reflected power is asked first.
class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __pow__(self, k: "V") -> "V":
        return V(self.n ** k.n)

    def __rpow__(self, k: int) -> "V":
        return V(k ** self.n)


class W(V):
    def __rpow__(self, k: int) -> "V":
        return V(-1)


print((V(3) ** W(2)).n)
