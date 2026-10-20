# None used where only a value works raises CPython's error (items)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: dict[str, int] | None) -> None:
    print("using", repr(s))
    for k, v in s.items():
        print(k, v)


use(None)
