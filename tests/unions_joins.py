# Values of different types that meet where an expression joins its ways: x if c else y, x or y
# and x and y give the union of their types where no other type holds both (each value is boxed
# on its way to the join), and a test in c narrows each arm as it does a statement
import sys


def pick(n: int, m: int | None, s: str) -> None:
    print(n or "zero", n and s, m or "none", m and s, s or 2.5, [n or 1.5, s or 2])
    w: int | str | None = m or s
    print(w, 1 if n else 2.5, True if n else 7, n or True)


def shape(x: int | str) -> None:
    print(x.upper() if isinstance(x, str) else x + 1)
    print(isinstance(x, int) and x + 1)
    print(isinstance(x, str) or x * 3)
    y = x if isinstance(x, int) else len(x)
    print(y + 1)


def deep(n: int, f: float) -> int | float | str:
    return n or f or "neither"


def label(x: int | str = 5, y: int | str | None = None) -> str:
    return repr(x) + " " + repr(y)


def items() -> None:
    t: tuple[int | str, int] = (1, 2)
    u: tuple[int | str, int] = ("a", 3)
    print(t, u, t == u, t < (1, 3), [t, u], [y + 1 for y in [t[0], u[0], 4] if isinstance(y, int)])


pick(0, None, "")
pick(3, 4, "s")
pick(0, 0, "x")
shape(3)
shape("ab")
print(deep(0, 0.0), deep(0, 1.5), deep(4, 0.0), label(), label("a"), label(y=3), label(2, "b"))
items()
argc = len(sys.argv)
print(argc > 9 or "few", argc > 0 and [argc] or "none")
