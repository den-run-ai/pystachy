# pystachy: python-int
# x or y and x and y of a 64-bit int and a promoting int, in an expression that is typed before
# it is compiled (a dict.get() default): typing it converted the first operand in a block that
# is in no list ("internal error: no block entry to convert int to int+ in")
import sys


def default_or(a: int) -> int:
    n = 3
    d: dict[str, int] = {"k": 1}
    return d.get("x", n or a)


def default_and(a: int) -> int:
    n = 3
    d: dict[str, int] = {"k": 1}
    return d.get("x", n and a) + d.get("k", (n - 3) or a)


def items(a: int, s: str) -> list[int | str]:
    n = len(s)
    d: dict[str, int] = {"k": 1, "ab": 2}
    ss = ["p", "qq"]
    return [d.get(s or "k", n or a), ss[d.get(s, n and a) % 2]]


z = len(sys.argv) - 1
print(default_or(5), default_or(2**70), default_and(7 + z), default_and(2**70), items(9, ""), items(2**70, "ab"), items(5 + z, "zz"))
