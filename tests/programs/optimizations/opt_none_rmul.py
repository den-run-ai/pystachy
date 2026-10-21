# None used where only a value works raises CPython's error (rmul)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(s: list[int] | None) -> None:
    print("using", repr(s))
    print(say(2) * s)


use(None)
