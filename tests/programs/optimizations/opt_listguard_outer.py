# Range loops that hold other loops, whose own item reads and assignments run unchecked after tests
# before them (listguard copies inner loops first, then the loops around them), the same loops where
# those tests fail and they run as compiled, and outer loops whose inner loop may shorten a list,
# which keep their checks: every result and every IndexError with the iterations before it, is
# CPython's
import sys


def rows(a: list[list[float]], x: list[float], y: list[float], n: int) -> None:
    for i in range(n):
        s = 0.0
        row = a[i]
        for j in range(n):
            s += row[j] * x[j]
        y[i] = s * x[i]


def pairs(x: list[float], n: int) -> float:
    t = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            t += x[i] * x[j]
    return t


def back(a: list[list[float]], b: list[float], n: int) -> list[float]:
    # (back substitution: an outer loop that counts down around one that counts up)
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = b[i]
        row = a[i]
        for j in range(i + 1, n):
            s -= row[j] * x[j]
        x[i] = s / row[i]
    return x


def cube(c: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        for j in range(n):
            for k in range(n):
                t += c[i] * 100 + c[j] * 10 + c[k]
    return t


def waits(a: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        k = a[i]
        while k > 0:
            t += k
            k -= 2
    return t


def drains(a: list[int], b: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        for j in range(2):
            if len(b) > 0 and a[i] % 3 == 0:
                b.pop()
        t += a[i] + len(b)
    return t


def main() -> None:
    n = len(sys.argv) + 4
    a = [[float(i * n + j + 1) for j in range(n)] for i in range(n)]
    x = [float(k) + 0.5 for k in range(n)]
    y = [0.0] * n
    rows(a, x, y, n)
    print("rows", y, "pairs", pairs(x, n))
    try:
        rows(a, x, [0.0, 0.0], n)
    except IndexError as e:
        print("rows short", e)
    try:
        rows(a[:3], x, y, n)
    except IndexError as e:
        print("rows few", e)
    print("back", back(a, x, n))
    try:
        back(a, x[:2], n)
    except IndexError as e:
        print("back short", e)
    print("cube", cube([1, 2, 3, 4, 5, 6], 4))
    try:
        cube([1, 2], 3)
    except IndexError as e:
        print("cube short", e)
    print("waits", waits([5, 4, 3, 0, 7, 1], 6))
    print("drains", drains([3, 1, 6, 2, 9, 4], [7, 7, 7, 7, 7], 6))
    try:
        drains([3, 6, 9, 1], [1], 6)
    except IndexError as e:
        print("drains short", e)


main()
