# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (format)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(n: float | None) -> None:
    print("using", repr(n))
    print(f"{n}|{n!r}|{say(1)}|{n:5}")


use(None)
