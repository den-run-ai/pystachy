# None used where only a value works raises CPython's error (find)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: str | None) -> None:
    print("using", repr(s))
    print('abc'.find(s))


use(None)
