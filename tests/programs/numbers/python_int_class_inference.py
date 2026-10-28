# pystachy: python-int
# Promoting counts still infer repeated list/string fields in both operand orders.
class Repeated:
    def __init__(self, n: int, value: int) -> None:
        self.left = [value] * n
        self.right = n * [value]
        self.text = "ab" * n
        self.reverse = n * "xy"


for n in [-2, 0, 3]:
    repeated = Repeated(n, 2 ** 80)
    print(repeated.left, repeated.right, repr(repeated.text), repr(repeated.reverse))
