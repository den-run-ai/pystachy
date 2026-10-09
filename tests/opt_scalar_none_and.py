# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (and)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(n: bool | None) -> None:
    print("using", repr(n))
    print(n & (say(1) > 0))


use(None)
