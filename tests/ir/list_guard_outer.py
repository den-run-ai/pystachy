# listguard where a range loop holds another: the inner loop gets its copy first, then the outer
# loop a copy of its own, around both versions of the inner loop, whose own reads of row = a[i]
# and x[i] and store to y[i] are inline (.tbaa); an outer loop whose inner loop may shorten a list
# (drains) keeps its checks
def rows(a: list[list[float]], x: list[float], y: list[float], n: int) -> None:
    for i in range(n):
        s = 0.0
        row = a[i]
        for j in range(n):
            s += row[j] * x[j]
        y[i] = s * x[i]


def drains(a: list[int], b: list[int], n: int) -> int:
    t = 0
    for i in range(n):
        for j in range(2):
            if len(b) > 0 and a[i] % 3 == 0:
                b.pop()
        t += a[i] + len(b)
    return t


y = [0.0, 0.0]
rows([[1.0, 2.0], [3.0, 4.0]], [0.5, 1.5], y, 2)
print(y, drains([3, 1, 6], [7, 7, 7], 3))
