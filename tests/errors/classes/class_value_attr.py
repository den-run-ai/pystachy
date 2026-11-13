# error: the attributes of a class object (type[A]) other than its names and its class's attributes, the names the class body binds, are not supported (.n)
# CPython raises AttributeError: n is an attribute of A's objects, which __init__ assigns, not
# of the class (#7)
class A:
    def __init__(self) -> None:
        self.n = 1


class B(A):
    pass


k: type[A] = B
print(k.n)
