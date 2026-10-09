# error: C.__init__() takes 1 positional argument but 2 were given
class C:
    def __init__(self, *, k: int) -> None:
        self.k = k

    @classmethod
    def mk(cls) -> "C":
        return cls(1)


print(C.mk().k)
