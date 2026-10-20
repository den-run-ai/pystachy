# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (add)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(n: int | None) -> None:
    print("using", repr(n))
    print(n + say(1))


use(None)
