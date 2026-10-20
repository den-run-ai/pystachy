# None used where only a value works raises CPython's error (iter)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: str | None) -> None:
    print("using", repr(s))
    for c in s:
        print(c)


use(None)
