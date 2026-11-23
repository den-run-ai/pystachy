# The reactor recognizes the three backing arrays by their distinct sizes.
import gc


def inner() -> int:
    child = [43] * 10001
    gc.collect()
    return child[0]


def throwing() -> None:
    child = [47] * 10002
    gc.collect()
    if child[0] == 47:
        raise ValueError("done")
    raise RuntimeError("lost local")


def outer() -> int:
    parent = [41] * 10000
    gc.collect()
    if inner() != 43:
        raise RuntimeError("lost local")
    gc.collect()
    try:
        throwing()
    except ValueError:
        pass
    gc.collect()
    return parent[0]


if outer() != 41:
    raise RuntimeError("lost caller local")
