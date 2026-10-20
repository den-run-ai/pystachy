# None used where only a value works raises CPython's error (enumerate)


def say(v: int) -> int:
    print("evaluated", v)
    return v


def use(s: list[int] | None) -> None:
    print("using", repr(s))
    for i, v in enumerate(s, say(1)):
        print(i, v)


use(None)
