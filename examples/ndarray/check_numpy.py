"""check_numpy: ndarray and lazy, run by CPython, against NumPy on the same data.

usage: python3 check_numpy.py

It needs NumPy, which a compiled program cannot import, so it runs under CPython only;
tests/example_ndarray.py carries representative NumPy results into the compiled tests. The counts
it prints are test results, not guarantees (README.md):

- exact: elementwise arithmetic, broadcasting, views, out= and in-place operators, and the sums of
  C- and F-ordered arrays, which add in NumPy's order, must equal NumPy's float64 results (signed
  zeros, infinities and nans included); errors must have NumPy's messages
- within 1e-12 relative: matmul() and dot() against BLAS (np.dot, @), and well-conditioned sums in
  another order than NumPy's
- policy: total() of other views sums the C-order items pairwise; lazy sum() equals Python's sum()
  of the items; an ill-conditioned sum shows how far orders can differ

It first checks that its own comparisons reject what they must: a nan against a number, lists of
different lengths, an infinity against a large number. It stops at the first failure, exit status 1.
"""
import math
import sys

import numpy as np

from lazy import lazy
from ndarray import (NDArray, add, arange, array, array2, divide, dot, matmul, mean, multiply, pairwise,
                     subtract, sum_axis, total, zeros)

counts = {"exact": 0, "close": 0, "policy": 0, "self": 0}


class Differs(Exception):
    pass


def same(x: float, y: float) -> bool:
    # the same float64: a nan for a nan, and -0.0 for -0.0
    if x != x or y != y:
        return x != x and y != y
    return x == y and math.copysign(1.0, x) == math.copysign(1.0, y)


def exact(what: str, mine: NDArray, theirs: np.ndarray) -> None:
    if mine.shape != list(theirs.shape):
        raise Differs(f"{what}: shape {mine.shape} against {list(theirs.shape)}")
    xs = mine.values()
    ys = theirs.ravel().tolist()
    if len(xs) != len(ys):
        raise Differs(f"{what}: {len(xs)} items against {len(ys)}")
    for i in range(len(xs)):
        if not same(xs[i], ys[i]):
            raise Differs(f"{what}: item {i} is {xs[i]!r}, NumPy's {ys[i]!r}")
    counts["exact"] += 1


def exact_float(what: str, x: float, y: float, kind: str = "exact") -> None:
    if not same(x, float(y)):
        raise Differs(f"{what}: {x!r} against {float(y)!r}")
    counts[kind] += 1


def close(what: str, xs: list[float], ys: list[float]) -> None:
    # within 1e-12 of the largest |y|; a nan or an infinity on either side must be the same on both
    if len(xs) != len(ys):
        raise Differs(f"{what}: {len(xs)} items against {len(ys)}")
    finite = [abs(y) for y in ys if math.isfinite(y)]
    scale = max(finite + [1e-300])
    for i in range(len(xs)):
        x = xs[i]
        y = ys[i]
        if not (math.isfinite(x) and math.isfinite(y)):
            if not same(x, y):
                raise Differs(f"{what}: item {i} is {x!r}, NumPy's {y!r}")
        elif abs(x - y) > 1e-12 * scale:
            raise Differs(f"{what}: item {i} is {x!r}, NumPy's {y!r}")
    counts["close"] += 1


def raises(what: str, mine, theirs) -> None:
    # mine and theirs are calls that raise; their messages must be the same
    msgs = []
    for f in [mine, theirs]:
        try:
            f()
        except (ValueError, IndexError, TypeError) as e:
            msgs.append(str(e))
            continue
        raise Differs(f"{what}: no error")
    if msgs[0] != msgs[1]:
        raise Differs(f"{what}: {msgs[0]!r}, NumPy's {msgs[1]!r}")
    counts["exact"] += 1


def rejects(what: str, f) -> None:
    # a comparison that must fail
    try:
        f()
    except Differs:
        counts["self"] += 1
        return
    raise Differs(f"the checker accepted {what}")


def nd(x: np.ndarray) -> NDArray:
    # the same float64 values as a C-order NDArray
    c = np.ascontiguousarray(x, dtype=np.float64)
    return NDArray(c.ravel().tolist(), list(c.shape), [s // 8 for s in c.strides], 0)


def checks() -> None:
    rejects("nan against 1.0", lambda: close("t", [math.nan], [1.0]))
    rejects("1.0 against nan", lambda: close("t", [1.0], [math.nan]))
    rejects("inf against 1e308", lambda: close("t", [math.inf], [1e308]))
    rejects("lists of 1 and 2 items", lambda: close("t", [1.0], [1.0, 2.0]))
    rejects("a nan item", lambda: exact("t", array([math.nan]), np.array([1.0])))
    rejects("-0.0 against 0.0", lambda: exact("t", array([-0.0]), np.array([0.0])))
    rejects("a shape", lambda: exact("t", array([1.0, 2.0]), np.array([[1.0, 2.0]])))

    rng = np.random.default_rng(2026)
    a = rng.standard_normal((3, 4))
    b = rng.standard_normal((3, 4))
    row = rng.standard_normal(4)
    col = rng.standard_normal((3, 1))
    cube = rng.standard_normal((2, 3, 4))
    A, B, R, C, K = nd(a), nd(b), nd(row), nd(col), nd(cube)
    for name, f, g in [("+", add, np.add), ("-", subtract, np.subtract), ("*", multiply, np.multiply),
                       ("/", divide, np.divide)]:
        exact(f"a {name} b", f(A, B), g(a, b))
        exact(f"a {name} row", f(A, R), g(a, row))
        exact(f"a {name} col", f(A, C), g(a, col))
        exact(f"cube {name} a", f(K, A), g(cube, a))
        exact(f"col {name} cube", f(C, K), g(col, cube))
        exact(f"a.T {name} b.T", f(A.T, B.T), g(a.T, b.T))
        exact(f"a {name} 2.5", f(A, 2.5), g(a, 2.5))
        exact(f"a {name} 3", f(A, 3), g(a, 3))
        out, theirs = A.copy(), a.copy()
        exact(f"{name} into out", f(A, R, out), g(a, row, out=theirs))
        sq, sq_np = nd(cube[0, :3, :3]), cube[0, :3, :3].copy()
        exact(f"{name} into an operand's transpose", f(sq, sq.T, sq), g(sq_np, sq_np.T, out=sq_np))
    exact("-a", -A, -a)
    exact("-a.T", -(A.T), -(a.T))
    exact("a.T", A.T, a.T)
    exact("a.copy()", A.T.copy(), a.T.copy())
    exact("a.T.reshape(2, 6)", A.T.reshape([2, 6]), a.T.reshape(2, 6))
    exact("cube.reshape(4, -1).T", K.reshape([4, -1]).T, cube.reshape(4, -1).T)
    exact("cube.reshape(-1)", K.reshape([-1]), cube.reshape(-1))
    exact("cube[1]", K.row(1), cube[1])
    exact("cube[-1][2]", K.row(-1).row(2), cube[-1][2])
    exact_float("cube[1, 2, 3]", K[1, 2, 3], cube[1, 2, 3])
    exact("arange(-3)", arange(-3), np.arange(-3.0))
    exact("zeros((2, 0))", zeros([2, 0]), np.zeros((2, 0)))
    z = zeros([3, 1])
    z_np = np.zeros((3, 1))
    if z.T.reshape([3]).data is not z.data or not np.shares_memory(z_np.T.reshape(3), z_np):
        raise Differs("reshape of a transposed (3, 1) array should be a view, as in NumPy")
    counts["exact"] += 1
    ip, ip_np = A.copy(), a.copy()
    ip += R
    ip *= 2.0
    ip -= C
    ip /= 3
    ip_np += row
    ip_np *= 2.0
    ip_np -= col
    ip_np /= 3
    exact("+= *= -= /=", ip, ip_np)
    special = np.array([1.0, -1.0, 0.0, -0.0, np.inf, -np.inf, np.nan, 2.5])
    S = nd(special)
    with np.errstate(divide="ignore", invalid="ignore"):
        for zero in [0.0, -0.0]:
            exact(f"special / {zero!r}", S / zero, special / zero)
        exact("special / special", S / S, special / special)
        exact("special * special", S * S, special * special)
        exact("special - special", S - S, special - special)

    for n in [0, 1, 7, 8, 9, 127, 128, 129, 1000, 4097, 100003]:
        x = rng.standard_normal(n) * 1000.0
        exact_float(f"total, {n} items", total(nd(x)), np.sum(x))
        if n > 0:
            exact_float(f"mean, {n} items", mean(nd(x)), np.mean(x))
    exact_float("total of [-0.0]", total(array([-0.0])), np.sum(np.array([-0.0])))
    big = rng.standard_normal((300, 70))
    G = nd(big)
    exact_float("total of a transpose", total(G.T), np.sum(big.T))
    exact_float("total of a 3-D transpose", total(K.T), np.sum(cube.T))
    exact_float("total of a strided row", total(G.T.row(5)), np.sum(big.T[5]))
    exact_float("mean of a transpose", mean(G.T), np.mean(big.T))
    m = rng.standard_normal((50, 37))
    M = nd(m)
    for axis in [0, 1, -1]:
        exact(f"sum axis {axis}", sum_axis(M, axis), np.sum(m, axis=axis))
        exact(f"sum axis {axis} of the transpose", sum_axis(M.T, axis), np.sum(m.T, axis=axis))

    # Cancellation makes the wrong traversal order visible: pairwise gives 84, plain order 0.
    cols = array2([[v, v] for v in [1e16] + [1.0] * 100 + [-1e16]])
    cols_np = np.array(cols.values()).reshape(102, 2)
    for rstep in [1, -1]:
        for cstep in [1, -1]:
            off = (202 if rstep < 0 else 0) + (1 if cstep < 0 else 0)
            v = NDArray(cols.data, [102, 2], [2 * rstep, cstep], off)
            v_np = cols_np[::rstep, ::cstep]
            exact("sum reversed rows", sum_axis(v, 0), np.sum(v_np, axis=0))
            exact("sum transposed reversed rows", sum_axis(v.T, 1), np.sum(v_np.T, axis=1))
    singleton = NDArray(cols.data, [102, 1], [2, -1], 0)
    exact("sum strided singleton column", sum_axis(singleton, 0), np.sum(cols_np[:, :1], axis=0))
    exact("sum transposed singleton column", sum_axis(singleton.T, 1), np.sum(cols_np[:, :1].T, axis=1))

    # a 2-D view that is neither C- nor F-ordered: total() adds its C-order items, NumPy runs of
    # them in memory order; well-conditioned data agrees closely, ill-conditioned need not
    view = K.T.row(1)
    exact_float("total of a 2-D view is pairwise in C order", total(view),
                0.0 + pairwise(view.values(), 0, view.size, 1), "policy")
    close("total of a 2-D view against np.sum", [total(view)], [float(np.sum(cube.T[1]))])

    x = rng.standard_normal(10007)
    y = rng.standard_normal(10007)
    X, Y = nd(x), nd(y)
    d = lazy(X) - lazy(Y)
    exact_float("lazy sum is Python's sum()", (d * d).sum(), sum(((x - y) * (x - y)).tolist()), "policy")
    close("lazy sum against np.sum", [(d * d).sum()], [float(np.sum((x - y) * (x - y)))])
    exact("lazy x * y + 1", (lazy(X) * lazy(Y) + 1.0).evaluate(), x * y + 1.0)
    exact("lazy (x - 2) / y", ((lazy(X) - 2) / lazy(Y)).evaluate(), (x - 2) / y)
    into, into_np = X.copy(), x.copy()
    exact("lazy evaluate into an operand", (lazy(into) * lazy(Y) + lazy(into)).evaluate(into), into_np * y + into_np)
    exact_float("dot is np.sum(x * y)", dot(X, Y), np.sum(x * y))
    close("dot against np.dot", [dot(X, Y)], [float(np.dot(x, y))])
    canc = [1e16] + [1.0] * 100 + [-1e16]
    Z = array(canc)
    exact_float("total of [1e16, 1.0 x 100, -1e16]", total(Z), np.sum(np.array(canc)))
    exact_float("its lazy sum is math.fsum's", (lazy(Z) + 0.0).sum(), math.fsum(canc), "policy")
    if total(Z) != 84.0:
        raise Differs("the pairwise sum of the ill-conditioned list should lose 16 of its ones")
    counts["policy"] += 1
    p = rng.standard_normal((17, 23))
    q = rng.standard_normal((23, 9))
    P, Q = nd(p), nd(q)
    close("matmul", matmul(P, Q).values(), (p @ q).ravel().tolist())
    close("matmul of transposes", matmul(Q.T, P.T).values(), (q.T @ p.T).ravel().tolist())
    close("@", (P @ Q).values(), (p @ q).ravel().tolist())

    two = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    T = array2(two.tolist())
    raises("broadcast", lambda: T + array([1.0, 2.0]), lambda: two + np.array([1.0, 2.0]))
    raises("broadcast (3,1)", lambda: T + nd(col), lambda: two + col)
    raises("out shape", lambda: add(T, T, zeros([3])), lambda: np.add(two, two, out=np.zeros(3)))
    raises("in-place broadcast", lambda: add(array([1.0, 2.0, 3.0]), T, array([1.0, 2.0, 3.0])),
           lambda: np.add(np.ones(3), two, out=np.ones(3)))
    raises("reshape", lambda: T.reshape([4]), lambda: two.reshape(4))
    raises("reshape unknown", lambda: T.reshape([4, -1]), lambda: two.reshape(4, -1))
    raises("reshape two unknowns", lambda: T.reshape([-1, -1]), lambda: two.reshape(-1, -1))
    for huge in [[0, 4611686018427387904], [-1, 4611686018427387904], [0, 4294967296, 4294967296]]:
        raises("reshape empty with unrepresentable extents", lambda shape=huge: zeros([0]).reshape(shape),
               lambda shape=huge: np.zeros(0).reshape(shape))
    raises("negative dimensions", lambda: zeros([-1, -2]), lambda: np.zeros((-1, -2)))
    raises("index", lambda: T[2, 0], lambda: two[2, 0])
    raises("negative index", lambda: T[0, -4], lambda: two[0, -4])
    raises("too many indices", lambda: T[0, 0, 99], lambda: two[0, 0, 99])
    raises("1-D index", lambda: array([1.0])[3], lambda: np.array([1.0])[3])
    raises("1-D, two indices", lambda: array([1.0])[0, 0], lambda: np.array([1.0])[0, 0])
    raises("0-D row", lambda: zeros([]).row(0), lambda: np.zeros(())[0])
    raises("matmul", lambda: matmul(T, T), lambda: two @ two)


try:
    checks()
except Differs as e:
    print("DIFFERS:", e)
    sys.exit(1)
print(f"{counts['exact']} checks equal NumPy's results, {counts['close']} agree within 1e-12, "
      + f"{counts['policy']} check the summation policy, {counts['self']} check the checker (numpy {np.__version__})")
