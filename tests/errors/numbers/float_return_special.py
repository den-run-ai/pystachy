# error: expected float, got float | int (note: what is annotated float and was given an int at
# A function annotated -> float returns the int a float field holds (#1534), but not a special
# method, whose result the operation that calls it checks: CPython's float() raises TypeError
class N:
    def __init__(self) -> None:
        self.v: float = 1

    def __float__(self) -> float:
        return self.v


print(float(N()))
