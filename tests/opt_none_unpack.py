# None used where only a value works raises CPython's error (unpack)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: tuple[int, int] | None) -> None:
    print("using", repr(s))
    a, b = s
    print(a, b)


use(None)
