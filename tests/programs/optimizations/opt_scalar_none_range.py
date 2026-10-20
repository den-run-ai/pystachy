# An int, float or bool | None that is None, used where only a value works, raises CPython's
# error (range)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(n: int | None) -> None:
    print("using", repr(n))
    for i in range(say(1), n):
        print(i)


use(None)
