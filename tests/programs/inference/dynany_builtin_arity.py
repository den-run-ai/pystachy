# pystachy: dynamic-any
from typing import Any


def side(n: int) -> int:
    print("arg", n)
    return n


def fail() -> int:
    print("arg raises")
    raise ValueError("argument first")


def changed(xs: Any) -> int:
    xs.append(9)
    print("changed", xs)
    return 1


def attempt(kind: str, x: Any) -> None:
    try:
        if kind == "append":
            x.append(side(1), side(2))
        elif kind == "append-empty":
            x.append()
        elif kind == "insert":
            x.insert(side(1))
        elif kind == "clear":
            x.clear(side(1))
        elif kind == "pop":
            x.pop(side(1), side(2), side(3))
        elif kind == "index":
            x.index(side(1), side(2), side(3), side(4))
        elif kind == "split":
            x.split(side(1), side(2), side(3))
        elif kind == "splitlines":
            x.splitlines(side(1), side(2))
        elif kind == "strip":
            x.strip(side(1), side(2))
        elif kind == "bit-count":
            x.bit_count(side(1))
        elif kind == "hex":
            x.hex(side(1))
        elif kind == "update":
            x.update(side(1), side(2))
        elif kind == "sort":
            x.sort(side(1))
        elif kind == "first-error":
            x.append(fail(), side(2))
        elif kind == "missing":
            x.missing(side(1))
        elif kind == "mutate":
            x.append(changed(x), side(2))
        elif kind == "starred":
            x.append(*(side(1), side(2)))
    except (TypeError, AttributeError, ValueError) as err:
        print(kind, type(err).__name__ + ":", err)


xs: Any = [0]
for kind in ["append", "append-empty", "insert", "clear", "pop", "index", "sort", "first-error", "missing", "mutate", "starred"]:
    attempt(kind, xs)
print("retained", xs)
attempt("append", "not a list")
for kind in ["clear", "pop", "update"]:
    attempt(kind, {"a": 1})
for kind in ["split", "splitlines", "strip", "index"]:
    attempt(kind, "abc")
attempt("index", (1, 2))
attempt("bit-count", 1)
attempt("bit-count", True)
attempt("hex", 1.0)
