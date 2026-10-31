# Calling C and CPython, and building Python extensions

Pystachy's experimental FFI can call C libraries and CPython from JIT and AOT programs, or
build AOT extension modules that CPython imports. The tested platform is x86-64 Linux with
glibc.

| Direction | Interface | Status |
|---|---|---|
| Pystachy → C | Typed `@ffi.extern` declarations | Implemented in JIT and AOT. |
| CPython → Pystachy | `@ffi.export` and `pystachy ext` | Implemented in AOT. |
| Pystachy → CPython | `import pyobj`, with CPython embedded | Implemented in JIT and AOT; AOT is the reference. |

Start with the examples, then use the contracts below for exact behavior:

- [Call C](#calling-c), [C types](#c-types-and-conversions) and [pointer lifetimes](#pointer-lifetimes-and-foreign-control-flow).
- [Call CPython](#calling-cpython), including [ownership and shutdown](#references-memory-and-program-end).
- [Build an extension](#building-a-cpython-extension) and check its [threading contract](#threading-and-host-lifetime).
- [Compare behavior](#checking-behavior-and-compatibility), [deviations](#deviations-from-cpython-and-the-twin) and [platform limits](#platform-and-api-limits).

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

`ffi.at(xs, k)` passes a list from its index `k`: C gets a pointer to item `k` of the list's
own items, and may use the `len(xs) - k` items from there. It is only an argument of an
`@extern` call, for a list parameter. `k` is checked as the call starts, once the other
arguments are evaluated: outside `0 <= k <= len(xs)` it raises `IndexError`.

```python
from ffi import at

zs = [1.0, 2.0, 3.0, 4.0]
cblas_daxpy(2, 1.0, zs, 1, at(zs, 2), 1)  # zs is now [1.0, 2.0, 4.0, 6.0]
```

In a program where a module opts in to [promoting ints](python-int.md), a list of ints that
holds an int past 64 bits raises `OverflowError` before C gets its items, directly or through
`ffi.at()` (`tests/ffi/c_python_int.py`).

## Declaring and resolving C functions

`extern(lib, symbol="")` takes string literals, by position or keyword. An omitted
or empty symbol uses the function's name. When the `def` runs, `pys_c_bind` uses
`dlopen(lib, RTLD_NOW | RTLD_LOCAL)` and resolves the symbol in that handle with
`dlsym`. `@extern("")` uses the process's libraries, as `ctypes.CDLL(None)` does.
A missing library raises `OSError`; a missing symbol raises `AttributeError`, with
`dlerror()` text. Library names and paths are passed through without translation.

Calls bind positional and keyword arguments and declared defaults using the
function's normal signature. The compiler rejects:

- Bare `int`, `bool`, classes, containers other than `list[float]` and
  `list[ffi.c_int64]` arguments, and optionals other than a `str | None` return; every C
  integer must specify its width, a list's items too (`list[ffi.c_int64]`, not `list[int]`).
- Unannotated parameters, `*args`, a body other than `...`, or `@extern` on a method.
- Nonliteral library/symbol names, embedded NULs and invalid decorator arguments.
- Conflicting declarations of one C symbol, including conflicts with the runtime's
  declarations such as `memchr` or `fabs`.
- Reserved symbols: `pys_*`, `pyx_*`, `PyInit_*`, `PyModExport_*` and `main`.

Structs by value, varargs and callbacks require a C shim with scalar arguments.
The compiler does not read C headers or infer C calling conventions.

## C types and conversions

| Annotation | C type | Checks and conversion |
|---|---|---|
| `ffi.c_int` | 32-bit signed `int` | `OverflowError` outside `[-2**31, 2**31)`; sign-extended. |
| `ffi.c_uint` | 32-bit `unsigned int` | `OverflowError` outside `[0, 2**32)`; zero-extended. |
| `ffi.c_int64`, `ffi.c_ssize_t` | `int64_t`, `ssize_t` | Signed 64-bit values. |
| `ffi.c_uint64`, `ffi.c_size_t` | `uint64_t`, `size_t` | An argument must be nonnegative; a result must be below `2**63`. |
| `ffi.c_void_p` | Pointer carried as `int` | `0` is NULL. |
| `float` | `double` | Preserves signed zero, infinities and NaN. |
| `ffi.c_float` | 32-bit `float` | An argument is rounded to the nearest float, ties to even, and past the largest float to an infinity, as ctypes rounds it; a result widens to a `float` exactly. Declare C `float` parameters with it: passed as `float`, a C `float` parameter would read the wrong register bits. |
| `str` argument | `const char *` | NUL-terminated UTF-8 bytes, valid during the call; NUL in the value raises `ValueError`. |
| `ffi.c_buf` argument | `const char *` | Same bytes, NULs allowed; pass the length separately. |
| `list[float]` argument | `double *` | The list's own items, for the call: C reads and writes them in place. Pass the length separately. |
| `list[ffi.c_int64]` argument | `int64_t *` | The same, for a list of ints (`list[ffi.c_ssize_t]` too). Other item types, `list[ffi.c_float]` and `list[ffi.c_int]` among them, are rejected: a list's items are 8 bytes each. |
| `ffi.at(xs, k)` argument | `double *`, `int64_t *` | Item `k` of the list's own items, for a list parameter: C may read and write the `len(xs) - k` items from there. `k` is checked as the call starts, after the other arguments: `IndexError` outside `0 <= k <= len(xs)`. Elsewhere `ffi.at()` is a compile error. |
| `str` result | `char *` | Copied into a new string; NULL raises `ValueError`. |
| `str \| None` result | `char *` | Copied into a new string; NULL becomes `None`. |
| `None` result | `void` | No value. |

C integer annotations are ordinary `int` inside a stub's subset signature.
`ffi.string_at(addr, n)` copies `n` bytes into a string; negative `n` raises
`ValueError` rather than reading to a NUL as ctypes would.

## Pointer lifetimes and foreign control flow

A C function must not retain a `str`, `c_buf` or list pointer after returning. Returned
strings are copied; that copy does not free the source allocation. If C allocated
it, declare a pointer result, copy it with `string_at` and call the library's
matching deallocator. Pointer addresses and lengths must designate valid memory.

A list argument lends C its item array for the call. The collector moves nothing, and no
subset code runs until the call returns, so the list cannot grow or lose its array
meanwhile. C may read and write `len(xs)` items (`len(xs) - k` from `ffi.at(xs, k)`), and
what it writes is in the list when the call returns; pass a copy (`xs[:]`) to keep the
original.

The CPython twin copies each distinct list into one C array before the call and back into the
list after it, so a list passed for two parameters is one array there as it is natively:
`f(xs, xs)` sees its own writes in both runtimes, and so does `f(xs, ffi.at(xs, 2))`, which
passes a pointer to that array's item 2.

A declaration must match the real C prototype. A mismatch in widths or calling
convention, C++ exception or `longjmp` across subset frames, or retained temporary
string pointer causes undefined behavior, as with ctypes. Foreign calls are
conservatively treated as having all effects; inside `try`, a call is an `invoke`.

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

`lib/pyobj.py` is subset code over CPython's stable ABI. It declares the CPython
functions it uses with `@extern("python")`, which only a module of Pystachy's `lib/`
that imports `ffi` may do; such a module's C functions are called directly rather
than looked up when their `def` runs. `python` means `$PYSTACHY_LIBPYTHON`, a shared
libpython of CPython 3.12 or later: `pystachy run` has `lli` load it with the
machine code of `pyembed.c`, and `pystachy build` links both, the library with an
rpath. The driver rejects an unset variable or, by its file name, an older
library. `pystachy ext` links no libpython: an extension module's `pyobj` uses the
host interpreter.

### The API

A program may use what the twin's `__all__` names. Importing another name of
`pyobj`, calling `Object(...)`, using an `Object`'s fields, or reflecting on one
(`dir()`, `vars()`, `hasattr()`, `getattr()` with a default) is a compile-time
error: the twin's `Object` is another class.

| Call | CPython operation |
|---|---|
| `import_module(name)` | `importlib.import_module(name)` |
| `of_int(v)`, `of_float(x)`, `of_str(s)` | A new int, float or str (UTF-8, `surrogatepass`). |
| `of_list(objects)` | A new list of those objects: an explicit copy of the list. |
| `o.attr(name)`, `o.call(args)`, `o[k]` | `getattr(o, name)`, a positional call, `o[k]`. |
| `len(o)`, `bool(o)`, `str(o)`, `repr(o)` | The same operations. |
| `o.to_int()`, `o.to_float()` | `PyLong_AsLongLong` (`__index__`, signed 64-bit) and `PyFloat_AsDouble` (no str). |
| `o.close()` | Releases the reference; a closed `Object` raises `ValueError`. |

No container converts implicitly; Pystachy code reaches Python's containers as
`Object`s ([#108](https://github.com/den-run-ai/pystachy/issues/108)).

### Startup, output and exceptions

CPython starts when `pyobj` is first imported, set up as `python3 script.py` sets
it up. In the C or POSIX locale, LC_CTYPE is coerced to C.UTF-8 (PEP 538) and
UTF-8 mode is on (PEP 540), as `PYTHONCOERCECLOCALE` and `PYTHONUTF8` say.
`sys.executable` is the interpreter of the libpython loaded, `sys.argv` is the
program's (decoded with `surrogateescape`), and the program's directory comes first
on `sys.path`. CPython installs no signal handlers. The program holds the GIL only
inside `pyobj` operations, so Python threads run while compiled code runs.

Pystachy's and Python's output reach stdout and stderr in the order they were
printed. Before an operation runs Python code, Pystachy's pending output is written;
before Pystachy writes after one, Python's stream is flushed; `call()` flushes
Python's `sys.stdout` first, as the twin does. While Python code has replaced
`sys.stdout` or `sys.stderr` (`contextlib.redirect_stdout`, `None`), Pystachy's
writes go through the replacement. Pystachy's `input()` is Python's, and
`sys.stdin.readline()` and `read()` read Python's `sys.stdin`, so neither reads
ahead of the other.

A Python exception becomes the first class in its type's `__mro__` that Pystachy
has (`json.JSONDecodeError` arrives as `ValueError`), with the same `str()`; if
`str()` raises, the exception it raised does. `SystemExit` keeps its `str()`, its
`repr()` and the exit status its code gives CPython (an int beyond 64 bits gives
-1, an int subclass its value). `KeyboardInterrupt` stays itself.

### References, memory and program end

An `Object` owns one reference, and each operation owns the references it passes to
CPython while it runs. A dropped `Object` releases its reference once a collection
finds it unreachable: at the next `pyobj` operation, at any depth, when an extension
module's outermost call returns, or at exit, never inside the collector, because
releasing runs Python code. The collector counts each reference as 512 bytes plus
the object's `sys.getsizeof()`, so dropping large Python objects starts collections
as allocating would.

When the program ends, normally, by an uncaught exception or by `sys.exit`, CPython
is finalized after the program's output and `atexit` callbacks: Python's
non-daemon threads are joined and its `atexit` handlers run. A failed flush of
Python's `sys.stdout` then exits with status 120, as CPython does. A Ctrl-C that
reaches a thread CPython started is passed to the main thread.

A program whose own `ffi.py` replaces the builtin module cannot import `pyobj`; the
compiler names that module.

<a id="extension-modules"></a>
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

`pystachy ext NAME.py` builds `NAME.abi3.so`, for CPython 3.12+ GIL builds.
`--abi abi3t` builds `NAME.abi3t.so`, for CPython 3.15+ GIL and free-threaded
builds, but still requires the GIL. Both use the same program IR.

`pyext.c` and `pyembed.c` use manually declared stable-ABI functions without
`Python.h`. Their bitcode is cached with the runtime. The program, glue and runtime
are linked into one shared object, exposing only `PyInit_<name>` for `abi3` or
`PyModExport_<name>` for `abi3t`.

### Exports and module initialization

- Public functions must be `@export`, take positional `int`, `float`, `bool` or
  `str` and return one of those or `None`. Defaults and `*args` are unsupported.
- A public class or variable is rejected; prefix private helpers with `_`.
  Subset code cannot call an `@export` function directly, because the CPython twin
  applies boundary checks on each call. Both callers can use a private helper.
- Module code runs at import with the module's `__name__`, and with the host's `sys.argv`
  and `sys.warnoptions`, copied at import.
  An `if __name__ == "__main__":` block does not run.
- `print` uses the host's `sys.stdout`, including redirection and replacement;
  `input` and `sys.stdin` use the host's input. Failed writes raise in subset code.
- Exceptions are caught at the boundary. They leave as the builtin class matching
  their name, or the nearest builtin base of a custom class, with `args` rebuilt
  from their repr. No subset exception unwinds through CPython frames.
- Exported functions have the module as `__self__` and pickle by name, supporting
  `multiprocessing`.
- A failed import can be retried. A second load after a successful import is
  refused, including removal from `sys.modules` followed by re-import.
- At interpreter exit, an `atexit` handler releases the references the module's
  `pyobj` Objects hold and closes module files before module teardown. Calls after
  that handler has run are refused.

### Threading and host lifetime

Only the importing thread may call the module; another thread gets `RuntimeError`.
CPython subinterpreters are unsupported for both extension ABIs.
The runtime is single-threaded and has no TLS. Computation holds the GIL, so long
calls delay other Python threads and Ctrl-C. Host I/O calls can release the GIL;
thread-ID and entry-depth checks still protect the runtime. Process pools whose
workers each import the module run it in parallel; the
[concurrency contract](concurrency.md) states what they guarantee.

A callback into the module while its I/O hooks call the host's `sys.stdout`,
`sys.stderr` or `sys.stdin` raises `RuntimeError`. Stack-switching libraries such
as greenlet or gevent are unsupported while compiled extension frames are live:
the collector scans one contiguous stack from the outermost entry, and does not
detect a switched stack.

An `abi3t` module turns the GIL on for CPython 3.15t with CPython's warning
(`Py_mod_gil` is used); import under `PYTHON_GIL=0` raises `ImportError`.
An `abi3` module refuses import on CPython 3.13t and 3.14t. CPython 3.11 is below
the `abi3` floor and fails to load `PyErr_GetRaisedException`; package it with a
`cp312-abi3` wheel tag.

Two Pystachy extension modules carry independent runtimes and heaps. Values cross
between them through Python as copies. Allocation failure inside a collection or
stack exhaustion ends the host process.

<a id="why-this-design"></a>
<a id="tests"></a>
## Checking behavior and compatibility

The CPython twins in `tools/rt_cpython` supply ctypes-backed `extern` and checked
`export` decorators (`ffi.py`) and the `pyobj` API over CPython's own objects
(`pyobj.py`), so the same source can serve as a comparison:

```sh
PYTHONPATH=tools/rt_cpython python3 example.py
make test-ffi
```

Their checks and error messages are the comparison contract for native code;
`tests/ffi/run.sh` compares both implementations. A program's own `ffi.py` or
`ffi/` package takes precedence over the builtin module, as under CPython.

<a id="deviations"></a>
## Deviations from CPython and the twin

| Area | Behavior |
|---|---|
| Strings | UTF-8 storage inside Pystachy; lengths, indexing, slicing, iteration and search positions count code points. Invalid UTF-8 returned from C is kept as bytes in a string; the twin's decode raises `UnicodeDecodeError`. |
| Process symbol lookup | `@extern("")` sees different libraries in CPython, `lli` and an AOT executable. Name a library explicitly. |
| Library interposition | `lli`'s libraries can affect global bindings. JIT opens the named library with `RTLD_DEEPBIND` to bind its internal calls like AOT; CPython's process may still bind differently. |
| C output | Foreign stdio and subset `print` interleave according to their separate buffers and flushes. |
| Float text | Conversions use the C locale even if foreign code changes `setlocale`; format type `n` also uses the C locale. |
| Extension integers | Arguments or results outside signed 64-bit raise `OverflowError`, as the export twin does. Internal arithmetic remains checked. |
| Extension import exceptions | Custom exception classes leave as their nearest builtin base, rather than the source module's own class. |
| Re-import | A second successful module load raises `ImportError`; source code can be run again by CPython. |
| `sys.stdout = None` | Both `print` and `sys.stdout.write` do nothing in the extension; CPython's explicit `write` raises `AttributeError`. |
| Late calls | Calls after the module's shutdown handler raise `RuntimeError`, including from earlier-registered host `atexit` handlers. |
| `pyobj` exceptions | A Python exception arrives as the nearest builtin class Pystachy has, as the twin raises it; custom Python exception classes do not cross. |
| Release timing | A dropped `Object` releases its reference after a collection, not when CPython's count reaches zero: `__del__` methods and weakref callbacks run later, and a Python file written through a dropped `Object` gets its data then. Call `close()`. `sys.getsizeof()` is shallow, so a dropped container counts only its own size. |
| Output timing | The text keeps its order, but each runtime buffers its own output: a write that bypasses `sys.stdout` (`os.write`, a child process, C stdio) may meet it sooner or later than under CPython's single buffer. |
| Caller frames | Python functions that read their caller's frame (`exec()` and `eval()` without globals, `globals()`, `locals()`, `vars()` and `dir()` without arguments, `sys._getframe()`) find no Python caller under `pyobj` and raise; the twin's calls come from its own frames. Pass `exec` and `eval` a globals dict. |
| Embedded `sys.path[0]` | The script's directory under `pystachy run`, the executable's directory for an AOT build. |
| JIT embedding | Under `pystachy run`, CPython loads extension modules with `RTLD_DEEPBIND` added to `sys.getdlopenflags()`, so that their libraries come before `lli`'s. AOT is the reference tier. |
| Hosted compiler | `python3 -m pystachy run` passes on the `LC_CTYPE=C.UTF-8` that its own CPython's PEP 538 coercion set ([#51](https://github.com/den-run-ai/pystachy/issues/51)); the native compiler passes the environment on unchanged. |
| Exit order | The program's `atexit` callbacks run before CPython is finalized, so before Python's threads are joined and its own `atexit` handlers run; the twin keeps one registry for both. |
| Ctrl-C while embedding | The program ends as on any Ctrl-C, without finalizing CPython: no Python `atexit` handlers, thread joins or buffered Python output. |
| Stdin before `pyobj` | Input that C stdio read ahead before `pyobj` was imported is not Python's to read. |
| Thread scheduling | Python threads run while compiled code runs; output whose order depends on scheduling is not defined by the twin. |

For general language differences, see [compatibility](language/compatibility.md).

<a id="limitations"></a>
## Platform and API limits

The tested platform is x86-64 Linux with LP64, glibc and Itanium exception
unwinding. macOS would need `-undefined dynamic_lookup` for extensions and lacks
`RTLD_DEEPBIND`; Windows requires another loader and unwinding implementation.

Keyword arguments/defaults for exports, public classes, exception classes,
containers, C callbacks and calls from arbitrary threads are unsupported. Mutable
containers are not copied implicitly because that would lose identity and shared
mutation; see [#108](https://github.com/den-run-ai/pystachy/issues/108). A
`list[float]` or `list[ffi.c_int64]` argument of `@extern` is lent, not copied, for
the call.
Embedding needs a shared libpython of CPython 3.12 or later. `pyobj` calls take
positional arguments only; passing compiled callables through `pyobj` and raw C
callbacks are unsupported. CPython can call exported functions through the
[extension interface](#extension-modules), subject to its host-entry restrictions.

<a id="invariants-for-maintainers"></a>
## Maintainer checks

- Keep twins and native checks/messages in agreement. `make test-ffi` covers C
  declarations in JIT/AOT, compile-time rejections, embedded CPython in JIT/AOT
  and extension behavior under GC stress, using the configured CPython for live
  twin comparisons. Embedding and extension checks require CPython 3.12+ with
  shared `libpython`; the runner reports skipped cases when the configured
  interpreter cannot load extensions.
- Keep glue opt-in: `pyext.c` is linked only for `ext`, `pyembed.c` for `ext` and
  for programs that import `pyobj`, which alone link libpython, and `-ldl` only for
  those and programs that resolve foreign functions. Programs that use none of
  them retain their IR byte for byte (`make irsame`).
- Keep `pyobj`'s API the twin's. A module of `lib/` that imports `ffi` offers only
  its `__all__`, with no fields, constructor or reflection (`Loader.take`,
  `Loader.qmod`, `Gen.glue_field`, `refl_supported`); only it may use `ffi.track`,
  `untrack`, `collected` and `@extern("python")`.
- Every `pyobj` operation owns the references it passes to CPython (`_own`), so
  releasing dropped Objects (`_enter`) is safe at any depth, including Python code
  that calls back into an extension module.
- Keep builds independent of Python headers. The driver does not need to launch
  CPython to build an extension; live compatibility checks still need CPython.
- `tools/abi_check.sh TOML SO MAXVER ENTRY` checks that only the entry is defined
  publicly and every imported Python symbol belongs to the target stable ABI.
- `make test` checks that a program's own `ffi` module takes precedence.

A future lock supporting arbitrary host threads must preserve runtime state over
all call-outs, including I/O. `PyCriticalSection` may suspend whenever its thread
detaches and cannot alone provide that contract.
