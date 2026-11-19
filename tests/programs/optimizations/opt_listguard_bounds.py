# Range loops with a start, a stop or a step that a register gives, and loops that count down,
# whose item reads and assignments run unchecked after tests before the loop (listguard), the same
# loops where those tests fail and the loop runs as compiled (a start of sys.maxsize, whose bound
# start + 1 overflows), and loops that add a base to an index from a variable start, which keep
# their checks: every result, every negative index that wraps and every IndexError with the
# iterations before it, is CPython's
import sys


def tri(x: list[float], n: int) -> float:
    t = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            t += x[i] * x[j]
    return t


def eliminate(a: list[float], b: list[float], j: int, f: float) -> None:
    for k in range(j + 1, len(a)):
        a[k] -= f * b[k]


def sparse(val: list[float], col: list[int], row: list[int], x: list[float]) -> list[float]:
    out = [0.0] * (len(row) - 1)
    for r in range(len(row) - 1):
        s = 0.0
        for k in range(row[r], row[r + 1]):
            s += val[k] * x[col[k]]
        out[r] = s
    return out


def down(a: list[int]) -> list[int]:
    out = [0] * len(a)
    for i in range(len(a) - 1, -1, -1):
        out[i] = a[i] * 2 + a[i - 1]
    return out


def between(a: list[int], hi: int, lo: int) -> int:
    s = 0
    for i in range(hi, lo, -1):
        s = s * 3 + a[i]
    return s


def strided(a: list[int], hi: int, step: int) -> int:
    s = 0
    for i in range(hi, -1, -3):
        s += a[i]
    for i in range(1, hi, step):
        s += a[i] * 10
    return s


def stepdown(a: list[int], hi: int, step: int) -> int:
    s = 0
    for i in range(hi, -1, step):
        s = s * 2 + a[i]
    return s


def shifted(a: list[int], lo: int, hi: int) -> int:
    s = 0
    for i in range(lo, hi):
        s = s * 2 + a[i - 1] + a[i + 1]
    return s


def based(data: list[int], b: int, lo: int, hi: int) -> int:
    s = 0
    for i in range(lo, hi):
        s += data[b + i] - data[b + i - 1]
    return s


def based_down(data: list[int], b: int, hi: int, lo: int) -> int:
    s = 0
    for i in range(hi, lo, -1):
        s = s * 2 + data[b + i]
    return s


def partial(a: list[int], lo: int, hi: int) -> int:
    s = 0
    for i in range(lo, hi):
        s += a[i]
        print("partial", i, s)
    return s


def partial_down(a: list[int], hi: int) -> int:
    s = 0
    for i in range(hi, -1, -1):
        s += a[i]
        print("partial down", i, s)
    return s


def main() -> None:
    n = len(sys.argv) + 5
    x = [float(i % 5) + 0.5 for i in range(n)]
    print("tri", tri(x, n), tri(x, 0), tri(x, 1))
    a = [float(i) for i in range(n)]
    b = [float(i * i) for i in range(n)]
    eliminate(a, b, 2, 0.5)
    print("eliminate", a)
    eliminate(a, b, n, 1.0)
    eliminate(a, b, -3, 1.0)  # (from k = -2: a[-2] and a[-1] wrap, as CPython reads them)
    print("eliminate wraps", a)
    print("sparse", sparse([1.0, 2.0, 3.0, 4.0], [0, 2, 1, 2], [0, 2, 2, 4], [10.0, 20.0, 30.0]))
    try:
        sparse([1.0, 2.0], [0, 1], [0, 3], [1.0, 2.0])
    except IndexError as e:
        print("sparse long row", e)
    print("down", down([1, 2, 3, 4]), down([]))
    c = [i * 7 % 11 for i in range(n)]
    print("between", between(c, n - 1, 2), between(c, 3, 3), between(c, 2, 5), between(c, 2, -3))
    try:
        between(c, n, 0)
    except IndexError as e:
        print("between past the end", e)
    print("strided", strided(c, n - 1, 2), strided(c, 5, 4), strided(c, 5, -1))
    try:
        strided(c, 5, 0)
    except ValueError as e:
        print("strided zero step", e)
    print("stepdown", stepdown(c, n - 1, -2), stepdown(c, 3, -1), stepdown(c, 4, 1))
    try:
        stepdown(c, n, -2)
    except IndexError as e:
        print("stepdown past the end", e)
    print("shifted", shifted(c, 1, n - 1), shifted(c, 0, 2), shifted(c, 3, 3))
    try:
        shifted(c, 1, n)
    except IndexError as e:
        print("shifted past the end", e)
    d = [i * i for i in range(12)]
    print("based", based(d, 3, 1, 8), based(d, -2, 3, 14), based(d, 0, 0, 3))
    try:
        based(d, 5, 2, 9)
    except IndexError as e:
        print("based past the end", e)
    big = 4611686018427387904
    print("based big", based(d, -big, big + 1, big + 6))
    top = 9223372036854775807
    print("based top", based(d, 3 - top, top - 2, top))
    try:
        between(c, top, top - 2)
    except IndexError as e:
        print("between at the top", e)
    print("based down", based_down(d, 2, 8, 0), based_down(d, 2, 3, 3), based_down(d, -4, 6, 1))
    bottom = -9223372036854775807 - 1
    print("based bottom", based_down(d, top, bottom + 3, bottom))
    try:
        based_down(d, 2, 10, 0)
    except IndexError as e:
        print("based down past the end", e)
    try:
        partial([1, 2, 3], 1, 5)
    except IndexError as e:
        print("partial long", e)
    try:
        partial_down([1, 2, 3], 4)
    except IndexError as e:
        print("partial down long", e)
    print("partial down", partial_down([1, 2, 3], 2))


main()
