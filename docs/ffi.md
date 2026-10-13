# Foreign functions: C, and CPython in both directions

Status: **prototype**, proposed as the decision record that issue
[#4](https://github.com/den-run-ai/pystachy/issues/4) §4 asks for (see
[history.md](history.md#open)). Two of the three directions are built: calling C and
extension modules; the [next step](#next-pystachy-calls-cpython-libpyobjpy) is calling
CPython. Nothing here changes a program that does not use it: such a program compiles to the
same LLVM IR, byte for byte, as without this work (`make irsame`).

| direction | how | tiers |
|---|---|---|
| Pystachy calls C | `@ffi.extern("lib")` on a typed `...` stub, looked up in the library's own handle as ctypes does | JIT and AOT, from the same IR |
| Pystachy calls CPython (next) | `lib/pyobj.py`: CPython's stable ABI through `@ffi.extern`, CPython embedded | JIT and AOT (AOT the reference) |
| CPython calls Pystachy | `pystachy ext NAME.py`: an abi3 or abi3t extension module of `@ffi.export` functions | AOT only |

Each direction keeps Pystachy's contract: a program prints what CPython prints, or is rejected
at compile time with `file:line: error`. CPython's side is defined by *twins*: the
`tools/rt_cpython` directory holds a plain-Python `ffi.py` (ctypes for `extern`, a checking
wrapper for `export`), so every file that uses the FFI also runs under CPython, and that run is
the oracle:

    PYTHONPATH=$PYSTACHY_HOME/tools/rt_cpython python3 prog.py   # what prog.py must print

The twins are the specification: the native code makes the twins' checks with the twins'
messages, and a program may use only what the twins offer (anything else is a compile-time
error). What still differs is listed under [Deviations](#deviations).

## Why this design

- **Calls out work in both tiers, calls in only AOT.** A call from Pystachy to C goes through an
  address the program looks up itself, and lib/pyobj.py's calls to CPython bind to the libpython
  that lli loads or the linker links, so `pystachy run` and `pystachy build` run the same IR.
  CPython, though, imports only shared objects, and `pystachy run` is a separate lli process. A
  JIT inside CPython does work (LLVM's ORC through libLLVM's C API, or llvmlite), but it would
  load a 117–123 MB libLLVM, or llvmlite's LLVM 22 (about 170 MiB installed, for IR written for
  LLVM 18), into every process that imports a module, through an LLJIT C API whose header says it
  is not stable; an extension module imports in under a millisecond. A compile-on-import cache,
  still AOT underneath, can give a quick edit loop later.
- **Typed stubs, not C headers.** The compiler reads no header, which would take libclang, a second
  toolchain. LLVM IR does not lower C's calling conventions for aggregates, so what crosses is C
  integers of a stated width, `double`, pointers and strings; a struct, varargs or a callback goes
  through a small C shim. Codon, Julia's `@ccall` and LPython declare C functions the same way.
- **Looked up when the `def` runs, as ctypes does.** Nothing is linked: the library is opened with
  `dlopen` and the symbol found in its own handle, so `pystachy run`, an AOT build and CPython with
  the twin call the same function, and lli's own libraries cannot shadow it.
- **CPython's stable ABI, declared by hand.** Every C API operation the glue needs is an exported
  stable-ABI function (`Py_IncRef`, `PyObject_Vectorcall`, `PyErr_GetRaisedException`, ...), so the
  glue declares them itself instead of including `Python.h`: the ABI is what the glue declares, and
  building needs no Python. abi3 serves CPython 3.12+ GIL builds and abi3t (PEP 803) 3.15+ GIL and
  free-threaded builds, from the same program IR. HPy is no longer maintained, and PEP 809's new
  stable ABI is still a draft.
- **Wrappers now, a typed-IR lowering later.** [typed-ir.md](typed-ir.md) §7.4's CPython lowering
  (containers as Python objects, references counted from liveness) needs the IR's step 16 and
  recoverable elaboration first. Here Pystachy keeps its own values and runtime and converts at the
  boundary, behind the same `@export` entry points, which §7.4 can lower another way later.
- **Scalars and str first.** As [#108](https://github.com/den-run-ai/pystachy/issues/108) and #4 §4
  ask, no container is copied across: a copy would lose identity and shared mutation, which need an
  explicit contract first.

## Calling C: `@ffi.extern`

    from ffi import extern, string_at, c_int, c_uint, c_size_t, c_void_p

    @extern("libz.so.1")
    def adler32(adler: c_uint, buf: str, n: c_uint) -> c_uint: ...

    @extern("")                      # the process's own libraries (libc, libm)
    def strdup(s: str) -> c_void_p: ...

    @extern("", "free")              # a C symbol under another Python name
    def c_free(p: c_void_p) -> None: ...

    p = strdup("Wikipedia")
    print(string_at(p, 9), adler32(1, "Wikipedia", 9))
    c_free(p)

`extern(lib, symbol="")` takes the library and the C symbol as string literals, by position or
keyword as the twin's signature takes them (`@extern(lib="libm.so.6")`,
`@extern("", symbol="free")`); a symbol left out or empty is the function's own name, as the
twin's `symbol or f.__name__` is.

When the `def` statement runs, the C function is looked up as `ctypes.CDLL(lib or None)` finds
it: `dlopen(lib, RTLD_NOW | RTLD_LOCAL)`, then `dlsym` in that handle (`pys_c_bind`), and the
stub calls it through the address it stored. A missing library raises `OSError` there, and a
missing symbol `AttributeError`, each with `dlerror()`'s text, as ctypes does. The library is a
platform soname or a path, passed as it is to dlopen and to ctypes; nothing is linked. Under
`pystachy run` the process is lli, whose own libraries (LLVM's dependencies: libz, libzstd,
libedit, libffi, libxml2, ...) are in the global scope; the handle lookup does not see them, and
the library is opened with `RTLD_DEEPBIND` there, so that its own calls bind as in an AOT build.

| annotation | C type | checks |
|---|---|---|
| `ffi.c_int` | `int` (32 bits, sign-extended) | `OverflowError` outside [-2**31, 2**31) |
| `ffi.c_uint` | `unsigned int` (zero-extended) | `OverflowError` outside [0, 2**32) |
| `ffi.c_int64`, `ffi.c_ssize_t` | `int64_t`, `ssize_t` | |
| `ffi.c_uint64`, `ffi.c_size_t` | `uint64_t`, `size_t` | an argument must be >= 0; a result must be below 2**63 |
| `ffi.c_void_p` | a pointer, carried as an int (NULL is 0) | |
| `float` | `double`, as it is (the sign of zero, infinities and NaN too) | |
| `str` | `const char *` to the str's UTF-8 bytes, NUL-terminated, valid during the call | `ValueError` for a NUL in it |
| `ffi.c_buf` (argument) | the same pointer, NULs allowed (pass the length separately) | |
| `str` (result) | a `char *` copied into a new str | `ValueError` for NULL |
| `str \| None` (result) | the same, NULL is `None` | |
| `None` (result) | `void` | |

A call binds its arguments as the `def`'s own parameters do: by position or keyword, with the
defaults it declares (the twin binds them with `inspect.signature`). `ffi.string_at(addr, n)`
copies n bytes at addr into a str (`ValueError` for n < 0, where ctypes would read up to a NUL).
In the C stub's own types, `c_int` and friends are `int`, so a C integer is an ordinary int
everywhere else.

Rejected at compile time, each with its own message (tests/ffi/errors): a bare `int` (say
which C integer type: without the header the compiler cannot know its width), `bool`,
containers, classes and other optionals; a body other than `...`; a parameter without an
annotation, or `*args`; a library or symbol that is not a string literal, or that has a NUL
character in it (ctypes raises `ValueError: embedded null byte` for the library's, and would
look the symbol up only as far as the NUL); arguments that `extern(lib, symbol="")` does not
take, with CPython's `TypeError` message (an unknown keyword, a second value for `lib` or
`symbol`, a third argument, no library); `@extern` on a method; one C symbol declared twice
with different types, or with other types than the runtime's own declaration of it (`memchr`,
`fabs`, ...); and a reserved symbol (`pys_*`, `pyx_*`, `PyInit_*`, `PyModExport_*`, `main`).
Structs by value, varargs and callbacks are not offered: write a small C shim with scalar
arguments and put it in a library.

A call of an `@extern` function may do anything as far as the compiler knows (every effect;
inside a `try` it is an `invoke`). A C++ exception or a `longjmp` across Pystachy frames, a C
function that keeps a str's pointer after it returns, or a declaration whose widths are not
the C prototype's, are undefined behaviour, as with ctypes. Once a C function has been looked
up, Pystachy writes and reads floats in the C locale whatever `setlocale` a C function calls.

A program's own `ffi.py` (or `ffi/` package) on its module path comes first, as under CPython:
Pystachy's builtin `ffi` is then not used (tests/ffi_own.py).

## CPython calls Pystachy: `pystachy ext`

    # fastmath.py: CPython can run it as it is (with the twins), or import it compiled
    from ffi import export

    @export
    def fib(n: int) -> int:
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    $ pystachy ext fastmath.py                  # fastmath.abi3.so: CPython 3.12+ GIL builds
    $ pystachy ext fastmath.py --abi abi3t      # fastmath.abi3t.so: CPython 3.15+, GIL and free-threaded

Both come from the same program IR; the generic glue is `pyext.c`, compiled once per ABI
without `Python.h` (it declares the stable-ABI functions it uses, as the ABI fixes them), and
`pyembed.c`; their bitcode is cached beside the runtime's, by its rules
([runtime-in-subset.md](runtime-in-subset.md) §1.4). The program, the glue and the runtime become one module, of which only the entry
(`PyInit_<name>` or `PyModExport_<name>`) stays visible; `tools/abi_check.sh` checks that, and
that every Py symbol it imports is in the stable ABI of its version.

- The module's public functions must be `@export`, and take and return `int` (64-bit), `float`,
  `bool` or `str` (or return `None`), positionally, without defaults or `*args`. Pystachy code
  may not call an `@export` function (under CPython each call goes through the export's checks):
  call a private function both use. A public class or variable is an error (they cannot cross
  yet); name them with a leading underscore.
- The module's code runs once, at import, with `__name__` the module's name (so its
  `if __name__ == "__main__":` block does not run) and `sys.argv` the host's. `print()` writes
  through Python's `sys.stdout` (so `contextlib.redirect_stdout` works, and a `None` one prints
  nothing), a failed write raises in the program as it does under CPython, and `input()` and
  `sys.stdin` are the host's (a replaced `sys.stdin` is read).
- Every call is caught at the boundary: no Pystachy exception unwinds through CPython's frames.
  An exception leaves as the builtin class of its name (one of the program's classes: its
  nearest builtin base), with its `args` rebuilt from their repr.
- Exported functions are builtin functions whose `__self__` is the module, so they pickle by
  name (`multiprocessing` works).
- When the host's interpreter exits, an `atexit` handler closes the module's open files before
  modules are torn down, as CPython would; the module refuses calls after that.
- An import that failed may be tried again (the code runs again, as CPython's would); a second
  import of a module that loaded is refused.

## Next: Pystachy calls CPython (`lib/pyobj.py`)

Not built yet; designed and prototyped as follows. `pyobj` is plain subset code (`lib/pyobj.py`)
that declares about 35 functions of CPython's stable ABI with `@extern("python")`, where `python`
means the libpython named by `$PYSTACHY_LIBPYTHON` (CPython 3.12 or later): `pystachy run` loads it
into lli (`-dlopen`), and an AOT build links it. Its API is `Object` (`attr`, `call`, `[]`, `len`,
`to_int`, `to_float`, `str`, `repr`, `close`), `import_module`, `of_int`, `of_float`, `of_str` and
`of_list`, and its twin `tools/rt_cpython/pyobj.py` is the same API over live objects. CPython starts
as `python3` starts it (PEP 538 and 540), Pystachy's and Python's output and input are one stream in
order, a Python exception arrives as the nearest class Pystachy has, an `Object` owns one reference,
and a dropped one is released after a collection (each counted with its `sys.getsizeof()`, so
dropped large objects start collections), or at exit, when CPython is finalized.

## Deviations

Against CPython running the same files with the twins (tools/rt_cpython):

- **str** is byte-indexed UTF-8 inside Pystachy, in either direction (the existing deviation,
  [language.md](language.md#deviations-from-cpython)). A C string that is not valid UTF-8, from
  `string_at` or a `-> str` result, is read as it is, where the twin's decode raises
  `UnicodeDecodeError` (as files are read).
- **Which process looks a symbol up.** `@extern("")` means the process's own libraries:
  python3 links libz and libexpat, lli has LLVM's dependencies loaded, and an AOT build has only
  libc and libm (`zlibVersion` is found by the twin and by `pystachy run`, and is an
  `AttributeError` at the `def` of an AOT build). Name the library. Likewise, a library's own
  calls of a function that the process's global scope also defines may bind differently in
  python3's process (its libz) than in an AOT build; `pystachy run` binds them as an AOT build
  does.
- **C's stdio** output from an `@extern` function interleaves with `print()` only as the two
  buffers are flushed.
- **Float text** is the C locale's whatever the host's `setlocale` says, as CPython's own float
  conversions are; format type `'n'`, which CPython takes from the locale, is the C locale's too.
- **Extension modules:**
  - **64-bit ints** at the boundary: an argument or result outside int64 raises
    `OverflowError` ("int too big to convert", "integer result does not fit in 64 bits"); the
    export twin raises the same. Overflow inside the function is the existing checked-int
    deviation.
  - **An exception the module's code raises at import** leaves as the nearest builtin class, as
    a call's does (`m._Bad(ValueError)` arrives as `ValueError`, same `args`); the source run
    raises the module's own class.
  - **One import per process:** a second import after one that succeeded (after deleting it
    from `sys.modules`, or `importlib.reload`) raises `ImportError`, where CPython would run the
    source again.
  - **The importing thread only:** a call from another thread raises `RuntimeError` (the twin
    enforces the same rule). Compiled code never releases the GIL, so a long call blocks other
    Python threads and a Ctrl-C arrives when it returns.
  - **The GIL:** on 3.15t an abi3t module turns the GIL on, with CPython's RuntimeWarning
    (`Py_mod_gil` = used), and its import raises `ImportError` under `PYTHON_GIL=0`. An
    `.abi3.so` raises `ImportError` on 3.13t and 3.14t, which load it but cannot use it.
  - **No re-entry from I/O:** a call back into the module from the host's `sys.stdout`,
    `sys.stderr` or `sys.stdin` while the module prints or reads raises `RuntimeError`.
  - **`sys.stdout.write` with `sys.stdout` set to `None`** does nothing in the module, as
    `print()` does, where CPython raises `AttributeError`.
  - **After the host's atexit handlers** (an `atexit` handler registered before the module was
    imported, or code run while modules are torn down), a call raises `RuntimeError`.
  - **Running out of memory** inside a collection, and running out of stack, end the host
    process.

## Limitations

- **Platforms:** x86-64 Linux (LP64, Itanium unwinding, glibc) is what is tested. macOS needs
  `-undefined dynamic_lookup` for `ext` and has no `RTLD_DEEPBIND`; Windows (python3.dll, SEH) is
  out of scope.
- **CPython versions:** an `.abi3.so` imported by CPython 3.11 fails with the dynamic loader's
  `ImportError` (undefined symbol `PyErr_GetRaisedException`); the wheel tag `cp312-abi3`
  keeps installers from offering it there.
- **Stack switching** (greenlet, gevent, any coroutine library that switches C stacks) while
  compiled frames of an extension module are live is not supported and not detected: the
  collector scans one contiguous stack from the outermost entry.
- **Two Pystachy extension modules** in one process each carry their own runtime and heap;
  objects cross between them only as copies through Python.
- **Not yet:** keyword arguments and defaults for `@export`; classes and exception classes across
  the boundary; callbacks into Pystachy from C; calls from any thread.
- **Containers do not cross by copy.** As [#108](https://github.com/den-run-ai/pystachy/issues/108)
  asks of typed/dynamic adapters, the boundary starts with scalars (and str, which is immutable): a
  copied list or dict would lose its identity and shared mutation, which need an explicit contract
  first. Pystachy code will reach Python's containers through `pyobj` Objects (the next step),
  without copying them.

## Invariants for maintainers

- **Pay for use.** Each piece is opt-in: an `@extern` of a program, or the `ext` command.
  `pyext.c` and `pyembed.c` are linked only into extension modules, `-ldl` only into programs
  that look C functions up, and the runtime's hooks (`std_hook`, `in_hook`, the C locale for
  floats) stay empty otherwise, at the cost of a test of a null pointer on a write. `make irsame`
  against the commit before the FFI must find every corpus program identical; `ffi` is left out
  of the missing-module message for that reason.
- **No Python to build.** Nothing includes `Python.h`, and the driver never runs python3, so the
  Python-free stage of `make verify` still rebuilds everything. `pystachy ext` is not part of that
  stage; header-free glue is kept for reproducibility (the ABI is what the glue declares, not
  what some installed header says) and so that no Python install is needed to build an
  extension.
- **The twins are the API.** A change to a check, a message or a name changes the twin and the
  native code together; `tests/ffi/run.sh` compares them (C calls against recorded output,
  extension modules live against the twins on the same CPython).
- **One thread, and when the GIL can change hands.** The runtime is single-threaded and has no
  TLS (lli cannot relocate native TLS in an extra object). In an extension module, compiled code
  holds the GIL, but not throughout: `print`'s `sys.stdout.write` may release the GIL for I/O,
  so other Python threads run then. What keeps
  the runtime safe is that only the importing thread may enter it (`pyx_call` checks the thread
  id, and `lib_depth` counts nested entries, the outermost of which bounds the stack scan).
- **For a later world lock (calls from any thread):** a `PyCriticalSection` is suspended
  whenever its thread detaches, including on a contended internal mutex, so it does not hold
  across call-outs. The runtime's state must then be parked at every call-out, the stdio hooks'
  Python calls included, not only at the boundary.

## Tests

| command | what it checks |
|---|---|
| `make test-ffi` (`tests/ffi/run.sh`) | `tests/ffi/c_*.py` JIT and AOT against output CPython recorded with the twin (a test library, `tests/ffi/ffitest.c`, whose names lli's libraries also define; a missing library and symbol); `tests/ffi/errors/*.py` rejected with their messages; with `$(PY)`'s libpython, the `tests/ffi/ext` modules against the twins (exceptions, conversions, argv, stdin, stdout redirected, pickling, the C locale), under GC stress |
| `make test` | `tests/ffi_own.py`: a program's own `ffi` module comes first |
| `tools/abi_check.sh TOML SO MAXVER ENTRY` | an extension module defines only its entry and imports only stable-ABI symbols of MAXVER or before (sh, nm and awk) |
