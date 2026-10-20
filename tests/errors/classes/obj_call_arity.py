# error: Scale.__call__() missing 1 required positional argument: 'x'
class Scale:
    def __init__(self, k: int) -> None:
        self.k = k

    def __call__(self, x: int, y: int = 0) -> int:
        return x * self.k + y


s = Scale(2)
print(s(y=1))
