import sys
import time


def matmult(val: list[float], col: list[int], row: list[int], x: list[float], y: list[float]) -> None:
    for r in range(len(row) - 1):
        s = 0.0
        for k in range(row[r], row[r + 1]):
            s += val[k] * x[col[k]]
        y[r] = s


def main() -> None:
    n = int(sys.argv[1])
    per = int(sys.argv[2])
    reps = int(sys.argv[3])
    val = [0.0] * (n * per)
    col = [0] * (n * per)
    row = [0] * (n + 1)
    x = [0.0] * n
    seed = 7
    for r in range(n):
        row[r + 1] = row[r] + per
        x[r] = (r % 17) / 8.0
        for i in range(per):
            seed = (seed * 1103515245 + 12345) % 2147483648
            col[row[r] + i] = seed % n
            val[row[r] + i] = (seed % 1000) / 250.0
    y = [0.0] * n
    t0 = time.perf_counter()
    for _ in range(reps):
        matmult(val, col, row, x, y)
        x[0] += y[n - 1] * 1e-9
    print(sum(y))
    print("sparse=%.4f" % (time.perf_counter() - t0), file=sys.stderr)


main()
