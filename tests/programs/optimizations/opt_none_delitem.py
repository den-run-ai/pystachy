# None used where only a value works raises CPython's error (delitem)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(s: list[int] | None) -> None:
    print("using", repr(s))
    del s[say(0)]


use(None)
