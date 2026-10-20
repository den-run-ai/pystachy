# assert False ends the code after it: x is narrowed after the if, and None fails the assertion


def need(s: str) -> str:
    return "<" + s + ">"


def asserted(x: str | None) -> str:
    if x is None:
        assert False, "nope"
    return need(x)


print(asserted("z"))
print(asserted(None))
