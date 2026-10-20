# An object that is None, called, raises CPython's TypeError once the arguments are evaluated
def say(v: int) -> int:
    print("evaluated", v)
    return v


class Scale:
    def __init__(self, k: int) -> None:
        self.k = k

    def __call__(self, x: int, y: int = 0) -> int:
        return x * self.k + y


def get(k: int) -> Scale | None:
    print("get", k)
    return Scale(k) if k > 0 else None


print(get(2)(say(1), y=say(2)))
print(get(0)(say(3), y=say(4)))
