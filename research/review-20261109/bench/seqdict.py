import time


def build(n: int) -> dict[int, int]:
    return {i: i * 2 for i in range(n)}


def lookup(d: dict[int, int], n: int) -> int:
    t = 0
    for i in range(n):
        t += d[i]
    return t


def lookup_rand(d: dict[int, int], n: int) -> int:
    t = 0
    k = 12345
    for i in range(n):
        k = (k * 1103515245 + 12345) % n
        t += d[k]
    return t


def main() -> None:
    for n in [100000, 1000000, 3000000]:
        t0 = time.perf_counter()
        d = build(n)
        t1 = time.perf_counter()
        r = lookup(d, n)
        t2 = time.perf_counter()
        r2 = lookup_rand(d, n)
        t3 = time.perf_counter()
        print(f"n={n}: build {(t1 - t0) * 1e9 / n:6.1f} ns/key  sequential lookup {(t2 - t1) * 1e9 / n:6.1f} ns  random lookup {(t3 - t2) * 1e9 / n:6.1f} ns  ({r % 1000}, {r2 % 1000})")


main()
