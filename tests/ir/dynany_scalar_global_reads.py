# pystachy: dynamic-any
# Numeric consumers need no global snapshot; escaping reads still need one.
# A returned literal carries its canonical object through the numeric call ABI.
from typing import Any

G = 0
F = 0.0
H = 0


def integer(n: int) -> int:
    global G
    total = 0
    for i in range(n):
        G = (G * 17 + 3) % 1000003
        total += G
    return total


def floating(n: int) -> int:
    global F
    total = 0
    for i in range(n):
        F = (F * 1.25 + 3.0) % 1000.0
        total += int(F)
    return total


def update(n: int) -> int:
    global G
    G += n
    return G + 1


def escape() -> Any:
    return G


def copy() -> int:
    global H
    H = G
    return H + 1


def walrus() -> int:
    global H
    return (H := G) + 1


def callback() -> int:
    global G
    G = 1000
    return 1


def open_operand() -> int:
    return G + callback()


def dynamic_operand(x: Any) -> Any:
    return G + x
