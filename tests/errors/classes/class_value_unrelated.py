# error: expected type[A], got type[C]
# class objects in one variable are those of classes with a base class in common (#7)
class A:
    def __init__(self) -> None:
        self.n = 1


class B(A):
    pass


class C:
    pass


def pick(flag: bool) -> str:
    k = A if flag else C
    return k.__name__


print(pick(True))
