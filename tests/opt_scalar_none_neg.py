# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (neg)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(n: float | None) -> None:
    print("using", repr(n))
    print(-n)


use(None)
