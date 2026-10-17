# ndarray: a float64 array in typed Python

A small NumPy-style array written in the typed subset, to measure how far Pystachy gets with array
code. [`ndarray.py`](ndarray.py) has views (transposes, rows and reshapes share their data),
NumPy's broadcasting, arithmetic with arrays and numbers into a new array or an existing one
(`out=`, `+=`), reductions and a matrix product. [`lazy.py`](lazy.py) builds elementwise
expressions over whole arrays whose evaluation compiles to one loop, without temporary arrays.
Both are plain Python: CPython runs them too, which lets [`check_numpy.py`](check_numpy.py)
compare them with NumPy.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 demo.py
pystachy run demo.py
pystachy build demo.py -o demo
./demo
```

```
a + b        array([11.0, 22.0, 33.0, 14.0, 25.0, 36.0], shape=(2,3))
a.T          array([1.0, 4.0, 2.0, 5.0, 3.0, 6.0], shape=(3,2))
a * 2 - 1    array([1.0, 3.0, 5.0, 7.0, 9.0, 11.0], shape=(2,3))
a @ a.T      array([14.0, 32.0, 32.0, 77.0], shape=(2,2))
a[1, 2]      6.0 a.row(1): array([4.0, 5.0, 6.0], shape=(3,))
sum axis 0   array([5.0, 7.0, 9.0], shape=(3,)) axis 1: array([6.0, 15.0], shape=(2,))
total, mean  21.0 3.5
a > 2.5      [False, False, True, True, True, True]
1 / [1 -1 0] array([inf, -inf, nan], shape=(3,))
t[0, 1] = 40 writes a[1, 0]: 40.0
ValueError: 'operands could not be broadcast together with shapes (2,3) (2,) '
c = a.copy(); c += b, in place: array([11.0, 22.0, 33.0, 50.0, 25.0, 36.0], shape=(2,3))
x * y + 1 fused == eager: True
sum((x - y) * (x - y)): lazy 42453252.551020406 total 42453252.551020406
sum of 1e16, 100 ones, -1e16: total (pairwise) 84.0 lazy (compensated) 100.0
```

CPython, the JIT and the executable print the same. `repr()` lists the items in C order and the
shape; it is not NumPy's format.

## Optional native BLAS matrix multiplication

[`ndarray_blas.py`](ndarray_blas.py) adds a separate, opt-in matrix product:

```python
from ndarray import array2
from ndarray_blas import matmul

x = array2([[1.0, 2.0], [3.0, 4.0]])
weight = array2([[5.0, 6.0], [7.0, 8.0], [9.0, 10.0]])
y = matmul(x, weight.T)
```

The compiled program calls `libblas.so.3`'s `cblas_dgemm` directly using the
[borrowed numeric-list FFI](../../docs/ffi.md). Execution needs the shared BLAS
library and does not need CPython or NumPy. Importing ordinary `ndarray` and
using its `matmul()` or `@` still uses the existing scalar implementation and
does not load BLAS. The optional module raises a library/symbol loading error
if its explicitly selected BLAS is unavailable; it does not silently switch
backends.

The binding requires the **LP64 CBLAS ABI**: dimensions and leading dimensions
are 32-bit C `int`, and elements are 64-bit `double`. Each dimension is checked
against `INT_MAX` before calling C. This is not an ILP64 binding; loading a
symbol successfully, or multiplying small matrices, cannot establish its
integer ABI. Use a provider documented to supply LP64 `libblas.so.3`. For the
validation host, that name resolves to the reference BLAS
`blas/libblas.so.3.12.0`, package `libblas3` version `3.12.0-3build1.1`; its
exported `cblas_dgemm` uses 32-bit dimensions. An optimized provider such as
OpenBLAS is a separate deployment choice, not a property of this adapter.

The adapter checks shapes, strides, addressable byte extents and all referenced
storage before passing pointers to C. It always creates fresh output, so the
operands may share storage without output aliasing. Empty dimensions return
correctly shaped zeros without calling BLAS. Zero-offset row-major arrays and
their transposes, including padded rows, borrow their existing data. Thus
`matmul(x, weight.T)` needs no transposed-weight copy. Other views, including
nonzero offsets, reversed axes and broadcast strides, are packed in logical
row-major order; that copying is part of a call's cost. Inputs are read afresh
on every call, so weight updates need no cache invalidation.

Validation is optional because the normal test suite does not require a BLAS
installation. From this directory:

```sh
pystachy run blas_cases.py
pystachy build blas_cases.py -o blas_cases
PYSTACHY_GC_STRESS=1 ./blas_cases
python3 check_blas.py --compiler ../../pystachy --stress 1
```

The last command requires NumPy in the checking interpreter. It verifies all
elements of 24 matrix cases against both the existing scalar product and
NumPy, plus 15 invalid-input rejections, under CPython, JIT, AOT and native GC
stress. Cases include padded transposes, negative and zero strides, nonzero
offsets, singleton strides, shared operands, repeated calls after mutation,
empty products and integer-limit guards. The CPython FFI twin copies lists
into C arrays; it is a correctness oracle and is not a measure of the native
borrowed-buffer overhead. No speedup is claimed by these checks. BLAS may use
a different accumulation order, so finite results use `1e-12` tolerances.

## Numerical behavior

Elementwise arithmetic is one IEEE operation per item, so it gives NumPy's float64 results,
signed zeros, infinities and NaNs included. Division by zero gives NumPy's `inf` and `nan`, not
Python's `ZeroDivisionError`. A sum, though, depends on the order of its additions, so each
operation here fixes its order:

| Operation | How it adds | Against NumPy, in `check_numpy.py` |
|---|---|---|
| `total()`, `mean()` | Pairwise, as NumPy's `pairwise_sum`: eight accumulators over blocks of up to 128 items. Memory order for C- and F-ordered arrays, C order for other views | Equal for C- and F-ordered arrays; other views within 1e-12 on random data |
| `sum_axis()` | Pairwise along the fastest axis (absolute strides, ignoring singleton axes); otherwise the lines across it one after another, into one result, as NumPy adds them | Equal |
| `lazy`'s `sum()` | Python's `sum()` of floats: in order, with Neumaier's compensation | Equal to `sum()` of the items; within 1e-12 of `np.sum` on random data |
| `dot()` | `total(a * b)` | Equal to `np.sum(a * b)`; within 1e-12 of `np.dot`, which calls BLAS |
| `matmul()`, `@` | Row by row | Within 1e-12 of BLAS |

An ill-conditioned sum shows how much the order matters. `[1e16] + [1.0] * 100 + [-1e16]` sums to:
- 84.0 pairwise (`total()`, `np.sum`);
- 100.0 compensated (`lazy`'s `sum()`, Python's `sum()`, `math.fsum`);
- 0.0 added in plain order.

The error bound of pairwise summation grows with log *n*, that of plain order with *n*.
Compensation keeps it near one rounding of the result for all but extremely ill-conditioned sums.

```sh
python3 check_numpy.py
```

```
124 checks equal NumPy's results, 6 agree within 1e-12, 4 check the summation policy, 7 check the checker (numpy 2.3.5)
```

These counts are results on the inputs the script generates, not a promise for every input.
- Additional regression checks cover reversed and strided axis sums and empty reshapes with unrepresentable byte extents; these pass against NumPy 2.3.5 too.
- **Self-checks first:** the script confirms that its comparisons reject a NaN against a number, lists of different lengths, and an infinity against a large number.
- **Error messages:** broadcasting, `out=` shapes, `reshape`, indexing and `matmul` errors are checked against NumPy's messages.
- **Compiled tests:** `tests/example_ndarray.py` carries representative NumPy results into the tests that run under the JIT and as an executable.

NumPy's own test suite is the second source of expected results. `tests/example_ndarray_upstream.py` adapts the cases of NumPy 2.5.3's tests that this array can express: 432 assertions on broadcasting, reshape, transpose and ravel, 0-d subscripts, creation limits, means, 2-D matrix products, sums of strided and reversed views, division and indexing errors. Its header names each upstream test, the source file's SHA-256, the adaptations and what it leaves out (other dtypes, `order='F'` results, fancy indexing, stacked `matmul`, warnings). It runs compiled like the other tests, and

```sh
python3 check_upstream.py
```

runs the same file against NumPy itself, through a thin layer that gives NumPy arrays this API, to check that the adaptations keep NumPy's assertions. Porting it found one difference, now fixed: `zeros()` of a shape too big to address raised `OverflowError`, where NumPy raises `ValueError: array is too big`.

## Recorded benchmark

```sh
python3 -I bench.py pystachy
```

The run:
- **Machine:** a single run on a shared 4-vCPU x86-64 VM (Xeon, 2.8 GHz).
- **Versions:** compiler at [`2379159`](https://github.com/den-run-ai/pystachy/commit/2379159), LLVM 18.1.3, CPython 3.13.16, NumPy 2.5.3.
- **Threads:** NumPy single-threaded (`OPENBLAS_NUM_THREADS=1`), as Pystachy is.
- **Timing:** best of five inside each process, in milliseconds, so the JIT's numbers exclude its compilation.
- **Data:** `a` and `b` have 4,000,000 items.
- **Rows:** "into `out`" writes into an array made once; "loop" is the reduction written by hand as one loop.

| Workload | AOT | JIT | NumPy |
|---|---:|---:|---:|
| `a + b` | 34.2 | 39.8 | 8.8 |
| `a + b`, into `out` | 10.5 | 17.7 | 10.0 |
| `a * 1.5` | 25.3 | 27.6 | 5.8 |
| `a * b + a` | 53.7 | 63.4 | 23.9 |
| `a * b + a`, into `out` | 20.8 | 34.9 | 15.7 |
| `a * b + a`, lazy | 31.2 | 38.1 | — |
| `a * b + a`, lazy into `out` | 13.4 | 23.3 | — |
| `sum(a)` | 5.0 | 8.1 | 3.6 |
| `sum((a - b) * (a - b))` | 80.9 | 117.9 | 40.0 |
| `sum((a - b) * (a - b))`, lazy | 9.7 | 31.6 | — |
| `sum((a - b) * (a - b))`, loop | 7.4 | 6.8 | — |
| `m + row`, 1000×1000 | 7.6 | 10.2 | 0.8 |
| `m.T + m`, 1000×1000 | 9.5 | 13.8 | 1.5 |
| `sum(m, axis=0)`, 1000×1000 | 1.3 | 3.8 | 0.3 |
| `p @ q`, 256×256 | 15.1 | 59.1 | 0.6 |

- **New arrays are most of the cost.** Writing into an array made once brings `a + b` from 34.2 ms
  to 10.5, about NumPy's 10.0 into `out`. NumPy's 8.8 for a new array reuses freed memory, while a
  new numeric list here takes fresh memory that the collector then scans
  ([#210](https://github.com/den-run-ai/pystachy/issues/210)).
- **Fusion removes temporaries.** The lazy sum of `(a - b) * (a - b)`, compensated, takes 9.7 ms
  against NumPy's 40.0 for the eager expression; a hand-written loop, uncompensated, takes 7.4.
  The lazy `a * b + a` into `out` takes 13.4, NumPy's two passes into `out` 15.7.
- **Strided loops are slower.** Broadcast and strided loops, and the axis sum, take 5 to 9 times
  NumPy's time: they index through strides with a bounds check per item.
- **The JIT inlines less** than the executable's whole-program `-O2`
  ([#209](https://github.com/den-run-ai/pystachy/issues/209)).
- **Matrix products need BLAS.** The compiled loop reaches about 2 GFLOP/s, NumPy's OpenBLAS 52.
- **One call per loop.** Each of `lazy`'s loops calls an expression's `at()` from one place: LLVM
  did not inline it from several, and the compensated sum ran at 6.2 ns per item with two calls
  against 2.4 with one.

## What the subset cannot express yet

| NumPy | Here | Why |
|---|---|---|
| `a[1:3]`, `a[:, j]` | `a.row(i)` | No slice objects ([#501](https://github.com/den-run-ai/pystachy/issues/501)) |
| `2.0 * a`, `1 - a` | `a * 2.0` | No reflected operators ([#113](https://github.com/den-run-ai/pystachy/issues/113)) |
| `a > x`, a boolean mask | `greater(a, x)`, a `list[bool]` | Comparison methods must return `bool` |
| `a[i]`, a row of a 2-D array | `a.row(i)` | `__getitem__` returns one type for each key type |
| `a[i] = v` of a 1-D array | — | `__setitem__` cannot be a template, so it takes only `tuple[int, int]` |
| `lazy(a) * b`, `b` an array | `lazy(a) * lazy(b)` | Compile time cannot decide `isinstance(b, NDArray)`: an object may be `None` |
| float32, int8 and other dtypes | float64 only | No narrower scalars or packed numeric buffers |

`lazy()` takes whole arrays only, so every operand is read when the expression is evaluated; a view
goes in as `lazy(v.copy())`. Native numeric buffers, optional BLAS and NumPy interoperability are
tracked in [#582](https://github.com/den-run-ai/pystachy/issues/582).
