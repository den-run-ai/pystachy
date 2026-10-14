# Calling C and building Python extensions

Pystachy's experimental FFI can call C libraries in JIT and AOT programs, or build AOT
extension modules that CPython imports. The tested platform is x86-64 Linux with glibc.

| Direction | Interface | Status |
|---|---|---|
| Pystachy → C | Typed `@ffi.extern` declarations | Implemented in JIT and AOT. |
| CPython → Pystachy | `@ffi.export` and `pystachy ext` | Implemented in AOT. |
| Pystachy → CPython | Proposed `pyobj` wrapper and embedding | Open [PR #170](https://github.com/den-run-ai/pystachy/pull/170); not available on `main`. |

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
integers, `float` for `double`, and `c_void_p` for pointers. A `str` argument is a
temporary UTF-8 C string. Structs, varargs and callbacks require a C shim with
scalar arguments. The [ABI reference](reference/ffi.md#c-types-and-conversions)
defines ranges, null handling, buffers and ownership.

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

The CPython twin in `tools/rt_cpython/ffi.py` supplies ctypes-backed `extern` and
checked `export` decorators, so the same source can serve as a comparison:

```sh
PYTHONPATH=tools/rt_cpython python3 example.py
make test-ffi
```

The [reference](reference/ffi.md) collects exact conversions, pointer lifetimes,
CPython deviations, platform limits and maintainer checks. FFI declarations must
match the real C prototypes; C code must not retain a temporary string pointer or
unwind across Pystachy frames.

<a id="next-pystachy-calls-cpython-libpyobjpy"></a>
## Python embedding proposal

[PR #170](https://github.com/den-run-ai/pystachy/pull/170) proposes a subset `pyobj`
module backed by CPython's stable ABI. It would let programs hold Python objects
and call libraries through an embedded interpreter. It is separate from the
extension support described above and is not a current library import.
