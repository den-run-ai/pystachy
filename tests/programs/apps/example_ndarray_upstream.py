# NumPy 2.5.3's own tests, adapted to examples/ndarray: the cases its float64 NDArray can express,
# with NumPy's expected values. NumPy uses the BSD 3-Clause license, in tests/upstream/NUMPY-LICENSE.txt
# (see THIRD_PARTY_NOTICES). The source files, from the numpy 2.5.3 wheel, and their SHA-256:
#   numpy/lib/tests/test_stride_tricks.py  b3e3fa0649b9be51e6adbba4b08bcd536b42161629db310329d144a1015f8d4f
#     test_same, test_one_off, test_same_input_shapes, test_two_compatible_by_ones_input_shapes,
#     test_two_compatible_by_prepending_ones_input_shapes, test_incompatible_shapes_raise_valueerror,
#     test_same_as_ufunc, test_broadcast_shapes_succeeds, test_broadcast_shapes_raises
#   numpy/_core/tests/test_multiarray.py  4b51861849e3b456480544dc3176c0b2151aaee2e00460e7ba40891ce8726bec
#     TestMethods.test_reshape, test_transpose, test_ravel; TestZeroRank.test_empty_subscript,
#     test_invalid_subscript; TestCreation.test_zeros, test_too_big_error; TestStats.test_empty,
#     test_mean_values; TestDot.test_dotmatmat, test_dotmatvec, test_dotvecmat2, test_dotvecvecouter,
#     test_dotvecvecinner, test_dot_array_order; MatmulCommon.test_exceptions,
#     test_matrix_matrix_values; TestMatmul.test_matmul_empty, test_dot_equivalent
#   numpy/_core/tests/test_ufunc.py  25449dff943a0febef85eb3c0a8515e18bdced05d2d4057a182c809455f7cceb
#     TestUfunc.test_sum_stability, test_sum
#   numpy/_core/tests/test_umath.py  f076f371edcd8c36efb636e7a428a25f51079caeccb53743fdaeb8e3ff7e2ad4
#     TestDivision.test_division_int
#   numpy/_core/tests/test_indexerrors.py  d019c705a6b4dbf1fe8c7217db0fcdb6382ece19db83c38881bcf6098d5984cd
#     TestIndexErrors.test_mapping, test_mapping_error_message
#   numpy/_core/tests/test_indexing.py  9d1a04348bd6d7cc5148e2bf92c09eed43db0d94b5a3d67d0b54e835ee8f7e7a
#     TestIndexing.test_single_int_index
#   numpy/_core/tests/test_regression.py  527abff2e69f971b1d7154346419affc52ce418a07f9312c508e5f014d3e32ca
#     TestRegression.test_dot_negative_stride
# Adaptations: standalone assertions replace pytest and numpy.testing (assert_almost_equal keeps its
# rule, |desired - actual| < 1.5 * 10**-decimal); float64 stands in for every dtype, so the int, bool,
# object and narrower float variants are the float64 case; shapes are lists; broadcast_arrays(x, y)
# is x + zeros(y.shape), as test_same_as_ufunc computes it, and broadcast_shapes folds that over its
# shapes; the views NumPy makes by slicing (x[::-1], x[1::3], x[..., ::2]) and order='F' arrays are
# built with the NDArray constructor, which takes strides and an offset; a[i] of a 2-D array is
# a.row(i); np.ones(n) is zeros([n]) + 1.0 and np.arange(1, v + 1) is arange(v) + 1.0; np.dot of 2-D
# arrays is matmul(); the random inputs of TestStats and TestDot are the values NumPy 2.5.3 draws for
# them (default_rng(range(3)).random((4, 5)), RandomState(128)), written out.
# Left out: what needs features the example lacks: order='F'/'A'/'K' results, as_strided, transpose
# axes, fancy and boolean indexing, assignment to a 1-D array or through (), matmul of 0-, 1- or
# 3-dimensional operands and stacks, dot of 1-D operands, mean along an axis, warnings and errstate,
# 1 << 64 indices (ints are 64-bit), np.empty and np.ones, and floor division and remainder.
from ndarray import NDArray, arange, array, array2, matmul, mean, total, zeros


class Tally:
    # the assertions that held, by group; a failure raises AssertionError naming its case
    def __init__(self) -> None:
        self.groups: list[str] = []
        self.counts: list[int] = []

    def group(self, name: str) -> None:
        self.groups.append(name)
        self.counts.append(0)

    def check(self, cond: bool, what: str) -> None:
        if not cond:
            raise AssertionError(f"{self.groups[-1]}: {what}")
        self.counts[-1] += 1


t = Tally()


def value_error(f) -> str:
    # the message of the ValueError that f() raises, or "" if it raises none
    try:
        f()
    except ValueError as e:
        return str(e)
    return ""


def index_error(f) -> str:
    try:
        f()
    except IndexError as e:
        return str(e)
    return ""


def almost(actual: float, desired: float, decimal: int) -> bool:
    # numpy.testing.assert_almost_equal's test
    return abs(desired - actual) < 1.5 * 10.0 ** (-decimal)


def all_almost(a: NDArray, desired: list[list[float]], decimal: int) -> bool:
    flat = [x for r in desired for x in r]
    if a.shape != [len(desired), len(desired[0])]:
        return False
    return all(almost(x, y, decimal) for x, y in zip(a.values(), flat))


def is_array(a: NDArray, shape: list[int], items: list[float]) -> bool:
    # assert_equal of an array and a nested list: its shape and its items in C order
    return a.shape == shape and a.values() == items


def prod(shape: list[int]) -> int:
    n = 1
    for d in shape:
        n *= d
    return n


def flip(a: NDArray) -> NDArray:
    # a[::-1]: a view of the first axis reversed (offset at its last index, stride negated)
    st = [-a.strides[0]] + a.strides[1:]
    last = a.shape[0] - 1 if a.shape[0] > 0 else 0
    return NDArray(a.data, list(a.shape), st, a.offset + last * a.strides[0])


def view(a: NDArray, r: range) -> NDArray:
    # a[start:stop:step] of a 1-D array, the bounds normalized as range(len(a))[start:stop:step] does
    return NDArray(a.data, [len(r)], [a.strides[0] * r.step], a.offset + (r.start if len(r) > 0 else 0) * a.strides[0])


def stepped(a: NDArray, axis: int, k: int) -> NDArray:
    # a[..., ::k] along one axis
    shape = list(a.shape)
    st = list(a.strides)
    shape[axis] = (shape[axis] + k - 1) // k
    st[axis] *= k
    return NDArray(a.data, shape, st, a.offset)


def fortran(rows: list[list[float]]) -> NDArray:
    # np.array(rows, order='F'): the items stored column by column
    return array2(rows).T.copy().T


def broadcast(x: NDArray, shape: list[int]) -> list[float]:
    # broadcast_arrays' view of x against shape, item by item in C order, read through x's strides
    out: list[float] = []
    idx = [0] * len(shape)
    for _ in range(prod(shape)):
        p = x.offset
        for k in range(len(x.shape)):
            if x.shape[k] != 1:
                p += idx[len(shape) - len(x.shape) + k] * x.strides[k]
        out.append(x.data[p])
        j = len(shape) - 1
        while j >= 0:
            idx[j] += 1
            if idx[j] < shape[j]:
                break
            idx[j] = 0
            j -= 1
    return out


def bshape(shapes: list[list[int]]) -> list[int]:
    # broadcast_shapes(*shapes): the shape of the sum of zero arrays of these shapes
    x = zeros(shapes[0])
    for s in shapes[1:]:
        x = x + zeros(s)
    return x.shape


def same_as_ufunc(s0: list[int], s1: list[int], transposed: bool, flipped: bool) -> None:
    # adding zeros to x1 gives the broadcast view of x1 (assert_same_as_ufunc)
    x0 = zeros(s0)
    x1 = arange(prod(s1)).reshape(s1)
    if transposed:
        x0 = x0.T
        x1 = x1.T
    if flipped:
        x0 = flip(x0)
        x1 = flip(x1)
    y = x0 + x1
    t.check(y.values() == broadcast(x1, y.shape), f"{s0} {s1} transposed={transposed} flipped={flipped}")


# ---- numpy/lib/tests/test_stride_tricks.py
t.group("broadcasting (test_stride_tricks.py)")
x = arange(10)
t.check((x + zeros([10])).values() == x.values(), "test_same")
ox = array2([[1.0, 2.0, 3.0]])
oy = array2([[1.0], [2.0], [3.0]])
t.check(is_array(ox + zeros([3, 1]), [3, 3], [1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0]), "test_one_off bx")
t.check(is_array(zeros([1, 3]) + oy, [3, 3], [1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 3.0, 3.0, 3.0]), "test_one_off by")

SAME: list[list[int]] = [[], [1], [3], [0, 1], [0, 3], [1, 0], [3, 0], [1, 3], [3, 1], [3, 3]]
for shape in SAME:
    t.check(bshape([shape]) == shape, f"test_same_input_shapes {shape}")
    t.check(bshape([shape, shape]) == shape, f"test_same_input_shapes {shape} x2")
    t.check(bshape([shape, shape, shape]) == shape, f"test_same_input_shapes {shape} x3")

BY_ONES: list[tuple[list[list[int]], list[int]]] = [
    ([[1], [3]], [3]),
    ([[1, 3], [3, 3]], [3, 3]),
    ([[3, 1], [3, 3]], [3, 3]),
    ([[1, 3], [3, 1]], [3, 3]),
    ([[1, 1], [3, 3]], [3, 3]),
    ([[1, 1], [1, 3]], [1, 3]),
    ([[1, 1], [3, 1]], [3, 1]),
    ([[1, 0], [0, 0]], [0, 0]),
    ([[0, 1], [0, 0]], [0, 0]),
    ([[1, 0], [0, 1]], [0, 0]),
    ([[1, 1], [0, 0]], [0, 0]),
    ([[1, 1], [1, 0]], [1, 0]),
    ([[1, 1], [0, 1]], [0, 1]),
]
BY_PREPENDING: list[tuple[list[list[int]], list[int]]] = [
    ([[], [3]], [3]),
    ([[3], [3, 3]], [3, 3]),
    ([[3], [3, 1]], [3, 3]),
    ([[1], [3, 3]], [3, 3]),
    ([[], [3, 3]], [3, 3]),
    ([[1, 1], [3]], [1, 3]),
    ([[1], [3, 1]], [3, 1]),
    ([[1], [1, 3]], [1, 3]),
    ([[], [1, 3]], [1, 3]),
    ([[], [3, 1]], [3, 1]),
    ([[], [0]], [0]),
    ([[0], [0, 0]], [0, 0]),
    ([[0], [0, 1]], [0, 0]),
    ([[1], [0, 0]], [0, 0]),
    ([[], [0, 0]], [0, 0]),
    ([[1, 1], [0]], [1, 0]),
    ([[1], [0, 1]], [0, 1]),
    ([[1], [1, 0]], [1, 0]),
    ([[], [1, 0]], [1, 0]),
    ([[], [0, 1]], [0, 1]),
]
for shapes, expected in BY_ONES + BY_PREPENDING:
    t.check(bshape(shapes) == expected, f"compatible {shapes}")
    t.check(bshape(shapes[::-1]) == expected, f"compatible {shapes[::-1]}")

INCOMPATIBLE: list[list[list[int]]] = [[[3], [4]], [[2, 3], [2]], [[3], [3], [4]], [[1, 3, 4], [2, 3, 3]]]
for shapes in INCOMPATIBLE:
    t.check(value_error(lambda: bshape(shapes)) != "", f"test_incompatible_shapes_raise_valueerror {shapes}")
    t.check(value_error(lambda: bshape(shapes[::-1])) != "", f"test_incompatible_shapes_raise_valueerror {shapes[::-1]}")

for shapes, expected in BY_ONES + BY_PREPENDING:
    t.check(bshape(shapes) == expected, f"test_same_as_ufunc's shape {shapes}")
    same_as_ufunc(shapes[0], shapes[1], False, False)
    same_as_ufunc(shapes[1], shapes[0], False, False)
    same_as_ufunc(shapes[0], shapes[1], True, False)
    if shapes[0] != [] and shapes[1] != []:
        same_as_ufunc(shapes[0], shapes[1], False, True)
        same_as_ufunc(shapes[0], shapes[1], True, True)

SUCCEEDS: list[tuple[list[list[int]], list[int]]] = [
    ([[]], []),
    ([[7]], [7]),
    ([[1, 2], [2]], [1, 2]),
    ([[1, 1]], [1, 1]),
    ([[1, 1], [3, 4]], [3, 4]),
    ([[6, 7], [5, 6, 1], [7], [5, 1, 7]], [5, 6, 7]),
    ([[5, 6, 1]], [5, 6, 1]),
    ([[1, 3], [3, 1]], [3, 3]),
    ([[1, 0], [0, 0]], [0, 0]),
    ([[0, 1], [0, 0]], [0, 0]),
    ([[1, 0], [0, 1]], [0, 0]),
    ([[1, 1], [0, 0]], [0, 0]),
    ([[1, 1], [1, 0]], [1, 0]),
    ([[1, 1], [0, 1]], [0, 1]),
    ([[], [0]], [0]),
    ([[0], [0, 0]], [0, 0]),
    ([[0], [0, 1]], [0, 0]),
    ([[1], [0, 0]], [0, 0]),
    ([[], [0, 0]], [0, 0]),
    ([[1, 1], [0]], [1, 0]),
    ([[1], [0, 1]], [0, 1]),
    ([[1], [1, 0]], [1, 0]),
    ([[], [1, 0]], [1, 0]),
    ([[], [0, 1]], [0, 1]),
    ([[1], [3]], [3]),
    ([[2], [3, 2]], [3, 2]),
]
for shapes, expected in SUCCEEDS:
    t.check(bshape(shapes) == expected, f"test_broadcast_shapes_succeeds {shapes}")
t.check(bshape([[1, 2]] * 32) == [1, 2], "test_broadcast_shapes_succeeds 32 x (1, 2)")
t.check(bshape([[1, 2]] * 100) == [1, 2], "test_broadcast_shapes_succeeds 100 x (1, 2)")
t.check(bshape([[2]] * 32) == [2], "test_broadcast_shapes_succeeds gh-5862")
RAISES: list[list[list[int]]] = [
    [[3], [4]],
    [[2, 3], [2]],
    [[3], [3], [4]],
    [[1, 3, 4], [2, 3, 3]],
    [[1, 2], [3, 1], [3, 2], [10, 5]],
    [[2], [2, 3]],
]
for shapes in RAISES:
    t.check(value_error(lambda: bshape(shapes)) != "", f"test_broadcast_shapes_raises {shapes}")
t.check(value_error(lambda: bshape([[2]] * 32 + [[3]] * 32)) != "", "test_broadcast_shapes_raises gh-5862")

# ---- numpy/_core/tests/test_multiarray.py: methods, 0-d subscripts, creation
t.group("reshape, transpose, ravel (test_multiarray.py TestMethods)")
arr = array2([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [10.0, 11.0, 12.0]])
twelve = [float(i) for i in range(1, 13)]
t.check(is_array(arr.reshape([2, 6]), [2, 6], twelve), "test_reshape (2, 6)")
t.check(is_array(arr.reshape([3, 4]), [3, 4], twelve), "test_reshape (3, 4)")
t.check(is_array(arr.T.reshape([3, 4]), [3, 4], [1.0, 4.0, 7.0, 10.0, 2.0, 5.0, 8.0, 11.0, 3.0, 6.0, 9.0, 12.0]), "test_reshape of a.T")
t.check(is_array(array2([[1.0, 2.0], [3.0, 4.0]]).T, [2, 2], [1.0, 3.0, 2.0, 4.0]), "test_transpose")
a = array2([[0.0, 1.0], [2.0, 3.0]])
t.check(a.values() == [0.0, 1.0, 2.0, 3.0] and a.values() == a.reshape([-1]).values(), "test_ravel C order")
a = fortran([[0.0, 1.0], [2.0, 3.0]])
t.check(not a.contiguous() and a.values() == [0.0, 1.0, 2.0, 3.0] and a.values() == a.reshape([-1]).values(), "test_ravel of order='F'")
t.check(flip(array2([[0.0, 1.0], [2.0, 3.0]])).values() == [2.0, 3.0, 0.0, 1.0], "test_ravel of a[::-1, :]")
t.check(flip(arange(4)).reshape([2, 2]).values() == [3.0, 2.0, 1.0, 0.0], "test_ravel of arange(4)[::-1].reshape(2, 2)")
t.check(zeros([]).values() == [0.0], "test_ravel of a 0-d array")
b = stepped(arange(2**4 * 2), 0, 2).reshape([2, 2, 2, 2])
t.check(stepped(b, 3, 2).values() == [0.0, 4.0, 8.0, 12.0, 16.0, 20.0, 24.0, 28.0], "test_ravel of b[..., ::2]")
t.check(stepped(b, 0, 2).values() == [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0], "test_ravel of b[::2, ...]")

t.group("0-d arrays and creation (TestZeroRank, TestCreation)")
z0 = zeros([])
t.check(z0[()] == 0.0, "test_empty_subscript a[()]")
t.check(index_error(lambda: z0[0]) != "", "test_invalid_subscript a[0]")
d = zeros([13])
t.check(len([v for v in d.values() if v != 0.0]) == 0 and total(d) == 0.0, "test_zeros")
big = value_error(lambda: zeros([3037000500, 3037000500]))
t.check(big == "array is too big; `arr.size * arr.dtype.itemsize` is larger than the maximum possible size.", "test_too_big_error")
print("zeros((3037000500, 3037000500)):", big)

# ---- TestStats
t.group("mean (TestStats)")
m = mean(zeros([0, 3]))
t.check(m != m, "test_empty: the mean of an empty array is nan")
rmat = array2([
    [0.8817035384837327, 0.28917661385918403, 0.8710360723907997, 0.12506576556030302, 0.176316778274328],
    [0.3174256694363563, 0.2050983095184159, 0.202721707353695, 0.11991904470480697, 0.5945046160189026],
    [0.6952467475474361, 0.6674661052967773, 0.6752115237507794, 0.18336355798943482, 0.17105537293364048],
    [0.4580441599582623, 0.5005837561525562, 0.6502371117525205, 0.5588432258239375, 0.11493222820706517],
])
t.check(almost(mean(rmat) * prod(rmat.shape), total(rmat), 7), "test_mean_values axis=None")

# ---- TestDot (np.dot of 2-D arrays) and the matmul tests
t.group("dot and matmul of 2-D arrays (TestDot, MatmulCommon, TestMatmul)")
A = array2([
    [0.8666370428503979, 0.2631448495974139],
    [0.131408478173487, 0.041593443747687364],
    [0.23892433469051455, 0.6454746004955415],
    [0.7905993520222332, 0.6014424381923764],
])
b1 = array2([[0.33429937148835265], [0.11942846158833154]])
b3 = array2([[0.6021133114626169, 0.25128495916256977]])
t.check(all_almost(matmul(A.T, A), [[1.45046013, 0.86323640], [0.86323640, 0.84934569]], 7), "test_dotmatmat")
t.check(all_almost(matmul(A, b1), [[0.32114320], [0.04889721], [0.15696029], [0.33612621]], 7), "test_dotmatvec")
t.check(all_almost(matmul(b3, A.T), [[0.58793804, 0.08957460, 0.30605758, 0.62716383]], 7), "test_dotvecmat2")
t.check(all_almost(matmul(b1, b3), [[0.20128610, 0.08400440], [0.07190947, 0.03001058]], 7), "test_dotvecvecouter")
t.check(all_almost(matmul(b3, b1), [[0.23129668]], 7), "test_dotvecvecinner")
ca = array2([[1.0, 2.0], [3.0, 4.0]])
fa = fortran([[1.0, 2.0], [3.0, 4.0]])
res = matmul(ca, ca)
t.check(matmul(ca, fa).values() == res.values() and matmul(fa, ca).values() == res.values() and matmul(fa, fa).values() == res.values(), "test_dot_array_order")
t.check(value_error(lambda: matmul(zeros([1, 2]) + 1.0, zeros([3, 1]) + 1.0)) != "", "test_exceptions: mismatched matrix matrix")
m1 = array2([[1.0, 2.0], [3.0, 4.0]])
m2 = array2([[1.0, 0.0], [1.0, 1.0]])
t.check(is_array(matmul(m1, m2), [2, 2], [3.0, 2.0, 7.0, 4.0]) and is_array(m1 @ m2, [2, 2], [3.0, 2.0, 7.0, 4.0]), "test_matrix_matrix_values m1 @ m2")
t.check(is_array(matmul(m2, m1), [2, 2], [1.0, 2.0, 4.0, 6.0]) and is_array(m2 @ m1, [2, 2], [1.0, 2.0, 4.0, 6.0]), "test_matrix_matrix_values m2 @ m1")
t.check(is_array(matmul(zeros([3, 0]), zeros([0, 3])), [3, 3], [0.0] * 9), "test_matmul_empty")


def exact(a: NDArray, b: NDArray) -> list[float]:
    # the matrix product from the items in C order, one product and one sum at a time: exact for these
    # small integers, whatever the order
    av = a.values()
    bv = b.values()
    k = a.shape[1]
    n = b.shape[1]
    out: list[float] = []
    for i in range(a.shape[0]):
        for j in range(n):
            s = 0.0
            for p in range(k):
                s += av[i * k + p] * bv[p * n + j]
            out.append(s)
    return out


e1 = arange(15).reshape([5, 3])
e2 = arange(21).reshape([3, 7])
e3 = stepped(arange(30).reshape([5, 6]), 1, 2)
e0 = zeros([3, 0])
PAIRS: list[tuple[NDArray, NDArray]] = [
    (e1, e2), (e2.T, e1.T), (e2.T.copy(), e1.T), (e2.T, e1.T.copy()),
    (e1, e1.T), (e1.T, e1), (e1, e3.T), (e3, e1.T), (e3, e3.T), (e3.T, e3),
    (e3, e2), (e2.T, e3.T), (e2.T.copy(), e3.T),
    (e0, e0.T), (e0.T, e0), (e1, e0), (e0.T, e1.T),
]
for p, q in PAIRS:
    r1 = matmul(p, q)
    r2 = p @ q
    r3 = matmul(p.copy(), q.copy())
    what = f"test_dot_equivalent {p.shape} {p.strides} @ {q.shape} {q.strides}"
    t.check(r1.shape == r2.shape == r3.shape == [p.shape[0], q.shape[1]], what)
    t.check(r1.values() == r2.values() == r3.values() == exact(p, q), what)
x = array2([[1.0, 5.0, 25.0, 125.0, 625.0]])
y = array2([[20.0], [160.0], [640.0], [1280.0], [1024.0]])
t.check(matmul(x, flip(y).copy()).values() == matmul(x, flip(y)).values(), "test_dot_negative_stride (ticket #588)")

# ---- numpy/_core/tests/test_ufunc.py
t.group("sum (test_ufunc.py TestUfunc)")
a = zeros([500]) + 1.0
t.check(almost(total(a / 10.0) - 500 / 10.0, 0.0, 13), "test_sum_stability float64")
for v in [0, 1, 2, 7, 8, 9, 15, 16, 19, 127, 128, 1024, 1235]:
    tgt = float(v * (v + 1) / 2)
    d = arange(v) + 1.0
    t.check(almost(total(d), tgt, 7), f"test_sum np.arange(1, {v + 1})")
    t.check(almost(total(view(d, range(v)[::-1])), tgt, 7), f"test_sum np.arange(1, {v + 1})[::-1]")
d = zeros([500]) + 1.0
t.check(almost(total(view(d, range(500)[::2])), 250.0, 7), "test_sum d[::2]")
t.check(almost(total(view(d, range(500)[1::2])), 250.0, 7), "test_sum d[1::2]")
t.check(almost(total(view(d, range(500)[::3])), 167.0, 7), "test_sum d[::3]")
t.check(almost(total(view(d, range(500)[1::3])), 167.0, 7), "test_sum d[1::3]")
t.check(almost(total(view(d, range(500)[::-2])), 250.0, 7), "test_sum d[::-2]")
t.check(almost(total(view(d, range(500)[-1::-2])), 250.0, 7), "test_sum d[-1::-2]")
t.check(almost(total(view(d, range(500)[::-3])), 167.0, 7), "test_sum d[::-3]")
t.check(almost(total(view(d, range(500)[-1::-3])), 167.0, 7), "test_sum d[-1::-3]")
d = zeros([1]) + 1.0
d += d
t.check(almost(d[0], 2.0, 7), "test_sum: d += d")

# ---- test_umath.py, test_indexerrors.py, test_indexing.py
t.group("division and indexing (TestDivision, TestIndexErrors, TestIndexing)")
xi = array([5.0, 10.0, 90.0, 100.0, -5.0, -10.0, -90.0, -100.0, -120.0])
t.check((xi / 100).values() == [0.05, 0.1, 0.9, 1.0, -0.05, -0.1, -0.9, -1.0, -1.2], "test_division_int x / 100")


def assign(a: NDArray, k: tuple[int, int], v: float) -> None:
    a[k] = v


g = array2([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
t.check(g.row(0).values() == [1.0, 2.0, 3.0] and g.row(-1).values() == [7.0, 8.0, 9.0], "test_single_int_index")
t.check(index_error(lambda: g.row(1 << 30)) != "", "test_single_int_index out of bounds")
t.check(index_error(lambda: zeros([0, 10]).row(12)) != "", "test_mapping a[12] of shape (0, 10)")
z35 = zeros([3, 5])
t.check(index_error(lambda: z35[10, 20]) != "", "test_mapping a[10, 20]")
t.check(index_error(lambda: assign(z35, (10, 20), 1.0)) != "", "test_mapping a[10, 20] = 1")
z30 = zeros([3, 0])
t.check(index_error(lambda: z30[1, 0]) != "", "test_mapping a[1, 0] of shape (3, 0)")
t.check(index_error(lambda: assign(z30, (1, 0), 1.0)) != "", "test_mapping a[1, 0] = 1 of shape (3, 0)")
msg = index_error(lambda: z35[1, 2, 3, 4, 5])
t.check("too many indices for array: array is 2-dimensional, but 5 were indexed" in msg, "test_mapping_error_message")

for i in range(len(t.groups)):
    print(f"{t.groups[i]}: {t.counts[i]} assertions hold")
print("in all", sum(t.counts))
