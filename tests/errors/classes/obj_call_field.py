# error: 'int' object is not callable
class C:
    def __init__(self) -> None:
        self.n = 1


print(C().n(2))
