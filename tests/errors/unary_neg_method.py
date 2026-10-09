# error: unary_neg_method.py:13: error: unary - on an object (__neg__) is not supported
# The class defines __neg__, so the message does not say that -v has a bad operand type.
class V:
    def __init__(self, x: int) -> None:
        self.x = x

    def __neg__(self) -> int:
        return -self.x


class A:
    def __init__(self, v: V) -> None:
        self.n = -v


print(A(V(3)).n)
