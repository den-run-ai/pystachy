# None used where only a value works raises CPython's error (setitem)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: dict[str, int] | None) -> None:
    print("using", repr(s))
    s[say('k')] = 1


use(None)
