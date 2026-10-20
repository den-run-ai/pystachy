# None used where only a value works raises CPython's error (listadd)


def say(v: str) -> str:
    print("evaluated", v)
    return v


def use(s: list[int] | None) -> None:
    print("using", repr(s))
    print([1] + s)


use(None)
