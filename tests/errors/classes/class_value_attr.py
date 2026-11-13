# error: the attributes of a class object (type[A]) other than __name__, __qualname__ and __module__ are not supported (.n)
# a class attribute is read through the class's name, not through a class object (#7)
class A:
    def __init__(self) -> None:
        self.n = 1


class B(A):
    pass


k: type[A] = B
print(k.n)
