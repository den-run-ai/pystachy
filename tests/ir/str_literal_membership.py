# Literal membership needs no list allocation; a variable RHS retains the
# ordinary list path, including evaluation of all its items.
def literal(value: str) -> bool:
    return value in ["a", "b"]


def optional(value: str | None) -> bool:
    return value not in [None, "a", "b"]


def fallback(value: str, item: str) -> bool:
    return value in ["a", item]
