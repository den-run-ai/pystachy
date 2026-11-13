# error: D.__init__() missing 1 required positional argument: 'x' (making an object of D, a class that the type[A] called at
# a call of a class object must suit the constructor of every class it may be (#7): CPython
# raises TypeError only where the class object is D's
class A:
    def __init__(self) -> None:
        self.n = 1


class B(A):
    pass


class D(A):
    def __init__(self, x: int) -> None:
        self.x = x


def make(k: type[A]) -> A:
    return k()


print(make(B).n)
