# None used where only a value works raises CPython's error (sorted)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: list[int] | None) -> None:
    print("using", repr(s))
    print(sorted(s))


use(None)
