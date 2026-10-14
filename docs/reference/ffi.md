# Foreign function reference

Read the [FFI guide](../ffi.md) for examples. This page defines the C boundary and
CPython extension behavior implemented on x86-64 Linux with glibc.

The CPython twin, `tools/rt_cpython/ffi.py`, uses ctypes for `extern` and checking
wrappers for `export`. Its checks and error messages are the comparison contract;
`tests/ffi/run.sh` compares native behavior with the twin. A program's own `ffi.py`
or `ffi/` package takes precedence over the builtin module, as under CPython.

## Declaring and resolving C functions

`extern(lib, symbol="")` takes string literals, by position or keyword. An omitted
or empty symbol uses the function's name. When the `def` runs, `pys_c_bind` uses
`dlopen(lib, RTLD_NOW | RTLD_LOCAL)` and resolves the symbol in that handle with
`dlsym`. `@extern("")` uses the process's libraries, as `ctypes.CDLL(None)` does.
A missing library raises `OSError`; a missing symbol raises `AttributeError`, with
`dlerror()` text. Library names and paths are passed through without translation.

Calls bind positional and keyword arguments and declared defaults using the
function's normal signature. The compiler rejects:

- Bare `int`, `bool`, containers, classes and optionals other than a `str | None`
  return; every C integer must specify its width.
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
| `str` argument | `const char *` | NUL-terminated UTF-8 bytes, valid during the call; NUL in the value raises `ValueError`. |
| `ffi.c_buf` argument | `const char *` | Same bytes, NULs allowed; pass the length separately. |
| `str` result | `char *` | Copied into a new string; NULL raises `ValueError`. |
| `str \| None` result | `char *` | Copied into a new string; NULL becomes `None`. |
| `None` result | `void` | No value. |

C integer annotations are ordinary `int` inside a stub's subset signature.
`ffi.string_at(addr, n)` copies `n` bytes into a string; negative `n` raises
`ValueError` rather than reading to a NUL as ctypes would.

## Pointer lifetimes and foreign control flow

A C function must not retain a `str` or `c_buf` pointer after returning. Returned
strings are copied; that copy does not free the source allocation. If C allocated
it, declare a pointer result, copy it with `string_at` and call the library's
matching deallocator. Pointer addresses and lengths must designate valid memory.

A declaration must match the real C prototype. A mismatch in widths or calling
convention, C++ exception or `longjmp` across subset frames, or retained temporary
string pointer causes undefined behavior, as with ctypes. Foreign calls are
conservatively treated as having all effects; inside `try`, a call is an `invoke`.

## Extension modules

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
- Module code runs at import with the module's `__name__` and the host's `sys.argv`.
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
- At interpreter exit, an `atexit` handler closes module files before module
  teardown. Calls after that handler has run are refused.

### Threading and host lifetime

Only the importing thread may call the module; another thread gets `RuntimeError`.
CPython subinterpreters are unsupported for both extension ABIs.
The runtime is single-threaded and has no TLS. Computation holds the GIL, so long
calls delay other Python threads and Ctrl-C. Host I/O calls can release the GIL;
thread-ID and entry-depth checks still protect the runtime.

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

## Deviations from CPython and the twin

| Area | Behavior |
|---|---|
| Strings | Byte-indexed UTF-8 inside Pystachy. Invalid UTF-8 returned from C is kept as bytes in a string; the twin's decode raises `UnicodeDecodeError`. |
| Process symbol lookup | `@extern("")` sees different libraries in CPython, `lli` and an AOT executable. Name a library explicitly. |
| Library interposition | `lli`'s libraries can affect global bindings. JIT opens the named library with `RTLD_DEEPBIND` to bind its internal calls like AOT; CPython's process may still bind differently. |
| C output | Foreign stdio and subset `print` interleave according to their separate buffers and flushes. |
| Float text | Conversions use the C locale even if foreign code changes `setlocale`; format type `n` also uses the C locale. |
| Extension integers | Arguments or results outside signed 64-bit raise `OverflowError`, as the export twin does. Internal arithmetic remains checked. |
| Extension import exceptions | Custom exception classes leave as their nearest builtin base, rather than the source module's own class. |
| Re-import | A second successful module load raises `ImportError`; source code can be run again by CPython. |
| `sys.stdout = None` | Both `print` and `sys.stdout.write` do nothing in the extension; CPython's explicit `write` raises `AttributeError`. |
| Late calls | Calls after the module's shutdown handler raise `RuntimeError`, including from earlier-registered host `atexit` handlers. |

For general language differences, see [compatibility](../language/compatibility.md).

## Platform and API limits

The tested platform is x86-64 Linux with LP64, glibc and Itanium exception
unwinding. macOS would need `-undefined dynamic_lookup` for extensions and lacks
`RTLD_DEEPBIND`; Windows requires another loader and unwinding implementation.

Keyword arguments/defaults for exports, public classes, exception classes,
containers, C callbacks and calls from arbitrary threads are unsupported. Mutable
containers are not copied implicitly because that would lose identity and shared
mutation; see [#108](https://github.com/den-run-ai/pystachy/issues/108).
Calling CPython from a Pystachy program is proposed in
[PR #170](https://github.com/den-run-ai/pystachy/pull/170), not implemented on `main`.

## Maintainer checks

- Keep twins and native checks/messages in agreement. `make test-ffi` covers C
  declarations in JIT/AOT, compile-time rejections and extension behavior under
  GC stress, using the configured CPython for live twin comparisons.
  Extension checks require CPython 3.12+ with shared `libpython`; the runner reports
  skipped cases when the configured interpreter cannot load extensions.
- Keep glue opt-in: `pyext.c` and `pyembed.c` are linked only for `ext`, and `-ldl`
  only for extensions or programs that resolve foreign functions. Programs that
  do not use FFI retain their normal runtime path.
- Keep builds independent of Python headers. The driver does not need to launch
  CPython to build an extension; live compatibility checks still need CPython.
- `tools/abi_check.sh TOML SO MAXVER ENTRY` checks that only the entry is defined
  publicly and every imported Python symbol belongs to the target stable ABI.
- `make test` checks that a program's own `ffi` module takes precedence.

A future lock supporting arbitrary host threads must preserve runtime state over
all call-outs, including I/O. `PyCriticalSection` may suspend whenever its thread
detaches and cannot alone provide that contract.
