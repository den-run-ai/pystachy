# None used where only a value works raises CPython's error (reversed)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: list[int] | None) -> None:
    print("using", repr(s))
    for v in reversed(s):
        print(v)


use(None)
