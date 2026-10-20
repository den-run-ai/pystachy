# Optional values that are None when used as operands, iterables or iterators raise CPython's
# TypeErrors: augmented assignment of either side, reversed(), iter() and next().


def maybe(n: int) -> int | None:
    return None if n < 0 else n


def text(n: int) -> str | None:
    return None if n < 0 else "t" * n


def items(n: int) -> list[int] | None:
    return None if n < 0 else list(range(n))


for n in [2, -1]:
    x = maybe(n)
    try:
        x += 1
        print("+=", x)
    except TypeError as e:
        print("TypeError:", e)
    y = maybe(n)
    try:
        y *= 3
        print("*=", y)
    except TypeError as e:
        print("TypeError:", e)
    s = text(n)
    try:
        s += "!"
        print("str +=", s)
    except TypeError as e:
        print("TypeError:", e)
    xs = items(n)
    try:
        print("reversed", [v for v in reversed(xs)])
    except TypeError as e:
        print("TypeError:", e)
    try:
        it = iter(xs)
        print("iter", next(it))
    except TypeError as e:
        print("TypeError:", e)
