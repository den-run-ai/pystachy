import sys
import time


def make(n: int, seed: int) -> list[list[float]]:
    rows: list[list[float]] = []
    x = seed
    for i in range(n):
        row = [0.0] * n
        for j in range(n):
            x = (x * 1103515245 + 12345) % 2147483648
            row[j] = (x % 1000) / 500.0 + (n if i == j else 0)
        rows.append(row)
    return rows


def lu(a: list[list[float]], n: int) -> None:
    # Gaussian elimination without pivoting: the row update runs over range(j + 1, n)
    for j in range(n):
        rowj = a[j]
        piv = rowj[j]
        for i in range(j + 1, n):
            rowi = a[i]
            f = rowi[j] / piv
            rowi[j] = f
            for k in range(j + 1, n):
                rowi[k] -= f * rowj[k]


def main() -> None:
    n = int(sys.argv[1])
    reps = int(sys.argv[2])
    t = 0.0
    total = 0.0
    for r in range(reps):
        a = make(n, r + 1)
        t0 = time.perf_counter()
        lu(a, n)
        t += time.perf_counter() - t0
        total += a[n - 1][n - 1]
    print(total)
    print("lu=%.4f" % t, file=sys.stderr)


main()
