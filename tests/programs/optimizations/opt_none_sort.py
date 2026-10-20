# None used where only a value works raises CPython's error (sort)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: list[str | None]) -> None:
    print("using", repr(s))
    print(sorted(s))


use(["b", None, "a"])
