# None used where only a value works raises CPython's error (iadd)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: str | None) -> None:
    print("using", repr(s))
    s += say('a')
    print(s)


use(None)
