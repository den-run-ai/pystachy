"""check_upstream: tests/example_ndarray_upstream.py, NumPy's own tests adapted to ndarray, run by
CPython against NumPy itself.

usage: python3 check_upstream.py

The adapted test calls ndarray's API; here that API is a thin layer over NumPy arrays (an NDArray
wraps a float64 view of a flat buffer, with ndarray's data, strides and offset in items), and this
module stands in for ndarray while the test runs. Every assertion must hold for NumPy too: that
checks the adaptations (the views built from strides for x[::-1] and x[1::3], order='F', the
written-out random inputs, the expected values) against NumPy's own behavior. It prints what the
test prints, which tests/example_ndarray_upstream.out records for ndarray.
"""
import os
import sys
import warnings

import numpy as np


class NDArray:
    def __init__(self, data, shape, strides, offset):
        self.base = data if isinstance(data, np.ndarray) else np.array(data, dtype=np.float64)
        self.arr = np.ndarray(tuple(shape), np.float64, buffer=self.base, offset=offset * 8, strides=tuple(s * 8 for s in strides))

    @staticmethod
    def wrap(r, like=None):
        # r as an NDArray: a view of like's buffer, or a C-ordered array of its own
        r = np.asarray(r, dtype=np.float64)
        if like is not None and np.shares_memory(r, like.base):
            o = NDArray.__new__(NDArray)
            o.base = like.base
            o.arr = r
            return o
        r = r if r.flags.c_contiguous else r.copy(order="C")
        return NDArray(r.reshape(-1) if r.ndim else r.reshape(1), list(r.shape), [s // 8 for s in r.strides], 0)

    data = property(lambda self: self.base)
    shape = property(lambda self: list(self.arr.shape))
    strides = property(lambda self: [s // 8 for s in self.arr.strides])
    offset = property(lambda self: (self.arr.__array_interface__["data"][0] - self.base.__array_interface__["data"][0]) // 8)
    ndim = property(lambda self: self.arr.ndim)
    size = property(lambda self: self.arr.size)
    T = property(lambda self: NDArray.wrap(self.arr.T, self))

    def contiguous(self):
        return self.arr.flags.c_contiguous

    def copy(self):
        return NDArray.wrap(self.arr.copy())

    def reshape(self, shape):
        return NDArray.wrap(self.arr.reshape(shape), self)

    def row(self, i):
        return NDArray.wrap(self.arr[i], self)

    def __getitem__(self, key):
        return float(self.arr[key])

    def __setitem__(self, key, v):
        self.arr[key] = v

    def __len__(self):
        return len(self.arr)

    def __add__(self, o):
        return NDArray.wrap(self.arr + (o.arr if isinstance(o, NDArray) else o))

    def __sub__(self, o):
        return NDArray.wrap(self.arr - (o.arr if isinstance(o, NDArray) else o))

    def __mul__(self, o):
        return NDArray.wrap(self.arr * (o.arr if isinstance(o, NDArray) else o))

    def __truediv__(self, o):
        with np.errstate(all="ignore"):
            return NDArray.wrap(self.arr / (o.arr if isinstance(o, NDArray) else o))

    def __iadd__(self, o):
        np.add(self.arr, o.arr if isinstance(o, NDArray) else o, out=self.arr)
        return self

    def __matmul__(self, o):
        return NDArray.wrap(np.matmul(self.arr, o.arr))

    def values(self):
        return [float(x) for x in self.arr.ravel()]


def arange(n):
    return NDArray.wrap(np.arange(max(n, 0), dtype=np.float64))


def array(xs):
    return NDArray.wrap(np.array(xs, dtype=np.float64))


def array2(rows):
    return NDArray.wrap(np.array(rows, dtype=np.float64))


def zeros(shape):
    return NDArray.wrap(np.zeros(tuple(shape)))


def total(a):
    return float(np.sum(a.arr))


def mean(a):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return float(np.mean(a.arr))


def matmul(a, b):
    return NDArray.wrap(np.matmul(a.arr, b.arr))


sys.modules["ndarray"] = sys.modules[__name__]  # (the test's `from ndarray import ...` finds these)
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tests", "example_ndarray_upstream.py")
with open(path) as f:
    exec(compile(f.read(), path, "exec"), {"__name__": "example_ndarray_upstream"})
print(f"(numpy {np.__version__}: the adapted assertions hold for NumPy itself)")
