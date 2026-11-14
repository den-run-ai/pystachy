# pystachy: dynamic-any
# a function returning values of different types chosen by its input
from typing import Any


def parse(tok: str) -> Any:
    if tok.isdigit():
        return int(tok)
    if tok in ("true", "false"):
        return tok == "true"
    try:
        return float(tok)
    except ValueError:
        return tok


vals = [parse(t) for t in "12 true 3.5 abc false 7".split()]
print(vals)
print([type(v).__name__ for v in vals])
