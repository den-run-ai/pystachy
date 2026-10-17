"""ndarray: a float64 n-dimensional array in typed Python, after NumPy's ndarray.

usage: from ndarray import NDArray, array, array2, arange, zeros, total, sum_axis, matmul

An NDArray is a flat list[float] with a shape, element strides and an offset, so a transpose, a row
and a reshape of contiguous data are views of the same list, as NumPy's are. Arithmetic with
another array or a number broadcasts as NumPy does; the operators make a new contiguous array, and
add(), subtract(), multiply(), divide() and the operators +=, -=, *= and /= can write into an
existing one instead. Division by zero gives NumPy's inf and nan.

Summation follows one policy (README.md): total() and mean() add pairwise, eight accumulators
over blocks of up to 128 items, in memory order for a C- or F-ordered array and in C order for
other views; sum_axis() adds each line along the fastest axis pairwise, and otherwise
adds the lines of the other axis one after another into one result. That is NumPy's summation,
and the tests find np.sum's results for such arrays, but the order of additions decides the
rounding: ill-conditioned sums can differ by more than the last digit in another order.

The subset has no slice objects, reflected operators or comparison methods that return arrays:
a[1:3], 2.0 * a and a > x are written a.row(i), a * 2.0 and greater(a, x) here. a[i, j] = v
needs a 2-D array (__setitem__ cannot be a template). See README.md.
"""
import math


def _prod(xs: list[int]) -> int:
    n = 1
    for x in xs:
        n *= x
    return n


def _cstrides(shape: list[int]) -> list[int]:
    # the element strides of a C-order (row-major) array of this shape
    st = [0] * len(shape)
    acc = 1
    k = len(shape) - 1
    while k >= 0:
        st[k] = acc
        acc *= shape[k]
        k -= 1
    return st


def _shape_str(shape: list[int]) -> str:
    # a shape as NumPy's messages write it: (3,) or (2,3)
    if len(shape) == 1:
        return f"({shape[0]},)"
    return "(" + ",".join([str(d) for d in shape]) + ")"


def _new_shape(shape: list[int]) -> list[int]:
    # a copy of a new array's shape, checked as NumPy checks it: no negative dimension, and a size in
    # bytes that fits in 64 bits. NumPy multiplies the nonzero dimensions by the 8 bytes of a float64,
    # so a shape with a 0 in it can be too big too
    for d in shape:
        if d < 0:
            raise ValueError("negative dimensions are not allowed")
    nbytes = 8
    for d in shape:
        if d != 0:
            if nbytes > 9223372036854775807 // d:
                raise ValueError("array is too big; `arr.size * arr.dtype.itemsize` is larger than the maximum possible size.")
            nbytes *= d
    return list(shape)


def _index(i: int, n: int, axis: int) -> int:
    # i along an axis of n items, from either end, with NumPy's IndexError
    if i < -n or i >= n:
        raise IndexError(f"index {i} is out of bounds for axis {axis} with size {n}")
    return i + n if i < 0 else i


class NDArray:
    def __init__(self, data: list[float], shape: list[int], strides: list[int], offset: int) -> None:
        self.data = data
        self.shape = shape
        self.strides = strides
        self.offset = offset

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        return _prod(self.shape)

    def contiguous(self) -> bool:
        # C order, as NumPy's C_CONTIGUOUS flag tests it: the stride of an axis of length 1 does not
        # matter, and an empty array is contiguous
        if self.size == 0:
            return True
        acc = 1
        k = len(self.shape) - 1
        while k >= 0:
            if self.shape[k] != 1:
                if self.strides[k] != acc:
                    return False
                acc *= self.shape[k]
            k -= 1
        return True

    def whole(self) -> bool:
        # a contiguous array over all of its list, as a new array is (not a view of part of one)
        return self.offset == 0 and self.size == len(self.data) and self.contiguous()

    @property
    def T(self) -> "NDArray":
        # the transpose: a view with the axes reversed
        return NDArray(self.data, self.shape[::-1], self.strides[::-1], self.offset)

    def copy(self) -> "NDArray":
        # a new C-ordered array with its own list
        return _unary(self, _same)

    def reshape(self, shape: list[int]) -> "NDArray":
        # a view of contiguous data, otherwise of a contiguous copy, as NumPy copies only when it
        # must. One negative entry is the unknown dimension NumPy infers.
        dims = list(shape)
        unknown = -1
        known = 1
        for k in range(len(dims)):
            if dims[k] < 0:
                if unknown >= 0:
                    raise ValueError("can only specify one unknown dimension")
                unknown = k
            else:
                known *= dims[k]
        if unknown >= 0:
            if known == 0 or self.size % known != 0:
                text = [str(d) for d in dims]
                text[unknown] = "newaxis"
                raise ValueError(f"cannot reshape array of size {self.size} into shape ({','.join(text)})")
            dims[unknown] = self.size // known
        elif known != self.size:
            raise ValueError(f"cannot reshape array of size {self.size} into shape {_shape_str(dims)}")
        # Even an empty result must have representable byte extents and strides.
        dims = _new_shape(dims)
        src = ascontiguous(self)
        return NDArray(src.data, dims, _cstrides(dims), src.offset)

    def row(self, i: int) -> "NDArray":
        # a[i]: a view of one index along the first axis
        if self.ndim == 0:
            raise IndexError("too many indices for array: array is 0-dimensional, but 1 were indexed")
        i = _index(i, self.shape[0], 0)
        return NDArray(self.data, self.shape[1:], self.strides[1:], self.offset + i * self.strides[0])

    def _pos(self, key) -> int:
        # a template: the data index of a[key], key a tuple of one int per axis
        if len(key) > self.ndim:
            raise IndexError(f"too many indices for array: array is {self.ndim}-dimensional, but {len(key)} were indexed")
        if len(key) < self.ndim:
            raise IndexError(f"indexing {len(key)} of the {self.ndim} axes makes a view: use a.row(i)")
        p = self.offset
        k = 0
        for i in key:
            p += _index(i, self.shape[k], k) * self.strides[k]
            k += 1
        return p

    def __getitem__(self, key):
        # a template: a[i] of a 1-D array, a[i, j, ...] with an index for every axis
        if isinstance(key, int):
            return self.data[self._pos((key,))]
        return self.data[self._pos(key)]

    def __setitem__(self, key: tuple[int, int], v: float) -> None:
        # a[i, j] = v, also through a view: the data is shared
        self.data[self._pos(key)] = v

    def __len__(self) -> int:
        if self.ndim == 0:
            raise TypeError("len() of unsized object")
        return self.shape[0]

    def __add__(self, other):
        return add(self, other)

    def __sub__(self, other):
        return subtract(self, other)

    def __mul__(self, other):
        return multiply(self, other)

    def __truediv__(self, other):
        return divide(self, other)

    def __iadd__(self, other):
        return add(self, other, self)

    def __isub__(self, other):
        return subtract(self, other, self)

    def __imul__(self, other):
        return multiply(self, other, self)

    def __itruediv__(self, other):
        return divide(self, other, self)

    def __neg__(self) -> "NDArray":
        return _unary(self, _neg)

    def __matmul__(self, other: "NDArray") -> "NDArray":
        return matmul(self, other)

    def values(self) -> list[float]:
        # the items in C order, as a.ravel().tolist() gives them
        c = ascontiguous(self)
        return c.data[c.offset : c.offset + c.size]

    def __repr__(self) -> str:
        # not NumPy's repr: the items in C order, then the shape
        return f"array({self.values()}, shape={_shape_str(self.shape)})"


def _add(x: float, y: float) -> float:
    return x + y


def _sub(x: float, y: float) -> float:
    return x - y


def _mul(x: float, y: float) -> float:
    return x * y


def _neg(x: float) -> float:
    return -x


def _same(x: float) -> float:
    return x


def true_divide(x: float, y: float) -> float:
    # x / y as NumPy divides float64s: inf, -inf or nan for a zero y (NumPy also warns), where
    # Python's float division raises ZeroDivisionError
    if y == 0.0:
        if x == 0.0 or x != x:
            return math.nan
        return math.copysign(math.inf, x) * math.copysign(1.0, y)
    return x / y


def add(a: NDArray, b, out: NDArray | None = None) -> NDArray:
    # np.add(a, b, out=out): b an array or a number; a new array unless out is given
    return _binary(a, _as_array(b), _add, out)


def subtract(a: NDArray, b, out: NDArray | None = None) -> NDArray:
    return _binary(a, _as_array(b), _sub, out)


def multiply(a: NDArray, b, out: NDArray | None = None) -> NDArray:
    return _binary(a, _as_array(b), _mul, out)


def divide(a: NDArray, b, out: NDArray | None = None) -> NDArray:
    return _binary(a, _as_array(b), true_divide, out)


def _as_array(v):
    # a template: a float or an int becomes a 0-d array, an NDArray stays as it is. (A test of
    # isinstance(v, NDArray) first would not be decided at compile time: an object may be None.)
    if isinstance(v, float) or isinstance(v, int):
        return NDArray([float(v)], [], [], 0)
    return v


def array(xs: list[float]) -> NDArray:
    return NDArray(list(xs), [len(xs)], [1], 0)


def array2(rows: list[list[float]]) -> NDArray:
    n = len(rows[0]) if rows else 0
    data: list[float] = []
    for r in rows:
        if len(r) != n:
            raise ValueError(f"rows of different lengths: {len(r)} and {n}")
        data.extend(r)
    return NDArray(data, [len(rows), n], [n, 1], 0)


def zeros(shape: list[int]) -> NDArray:
    dims = _new_shape(shape)
    return NDArray([0.0] * _prod(dims), dims, _cstrides(dims), 0)


def arange(n: int) -> NDArray:
    # np.arange(n) as floats: no items for an n below 1
    m = max(n, 0)
    return NDArray([float(i) for i in range(m)], [m], [1], 0)


def ascontiguous(a: NDArray) -> NDArray:
    # a itself if it is C-contiguous, otherwise a contiguous copy
    if a.contiguous():
        return a
    return _unary(a, _same)


def _broadcast_shapes(a: list[int], b: list[int]) -> list[int]:
    # NumPy's broadcasting: shapes align at their last axes, and an axis of 1 repeats
    n = max(len(a), len(b))
    out: list[int] = []
    for k in range(n):
        ka = len(a) - n + k
        kb = len(b) - n + k
        da = a[ka] if ka >= 0 else 1
        db = b[kb] if kb >= 0 else 1
        if da == db or db == 1:
            out.append(da)
        elif da == 1:
            out.append(db)
        else:
            raise ValueError(f"operands could not be broadcast together with shapes {_shape_str(a)} {_shape_str(b)} ")
    return out


def _bstrides(a: NDArray, shape: list[int]) -> list[int]:
    # a's element strides against a broadcast shape: 0 along the axes where a repeats
    n = len(shape)
    st = [0] * n
    for k in range(n):
        j = len(a.shape) - n + k
        if j >= 0 and a.shape[j] != 1:
            st[k] = a.strides[j]
    return st


def _unshared(x: NDArray, out: NDArray) -> NDArray:
    # x, or a copy of it where writing out could change items of x before they are read: out shares
    # x's list in another layout. (Item i of an input in out's own layout is read before out's item i
    # is written, so a += b needs no copy.)
    if x.data is out.data and (x.offset != out.offset or x.shape != out.shape or x.strides != out.strides):
        return x.copy()
    return x


def _unary(a: NDArray, op) -> NDArray:
    # a template on op, as _binary is
    shape = list(a.shape)
    if a.contiguous():
        d = a.data
        o = a.offset
        return NDArray([op(d[o + i]) for i in range(a.size)], shape, _cstrides(shape), 0)
    return _binary(a, NDArray([0.0], [], [], 0), _first(op), None)


def _first(op):
    def f(x: float, y: float) -> float:
        return op(x)

    return f


def _binary(a: NDArray, b: NDArray, op, out: NDArray | None) -> NDArray:
    # a template on op: each operation gets its own specialization, in which op() is a direct call
    # that LLVM inlines into the loop. The result goes into out, or a new array.
    shape = _broadcast_shapes(a.shape, b.shape)
    n = _prod(shape)
    if out is None:
        res = NDArray([0.0] * n, shape, _cstrides(shape), 0)
    else:
        if out.shape != shape:
            raise ValueError(
                f"non-broadcastable output operand with shape {_shape_str(out.shape)} doesn't match "
                + f"the broadcast shape {_shape_str(shape)}"
            )
        if not out.contiguous():
            raise ValueError("out must be C-contiguous here")
        a = _unshared(a, out)
        b = _unshared(b, out)
        res = out
    od = res.data
    oo = res.offset
    ad = a.data
    bd = b.data
    ao = a.offset
    bo = b.offset
    if n == 0:
        return res
    if a.shape == shape and a.contiguous():
        if b.shape == shape and b.contiguous():
            for i in range(n):
                od[oo + i] = op(ad[ao + i], bd[bo + i])
            return res
        if b.size == 1:
            y = bd[bo]
            for i in range(n):
                od[oo + i] = op(ad[ao + i], y)
            return res
    nd = len(shape)
    if nd == 0:
        od[oo] = op(ad[ao], bd[bo])
        return res
    # the last axis is the inner loop; the others advance like an odometer
    sa = _bstrides(a, shape)
    sb = _bstrides(b, shape)
    inner = shape[nd - 1]
    ia = sa[nd - 1]
    ib = sb[nd - 1]
    idx = [0] * nd
    pa = ao
    pb = bo
    po = oo
    for _ in range(n // inner):
        for j in range(inner):
            od[po + j] = op(ad[pa + j * ia], bd[pb + j * ib])
        po += inner
        k = nd - 2
        while k >= 0:
            idx[k] += 1
            pa += sa[k]
            pb += sb[k]
            if idx[k] < shape[k]:
                break
            pa -= sa[k] * shape[k]
            pb -= sb[k] * shape[k]
            idx[k] = 0
            k -= 1
    return res


def pairwise(d: list[float], lo: int, n: int, step: int) -> float:
    # pairwise summation of d[lo], d[lo + step], ... (n items), as NumPy's pairwise_sum adds them
    # (numpy/_core/src/umath/loops_utils.h.src): eight accumulators over blocks of up to 128 items,
    # the halves of longer runs added recursively. Its error grows with log n where adding in order
    # lets it grow with n; it is not compensated.
    if n < 8:
        res = -0.0
        for i in range(n):
            res += d[lo + i * step]
        return res
    if n <= 128:
        r0 = d[lo]
        r1 = d[lo + step]
        r2 = d[lo + 2 * step]
        r3 = d[lo + 3 * step]
        r4 = d[lo + 4 * step]
        r5 = d[lo + 5 * step]
        r6 = d[lo + 6 * step]
        r7 = d[lo + 7 * step]
        m = n - n % 8
        i = 8
        while i < m:
            p = lo + i * step
            r0 += d[p]
            r1 += d[p + step]
            r2 += d[p + 2 * step]
            r3 += d[p + 3 * step]
            r4 += d[p + 4 * step]
            r5 += d[p + 5 * step]
            r6 += d[p + 6 * step]
            r7 += d[p + 7 * step]
            i += 8
        res = ((r0 + r1) + (r2 + r3)) + ((r4 + r5) + (r6 + r7))
        while i < n:
            res += d[lo + i * step]
            i += 1
        return res
    n2 = n // 2
    n2 -= n2 % 8
    return pairwise(d, lo, n2, step) + pairwise(d, lo + n2 * step, n - n2, step)


def _dense(a: NDArray) -> bool:
    # whether a's items fill data[offset:offset + size] in some order of its axes, as those of a C- or
    # an F-ordered array (a transpose) do
    acc = 1
    for k in sorted(range(a.ndim), key=lambda j: a.strides[j]):
        if a.shape[k] != 1 and a.strides[k] != acc:
            return False
        acc *= a.shape[k]
    return True


def total(a: NDArray) -> float:
    # np.sum(a): pairwise, from 0.0 (so the sum of [-0.0] is 0.0), over the items in memory order for
    # a C- or F-ordered array, as NumPy adds them, and in C order for other views
    if _dense(a):
        return 0.0 + pairwise(a.data, a.offset, a.size, 1)
    c = ascontiguous(a)
    return 0.0 + pairwise(c.data, c.offset, c.size, 1)


def mean(a: NDArray) -> float:
    # np.mean(a): the sum divided by the count (nan for an empty array, where NumPy also warns)
    return true_divide(total(a), float(a.size))


def sum_axis(a: NDArray, axis: int) -> NDArray:
    # np.sum(a, axis=axis) of a 2-D array, in NumPy's order: where the summed axis is fastest
    # (ignoring singleton axes), each line along it pairwise; otherwise the lines of the other axis
    # one after another, from 0.0, into one result
    if a.ndim != 2:
        raise ValueError(f"sum_axis takes a 2-D array, not a {a.ndim}-D one")
    k = axis + 2 if axis < 0 else axis
    if k != 0 and k != 1:
        raise ValueError(f"axis {axis} is out of bounds for array of dimension 2")
    o = 1 - k
    n = a.shape[k]
    m = a.shape[o]
    sk = a.strides[k]
    so = a.strides[o]
    d = a.data
    # Reversal changes the traversal direction, not which axis is fastest. An unsummed
    # singleton axis contributes no traversal, regardless of its stride.
    if m == 1 or abs(sk) <= abs(so):
        return array([0.0 + pairwise(d, a.offset + j * so, n, sk) for j in range(m)])
    out = [0.0] * m
    for i in range(n):
        base = a.offset + i * sk
        for j in range(m):
            out[j] += d[base + j * so]
    return array(out)


def dot(a: NDArray, b: NDArray) -> float:
    # the inner product of two 1-D arrays, summed as total() sums: np.sum(a * b) (np.dot's BLAS
    # kernel adds in another order)
    if a.ndim != 1 or b.ndim != 1 or a.shape[0] != b.shape[0]:
        raise ValueError(f"shapes {_shape_str(a.shape)} and {_shape_str(b.shape)} not aligned")
    return total(a * b)


def matmul(a: NDArray, b: NDArray) -> NDArray:
    # a @ b of 2-D arrays: rows of a times b, accumulated row by row (BLAS adds in blocks, so the
    # results can differ from NumPy's in rounding)
    if a.ndim != 2 or b.ndim != 2:
        raise ValueError("matmul takes 2-D arrays here")
    if a.shape[1] != b.shape[0]:
        raise ValueError(
            "matmul: Input operand 1 has a mismatch in its core dimension 0, with gufunc signature "
            + f"(n?,k),(k,m?)->(n?,m?) (size {b.shape[0]} is different from {a.shape[1]})"
        )
    m = a.shape[0]
    k = a.shape[1]
    n = b.shape[1]
    ac = ascontiguous(a)
    bc = ascontiguous(b)
    A = ac.data
    B = bc.data
    rows = [B[bc.offset + p * n : bc.offset + (p + 1) * n] for p in range(k)]
    C: list[float] = []
    for i in range(m):
        crow = [0.0] * n
        base = ac.offset + i * k
        for p in range(k):
            aip = A[base + p]
            brow = rows[p]
            for j in range(n):
                crow[j] += aip * brow[j]
        C.extend(crow)
    return NDArray(C, [m, n], [n, 1], 0)


def greater(a: NDArray, x: float) -> list[bool]:
    # (a > x).ravel().tolist(): comparison methods return bool in the subset, so no __gt__ here
    return [v > x for v in a.values()]
