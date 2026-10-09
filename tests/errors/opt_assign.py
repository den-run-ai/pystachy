# error: the value assigned to 'y' (str) may be None (str | None); test it with 'is not None' first
def pick(x: str | None) -> str:
    y = "default"
    y = x
    return y


print(pick("a"))
