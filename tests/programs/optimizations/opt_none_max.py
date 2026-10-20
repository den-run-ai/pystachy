# None used where only a value works raises CPython's error (max)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: list[str | None]) -> None:
    print("using", repr(s))
    print(max(s))


use([None, "a"])
