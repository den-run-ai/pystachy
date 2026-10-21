# error: unary_field_no_method.py:10: error: bad operand type for unary -: 'P'
# P has no __neg__: CPython's TypeError, not a field whose type cannot be inferred
class P:
    def __init__(self, x: int) -> None:
        self.x = x


class H:
    def __init__(self, p: P) -> None:
        self.n = -p


print(H(P(1)).n)
