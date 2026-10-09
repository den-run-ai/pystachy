# An object that is None, used through the container protocol, raises CPython's error once
# the operands are evaluated (for loops and the builtins that iterate)
from collections.abc import Iterator


def say(v: int) -> int:
    print("evaluated", v)
    return v


class Box:
    def __init__(self) -> None:
        self.xs = [1, 2]

    def __getitem__(self, i: int) -> int:
        return self.xs[i]

    def __setitem__(self, i: int, v: int) -> None:
        self.xs[i] = v

    def __delitem__(self, i: int) -> None:
        del self.xs[i]

    def __contains__(self, v: int) -> bool:
        return v in self.xs

    def __iter__(self) -> Iterator[int]:
        return iter(self.xs)


def get(n: int) -> Box | None:
    print("get", n)
    return Box() if n > 0 else None


print(list(get(1)), sorted(get(1)), sum(get(1)))
for x in get(0):
    print(x)
