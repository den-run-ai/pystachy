# error: comparing closed union values requires narrowing with isinstance() first
# The identity of two numbers is not modeled: where both operands may hold an int, 'is' needs
# the object's type first (CPython prints True False)
class Sock:
    def __init__(self, fd: int) -> None:
        self.fd = fd


def same(a: Sock | int, b: Sock | int) -> bool:
    return a is b


s = Sock(3)
print(same(s, s), same(s, 3))
