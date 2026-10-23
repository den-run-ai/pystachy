# pystachy: dynamic-any
# Numeric copies preserve their source object before either binding first becomes Any.
from typing import Any


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def churn() -> None:
    for i in range(30):
        str([str(i), str(i + 1)])


def run() -> None:
    n = int("1000")
    m = n
    churn()
    same("int copy", n, m)
    x = float("-0.0")
    y = x
    churn()
    same("float copy", x, y)
    nan = float("nan")
    nan_copy = nan
    same("nan copy", nan, nan_copy)
    chain = m
    last = chain
    same("copy chain", n, last)
    distinct = int("1000")
    same("equal distinct", n, distinct)
    n = int("1000")
    same("source rebound", n, m)
    same("old alias survives", m, last)
    chain = int("1000")
    same("target rebound", chain, last)
    m = m
    same("self assignment", m, last)
    a = int("2000")
    b = int("3000")
    a_copy = a
    b_copy = b
    a, b = b, a
    same("swap first", a, b_copy)
    same("swap second", b, a_copy)
    # Neither source has a box when the simultaneous assignment reads it.
    p = int("4000")
    q = int("5000")
    p, q = q, p
    p_copy = p
    q_copy = q
    same("unboxed swap first", p, p_copy)
    same("unboxed swap second", q, q_copy)
    print("unboxed swap values", p, q)
    for flag in [False, True]:
        source = int("6000")
        if flag:
            copied = source
        else:
            copied = source
        churn()
        same("branch copy", source, copied)
        copied = int("6000")
        same("branch rebound", source, copied)
    prior: Any = None
    for i in range(3):
        source = int("7000")
        copied = source
        same("loop copy", source, copied)
        same("loop distinct", prior, copied)
        prior = copied


G = int("8000")
H = G
same("module copy", G, H)
G = int("8000")
same("module rebound", G, H)
run()
