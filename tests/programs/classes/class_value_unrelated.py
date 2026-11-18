# Class objects of classes without a base class in common share a variable: its type is
# type[object], any ordinary class's class object.
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


print(pick(True), pick(False))
