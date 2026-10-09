# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (rmul)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(n: float | None) -> None:
    print("using", repr(n))
    print(say(2) * n)


use(None)
