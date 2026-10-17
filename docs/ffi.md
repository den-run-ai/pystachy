# Calling C and CPython, and building Python extensions

Pystachy's experimental FFI can call C libraries and CPython from JIT and AOT programs, or
build AOT extension modules that CPython imports. The tested platform is x86-64 Linux with
glibc.

| Direction | Interface | Status |
|---|---|---|
| Pystachy → C | Typed `@ffi.extern` declarations | Implemented in JIT and AOT. |
| CPython → Pystachy | `@ffi.export` and `pystachy ext` | Implemented in AOT. |
| Pystachy → CPython | `import pyobj`, with CPython embedded | Implemented in JIT and AOT; AOT is the reference. |

<a id="foreign-functions-c-and-cpython-in-both-directions"></a>
<a id="calling-c-ffiextern"></a>
## Calling C

Declare the C signature explicitly. The library and symbol names must be string
literals; an omitted symbol uses the Python function's name.

```python
from ffi import extern, c_size_t

@extern("libc.so.6")
def strlen(s: str) -> c_size_t: ...

print(strlen("hello"))
```

```sh
./pystachy run example.py
./pystachy build example.py -o example
./example
```

The symbol is resolved when its definition runs, using the named library's
handle. Use a library name or path for reproducibility; `@extern("")` searches
the process's own libraries, which differ between CPython, JIT and AOT.

Use `ffi.c_int`, `c_uint`, `c_int64`, `c_uint64`, `c_size_t` or `c_ssize_t` for C
integers, `float` for `double`, `ffi.c_float` for C's 32-bit `float`, and `c_void_p` for pointers. A `str` argument is a
temporary UTF-8 C string. A `list[float]` argument lends C the list's own items as a
`double *` for the call, and a `list[ffi.c_int64]` as an `int64_t *`; C reads and writes
them in place, and the length goes as another argument:

```python
from ffi import extern, c_int

# void cblas_daxpy(int n, double alpha, const double *x, int incx, double *y, int incy)
@extern("libopenblas.so.0")
def cblas_daxpy(n: c_int, alpha: float, x: list[float], incx: c_int, y: list[float], incy: c_int) -> None: ...

xs = [1.0, 2.0]
ys = [10.0, 20.0]
cblas_daxpy(len(xs), 2.0, xs, 1, ys, 1)   # ys is now [12.0, 24.0]
```

Structs, varargs and callbacks require a C shim with scalar arguments. The
[ABI reference](reference/ffi.md#c-types-and-conversions) defines ranges, null
handling, buffers and ownership.

<a id="next-pystachy-calls-cpython-libpyobjpy"></a>
<a id="calling-cpython-libpyobjpy"></a>
## Calling CPython

`lib/pyobj.py` gives a program Python objects through an embedded CPython, which
starts when `pyobj` is first imported. `PYSTACHY_LIBPYTHON` names its shared
`libpython` (CPython 3.12 or later, GIL or free-threaded).

```python
from pyobj import import_module, of_int, of_str, of_list

json = import_module("json")
s = json.attr("dumps").call([of_list([of_int(1), of_str("hello")])])
print("json:", s)
try:
    json.attr("loads").call([of_str("{bad")])
except ValueError as e:      # JSONDecodeError arrives as the nearest class Pystachy has
    print("caught:", e)
s.close()
```

```sh
export PYSTACHY_LIBPYTHON=/usr/lib/x86_64-linux-gnu/libpython3.13.so.1.0
./pystachy run jsondemo.py                    # JIT: lli loads that libpython
./pystachy build jsondemo.py && ./jsondemo    # AOT: linked to it, with an rpath
PYTHONPATH=tools/rt_cpython python3 jsondemo.py   # the twin under CPython
```

A program may use `Object` (`attr`, `call`, `[]`, `len`, truth, `to_int`,
`to_float`, `str`, `repr`, `close`), `import_module`, `of_int`, `of_float`,
`of_str` and `of_list`, as the twin offers. Nothing converts a container
implicitly; `of_list` copies explicitly. Python exceptions become the nearest
builtin class Pystachy has, with the same `str()`; `SystemExit` and
`KeyboardInterrupt` keep theirs. Pystachy's and Python's output share stdout and
stdin in order, and CPython is finalized when the program ends. Inside an
extension module, `pyobj` uses the host interpreter instead. The
[reference](reference/ffi.md#calling-cpython) covers references, memory, startup,
exit and deviations.

<a id="cpython-calls-pystachy-pystachy-ext"></a>
## Building a CPython extension

```python
# fastmath.py
from ffi import export

@export
def fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
```

```sh
./pystachy ext fastmath.py                 # fastmath.abi3.so: CPython 3.12+ GIL builds
python3 -c 'import fastmath; print(fastmath.fib(10))'
./pystachy ext fastmath.py --abi abi3t     # fastmath.abi3t.so: CPython 3.15+
```

Exports accept positional `int`, `float`, `bool` and `str` values and return one
of those or `None`. Integers are checked signed 64-bit values. Exported functions
have no defaults or `*args`; classes and containers do not cross the boundary.
Keep module helpers private with a leading underscore.

The runtime accepts calls only from the importing thread and requires the GIL,
including with `abi3t`. Re-import after a successful load and I/O re-entry are
restricted. Review the [extension contract](reference/ffi.md#extension-modules)
before using it in a threaded or embedded host.

<a id="why-this-design"></a>
<a id="deviations"></a>
<a id="limitations"></a>
<a id="invariants-for-maintainers"></a>
<a id="tests"></a>
## Checking behavior and compatibility

The CPython twins in `tools/rt_cpython` supply ctypes-backed `extern` and checked
`export` decorators (`ffi.py`) and the `pyobj` API over CPython's own objects
(`pyobj.py`), so the same source can serve as a comparison:

```sh
PYTHONPATH=tools/rt_cpython python3 example.py
make test-ffi
```

The [reference](reference/ffi.md) collects exact conversions, pointer lifetimes,
CPython deviations, platform limits and maintainer checks. FFI declarations must
match the real C prototypes; C code must not retain a temporary string pointer or
unwind across Pystachy frames.
