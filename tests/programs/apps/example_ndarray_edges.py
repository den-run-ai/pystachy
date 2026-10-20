# NumPy 2.3.5 references; check_numpy.py also compares these cases with installed NumPy.
from ndarray import NDArray, array2, matmul, sum_axis, zeros


# Reversing the slow axis must not turn it into a pairwise reduction. These values
# produce 0.0 in sequential order and 84.0 with pairwise summation.
a = array2([[v, v] for v in [1e16] + [1.0] * 100 + [-1e16]])
for rstep in [1, -1]:
    for cstep in [1, -1]:
        offset = (202 if rstep < 0 else 0) + (1 if cstep < 0 else 0)
        view = NDArray(a.data, [102, 2], [2 * rstep, cstep], offset)
        assert sum_axis(view, 0).values() == [0.0, 0.0]
        assert sum_axis(view.T, 1).values() == [0.0, 0.0]
print("reversed slow axes preserve summation order")

# A singleton axis has no traversal, so its stride does not decide reduction order.
for step in [1, -1]:
    view = NDArray(a.data, [102, 1], [2 * step, -1], 202 if step < 0 else 0)
    assert sum_axis(view, 0).values() == [84.0]
    assert sum_axis(view.T, 1).values() == [84.0]
print("strided singleton axes preserve pairwise summation")

for shape in [[0, 4611686018427387904], [-1, 4611686018427387904], [0, 4294967296, 4294967296]]:
    try:
        zeros([0]).reshape(shape)
    except ValueError as e:
        assert str(e) == "array is too big; `arr.size * arr.dtype.itemsize` is larger than the maximum possible size."
    else:
        raise AssertionError("reshape accepted unrepresentable byte extents")
assert zeros([0]).reshape([0, 1024]).shape == [0, 1024]
assert zeros([0]).reshape([-1, 1024]).shape == [0, 1024]
print("empty reshape checks byte extents after inference")


# matmul reads its operands in place in any layout, and sums each item from 0.0 in order along the
# shared axis: exactly the triple loop below, whatever the strides and offsets of a and b
def exact(x: float, y: float) -> bool:
    if x != x or y != y:
        return x != x and y != y
    return x == y and str(x) == str(y)


def layouts(rows: int, cols: int, seed: int) -> list[NDArray]:
    # the same rows x cols matrix as a row-major array, a transpose, padded rows at an offset,
    # reversed rows and padded, reversed columns; -0.0, inf and nan among its items
    items: list[float] = []
    s = seed
    for i in range(rows * cols):
        s = (s * 1103515245 + 12345) % 2147483648
        items.append([-0.0, float("inf"), float("nan"), 0.5][s % 4] if s % 13 == 0 else s / 2147483648.0 - 0.5)
    out = [NDArray(list(items), [rows, cols], [cols, 1], 0)]
    out.append(NDArray([items[i * cols + j] for j in range(cols) for i in range(rows)], [cols, rows], [rows, 1], 0).T)
    padded = [9.0] * 3
    for i in range(rows):
        padded.extend(items[i * cols : (i + 1) * cols] + [7.0, 7.0])
    out.append(NDArray(padded, [rows, cols], [cols + 2, 1], 3))
    out.append(NDArray([items[(rows - 1 - i) * cols + j] for i in range(rows) for j in range(cols)], [rows, cols], [-cols, 1], (rows - 1) * cols))
    cm = [0.0] * (cols * (rows + 1))
    for i in range(rows):
        for j in range(cols):
            cm[(cols - 1 - j) * (rows + 1) + i] = items[i * cols + j]
    out.append(NDArray(cm, [rows, cols], [1, -(rows + 1)], (cols - 1) * (rows + 1)))
    return out


products = 0
for m, k, n in [(3, 5, 8), (2, 4, 7), (4, 3, 6), (1, 6, 5), (3, 0, 4), (0, 3, 2), (2, 1, 1)]:
    av = layouts(m, k, m + k)
    bv = layouts(k, n, k * n + 1)
    want: list[float] = []
    for i in range(m):
        for j in range(n):
            t = 0.0
            for p in range(k):
                t += av[0].data[i * k + p] * bv[0].data[p * n + j]
            want.append(t)
    for x in av:
        for y in bv:
            got = matmul(x, y)
            assert got.shape == [m, n] and len([q for q in range(m * n) if not exact(got.values()[q], want[q])]) == 0
            products += 1
row = NDArray([2.0], [3, 4], [0, 0], 0)  # (one item, broadcast)
col = NDArray([1.0, -0.5, 4.0, 3.0], [4, 2], [1, 0], 0)
assert matmul(row, col).values() == [15.0] * 6
try:
    matmul(NDArray([1.0, 2.0, 3.0], [2, 2], [2, 1], 0), zeros([2, 1]))
    raise AssertionError("matmul read past its operand's data")
except IndexError:
    pass
print(products, "products of matmul in five layouts of each operand equal the triple loop")
