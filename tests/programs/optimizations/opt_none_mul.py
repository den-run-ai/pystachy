# None used where only a value works raises CPython's error (mul)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(s: str | None) -> None:
    print("using", repr(s))
    print(s * say(2))


use(None)
