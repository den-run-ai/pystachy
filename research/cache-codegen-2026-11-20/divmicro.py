"""Division-heavy loop: Python floor division and modulo by run-time divisors whose operands
fit in 32 bits (what LLVM's 64-bit division bypass speeds up on CPUs with slow 64-bit division)."""
import sys
import time


def work(n: int, m: int) -> int:
    s = 0
    x = 12345
    for i in range(m):
        x = (x * 1103515245 + 12345) % 2147483648
        s += x % n + x // (n + i % 5 + 1)
    return s


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    m = int(sys.argv[2]) if len(sys.argv) > 2 else 20000000
    t0 = time.perf_counter()
    print(work(n, m))
    print("seconds", time.perf_counter() - t0, file=sys.stderr)


main()
