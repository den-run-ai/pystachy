# error: the value pick() returns (str) may be None (str | None); test it with 'is not None' first
def find(xs: list[str], k: str) -> str | None:
    return k if k in xs else None


def pick(xs: list[str], k: str) -> str:
    return find(xs, k)


print(pick(["a"], "a"))
