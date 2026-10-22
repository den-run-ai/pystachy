# pystachy: dynamic-any
"""Typed numeric copies and global reads without observing object identity.

The recurrences preserve the numeric-copy and mutable-global regression probes.
Runtime iteration/seed inputs keep these loops observable without crossing Any.
"""
import sys
import time

G = 0
F = 0.0


def integer(n: int, seed: int) -> int:
    x = seed
    total = 0
    for i in range(n):
        x = (x * 17 + 3) % 1000003
        y = x
        total += y
    return total


def floating(n: int, seed: int) -> int:
    x = float(seed)
    total = 0
    for i in range(n):
        x = (x * 1.25 + 3.0) % 1000.0
        y = x
        total += int(y)
    return total


def global_integer(n: int, seed: int) -> int:
    global G
    G = seed
    total = 0
    for i in range(n):
        G = (G * 17 + 3) % 1000003
        total += G
    return total


def global_floating(n: int, seed: int) -> int:
    global F
    F = float(seed)
    total = 0
    for i in range(n):
        F = (F * 1.25 + 3.0) % 1000.0
        total += int(F)
    return total


def main() -> None:
    mode, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    if n < 1 or mode not in ("int", "float", "global_int", "global_float"):
        raise ValueError("expected int|float|global_int|global_float, a positive iteration count and an integer seed")
    # Small analytical checks, including modulo wraparound, run outside timing.
    assert integer(3, 1) == 6197
    assert integer(1, 1000002) == 999989
    assert floating(3, 4) == 40
    assert floating(1, 800) == 3
    assert global_integer(3, 1) == 6197
    assert global_integer(1, 1000002) == 999989
    assert global_floating(3, 4) == 40
    assert global_floating(1, 800) == 3
    start = time.perf_counter()
    if mode == "int":
        checksum = integer(n, seed)
    elif mode == "float":
        checksum = floating(n, seed)
    elif mode == "global_int":
        checksum = global_integer(n, seed)
    else:
        checksum = global_floating(n, seed)
    elapsed = time.perf_counter() - start
    print(mode, checksum)
    print("seconds", elapsed, file=sys.stderr)


if __name__ == "__main__":
    main()
