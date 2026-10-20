# None used where only a value works raises CPython's error (extend)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: list[int] | None) -> None:
    print("using", repr(s))
    xs = [1]
    xs.extend(s)


use(None)
