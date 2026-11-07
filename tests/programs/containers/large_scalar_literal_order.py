seen: list[int] = []


def mark(n: int) -> int:
    seen.append(n)
    if n == 99:
        raise ValueError("stop")
    return n


values = [mark(0), 1, 2, 3, 4, 5, 6, 7, mark(8), 9, 10, 11, 12, 13, 14, 15,
          16, 17, 18, 19, 20, 21, 22, 23, mark(24), 25, 26, 27, 28, 29, 30, mark(31)]
print(seen, len(values), values[:4], values[-4:])
seen.clear()
try:
    values = [mark(1), 1, 2, 3, 4, 5, 6, 7, mark(99), 9, 10, 11, 12, 13, 14, 15,
              16, 17, 18, 19, 20, 21, 22, 23, mark(2), 25, 26, 27, 28, 29, 30, mark(3)]
except ValueError as error:
    print(seen, str(error), len(values), values[0], values[-1])

# Computed NaNs are not constant source data, and an unpacked list stays fresh.
n = float("nan")
nans = [n, n, n, n, n, n, n, n, n, n, n, n, n, n, n, n,
        n, n, n, n, n, n, n, n, n, n, n, n, n, n, n, n]
print(len(nans), nans[0] != nans[0])
unpacked = [*values]
print(unpacked is values, unpacked == values)
