"""Optional FP64/LP64 CBLAS matrix multiplication for this ndarray example.

The native program calls libblas.so.3 directly; no CPython or NumPy runtime is
needed. The library must export the LP64 cblas_dgemm ABI (32-bit C int dimensions,
64-bit double elements). ILP64 libraries require a different explicit binding.
Importing this module requires that library; ndarray.matmul stays independent.

Both operands are two-dimensional. Row-major matrices and their transposes
(including padded rows, and views at an offset) lend their lists directly, from
the view's first item (ffi.at); other views are packed in logical row-major
order. Every result has fresh storage, including products of operands which
share their data. There is no stale weight cache.
linear() computes PyTorch's Linear, x @ weight.T + bias, in one call by
accumulating the product into the bias.
"""

from ffi import at, c_int, extern

from ndarray import NDArray, _new_shape, zeros


@extern("libblas.so.3", "cblas_dgemm")
def _dgemm(layout: c_int, transa: c_int, transb: c_int, m: c_int, n: c_int, k: c_int,
           alpha: float, a: list[float], lda: c_int, b: list[float], ldb: c_int,
           beta: float, c: list[float], ldc: c_int) -> None: ...


def _check_matrix(a: NDArray) -> None:
    if a.ndim != 2 or len(a.strides) != 2:
        raise ValueError("BLAS matmul requires 2-D shapes and strides")
    for dimension in a.shape:
        if dimension < 0:
            raise ValueError("BLAS matmul dimensions must be nonnegative")
        if dimension > 2147483647:
            raise OverflowError("BLAS matmul dimension exceeds LP64 C int")
    # Packing a broadcast view must satisfy the same byte-extent limit as a
    # newly allocated array, even when its original storage is tiny.
    _new_shape(a.shape)
    _check_storage(a)


def _check_storage(a: NDArray) -> None:
    # Shape/stride ranks and nonnegative dimensions are checked by the caller.
    # Check every reachable index before values() can silently truncate a slice
    # or an FFI call can borrow native storage.
    count = len(a.data)
    empty = False
    for dimension in a.shape:
        if dimension == 0:
            empty = True
    if empty:
        if a.offset < 0 or a.offset > count:
            raise ValueError("BLAS view is outside its data")
        return
    if a.offset < 0 or a.offset >= count:
        raise ValueError("BLAS view is outside its data")
    low = a.offset
    high = a.offset
    for axis in range(a.ndim):
        steps = a.shape[axis] - 1
        if steps != 0:
            stride = a.strides[axis]
            # Check before multiplying: malformed strides can exceed int64, and
            # abs(INT64_MIN) itself overflows. Valid products stay within data.
            if stride >= 0:
                if stride > (count - 1 - high) // steps:
                    raise ValueError("BLAS view is outside its data")
                high += steps * stride
            else:
                if stride < -(low // steps):
                    raise ValueError("BLAS view is outside its data")
                low += steps * stride


def _operand(a: NDArray) -> tuple[list[float], int, int, int]:
    # Called only for nonempty, checked matrices: the list, the index of the
    # view's first item in it, from which C reads the matrix (ffi.at), and how:
    # CblasNoTrans=111 or CblasTrans=112, with a physical row stride. Lent views
    # reach no item outside the ones _check_storage has checked.
    if a.contiguous():
        return a.data, a.offset, 111, a.shape[1]
    if a.strides[1] == 1 and a.shape[1] <= a.strides[0] <= 2147483647:
        return a.data, a.offset, 111, a.strides[0]
    if a.strides[0] == 1 and a.shape[0] <= a.strides[1] <= 2147483647:
        return a.data, a.offset, 112, a.strides[1]
    result: list[float] = []
    for row in range(a.shape[0]):
        base = a.offset + row * a.strides[0]
        for column in range(a.shape[1]):
            result.append(a.data[base + column * a.strides[1]])
    return result, 0, 111, a.shape[1]


def matmul(a: NDArray, b: NDArray) -> NDArray:
    """Return a @ b using LP64 CBLAS, packing views and allocating fresh output."""
    _check_matrix(a)
    _check_matrix(b)
    if a.shape[1] != b.shape[0]:
        raise ValueError("BLAS matmul inner dimensions do not match")
    rows = a.shape[0]
    inner = a.shape[1]
    columns = b.shape[1]
    result = zeros([rows, columns])
    # No pointer is passed for an empty product; K=0 must still yield an MxN
    # zero matrix. Nonempty leading dimensions below are always at least one.
    if rows == 0 or columns == 0 or inner == 0:
        return result
    left, lo, transa, lda = _operand(a)
    right, ro, transb, ldb = _operand(b)
    # CblasRowMajor=101. Result storage cannot alias either input.
    _dgemm(101, transa, transb, rows, columns, inner, 1.0, at(left, lo), lda,
           at(right, ro), ldb, 0.0, result.data, columns)
    return result


def linear(x: NDArray, weight: NDArray, bias: NDArray | None) -> NDArray:
    """Return x @ weight.T + bias (PyTorch's Linear layout) in one cblas_dgemm call.

    The result starts as the bias repeated for every row, and BLAS adds the
    product into it (beta=1). That replaces zero-filling the output and a
    separate pass adding the bias. BLAS adds its partial sums to the bias in its
    own order, so a library that splits the inner dimension can round differently
    from matmul(x, weight.T) + bias; agreement is within the BLAS tolerance.
    Without a bias this is matmul(x, weight.T).
    """
    right = weight.T
    if bias is None:
        return matmul(x, right)
    _check_matrix(x)
    _check_matrix(right)
    if x.shape[1] != right.shape[0]:
        raise ValueError("BLAS linear inner dimensions do not match")
    rows = x.shape[0]
    inner = x.shape[1]
    columns = right.shape[1]
    if bias.shape != [columns]:
        raise ValueError("BLAS linear bias must have one value per output feature")
    if len(bias.strides) != 1:
        raise ValueError("BLAS linear bias requires one stride")
    # As zeros() would for the product: the output's byte extent must be valid.
    _new_shape([rows, columns])
    _check_storage(bias)
    # values() reads a strided bias in logical order; the result is a new list.
    values = bias.values()
    if len(values) != columns:
        raise ValueError("BLAS linear bias storage does not match its shape")
    result = NDArray(values * rows, [rows, columns], [columns, 1], 0)
    # An empty product contributes nothing (K=0 leaves the bias); call no BLAS.
    if rows == 0 or columns == 0 or inner == 0:
        return result
    left, lo, transa, lda = _operand(x)
    weights, wo, transb, ldb = _operand(right)
    _dgemm(101, transa, transb, rows, columns, inner, 1.0, at(left, lo), lda,
           at(weights, wo), ldb, 1.0, result.data, columns)
    return result
