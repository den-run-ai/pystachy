# None used where only a value works raises CPython's error (in)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: list[str] | None) -> None:
    print("using", repr(s))
    print(say('a') in s)


use(None)
