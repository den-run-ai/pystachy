# error: unary_neg_method.py:13: error: cannot infer the type of field 'n'; annotate it (self.n: T = ...)
# -v is what V.__neg__ returns, which a field's type is not inferred from (as for v + v).
class V:
    def __init__(self, x: int) -> None:
        self.x = x

    def __neg__(self) -> int:
        return -self.x


class A:
    def __init__(self, v: V) -> None:
        self.n = -v


print(A(V(3)).n)
