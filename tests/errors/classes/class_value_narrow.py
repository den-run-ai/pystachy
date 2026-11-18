# error: expected type[B], got type[A]
# type[B] holds the class object of B or of a class deriving from it, not that of its base (#7)
class A:
    def __init__(self) -> None:
        self.n = 1


class B(A):
    pass


k: type[B] = A
print(k)
