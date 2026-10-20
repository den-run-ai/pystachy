# examples/ndarray's elementwise operations have loops of their own for arrays at the start of
# their lists (as new arrays are), a one-item operand and a row broadcast along the leading axes
# (x + bias), beside the general strided loop: each result equals the expression of the items one
# by one, for operands at an offset, into out and in place, where the operand shares out's list
from ndarray import NDArray, add, divide, multiply, subtract, zeros


def exact(x: float, y: float) -> bool:
    if x != x or y != y:
        return x != x and y != y
    return x == y and str(x) == str(y)


def filled(shape: list[int], seed: int) -> NDArray:
    a = zeros(shape)
    s = seed
    for i in range(a.size):
        s = (s * 1103515245 + 12345) % 2147483648
        a.data[i] = [-0.0, float("inf"), float("nan"), 0.0][s % 4] if s % 11 == 0 else s / 2147483648.0 - 0.5
    return a


def item(x: NDArray, idx: list[int]) -> float:
    # x's item at the index idx of a broadcast result: x's axes align with idx's last ones
    p = x.offset
    for k in range(len(x.shape)):
        if x.shape[k] != 1:
            p += idx[len(idx) - len(x.shape) + k] * x.strides[k]
    return x.data[p]


def plain(x: float, y: float, k: int) -> float:
    if k == 0:
        return x + y
    if k == 1:
        return x - y
    if k == 2:
        return x * y
    if y == 0.0:
        return divide(NDArray([x], [], [], 0), y).data[0]  # (NumPy's inf and nan)
    return x / y


def items(r: NDArray, a: NDArray, b: NDArray, k: int) -> int:
    # how many items of r differ from a's and b's combined one by one
    bad = 0
    idx = [0] * len(r.shape)
    for _ in range(r.size):
        if not exact(item(r, idx), plain(item(a, idx), item(b, idx), k)):
            bad += 1
        j = len(idx) - 1
        while j >= 0:
            idx[j] += 1
            if idx[j] < r.shape[j]:
                break
            idx[j] = 0
            j -= 1
    return bad


def apply(k: int, a: NDArray, b: NDArray, out: NDArray | None = None) -> NDArray:
    if k == 0:
        return add(a, b, out)
    if k == 1:
        return subtract(a, b, out)
    if k == 2:
        return multiply(a, b, out)
    return divide(a, b, out)


big = filled([3, 4, 6], 5)
x = filled([4, 6], 6)
y = filled([4, 6], 7)
bias = filled([6], 8)
cases: list[list[NDArray]] = [
    [x, y],  # whole arrays
    [big.row(1), big.row(2)],  # at offsets
    [x, bias],  # a row broadcast
    [big, bias],  # over two leading axes
    [x, bias.reshape([1, 6])],  # a (1, w) row
    [big.row(2), bias],  # a at an offset
    [x, big.row(1).row(3)],  # the row at an offset
    [x, NDArray([2.5], [], [], 0)],  # one item
    [big.row(1), NDArray([0.0], [1], [1], 0)],  # one item, a at an offset
    [x.T, y.T],  # the general loop
]
bad = 0
count = 0
for k in range(4):
    for c in cases:
        bad += items(apply(k, c[0], c[1]), c[0], c[1], k)
        count += 1
        out = zeros(c[0].shape)
        bad += items(apply(k, c[0], c[1], out), c[0], c[1], k)
        count += 1
    for c in [[x, y], [x, bias], [big, bias], [big.row(1), bias]]:
        # in place, as a op= b writes a: from a copy of a's items, and into a view at an offset
        before = c[0].copy()
        apply(k, c[0], c[1], c[0])
        bad += items(c[0], before, c[1], k)
        count += 1
    # b shares out's list in another layout: what out held before is what b reads
    m = filled([4, 6], 9 + k)
    before = m.copy()
    apply(k, m, m.row(1), m)
    bad += items(m, before, before.row(1), k)
    count += 1
print(count, "elementwise results,", bad, "items differ")
s = filled([4, 6], 3)
s += bias
s *= 2.0
s -= s.row(0)
s /= 4
print([round(v, 6) for v in s.values()[6:12]])
