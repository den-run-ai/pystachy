# POSIX `select` prototype

This prototype adds a real native `select.select` boundary for integer file
descriptors, in JIT and AOT. It is part of the missing builtin-module work in
[#491](https://github.com/den-run-ai/pystachy/issues/491) and the stdlib milestone
[#11](https://github.com/den-run-ai/pystachy/issues/11). It does not establish
`selectors`, `subprocess`, native unittest, pytest or pyperf compatibility.

## Contract

```python
import select
readable, writable, exceptional = select.select(read_fds, write_fds, error_fds, 0.1)
```

- The three positional descriptor arguments are `list[int]`, including `[]`.
  Each result is a new list, preserving the input's order and duplicates. Inputs
  remain unchanged; the returned tuple holds three independent lists.
- Timeout is a positional `int`, `bool`, `float`, literal `None`, or omitted.
  Zero polls, finite positive values wait, and `None`/omission waits indefinitely.
  A dynamically optional timeout must first be narrowed with `is not None`.
- Negative, NaN and overflowing timeout values raise the CPython 3.13.16 errors.
  Descriptor validation checks C-int bounds, nonnegativity, `FD_SETSIZE` and input
  count before using the C `FD_SET` macro. Closed descriptors report the OS error.
- Non-raising signal interruptions retry after rebuilding all descriptor sets.
  Finite waits use the remaining time to a monotonic deadline. The runtime blocks
  SIGINT before entering the I/O region, then `pselect` atomically restores the
  caller's mask while waiting. This prevents a Ctrl-C just before an indefinite
  wait from being noted and then lost. The previous mask is restored before any
  result or error. SIGINT follows the runtime's existing uncaught
  `KeyboardInterrupt` behavior; this does not add a
  general signal-handler API or catchable KeyboardInterrupt support.

Unsupported forms are compile-time errors, not successful no-op calls: arbitrary
iterables, `fileno()` objects, dynamically optional timeout values, keyword
arguments, `select.error`, `PIPE_BUF`, `poll`, `epoll`, `devpoll`, `kqueue` and their
constants. The prototype targets the existing Linux/macOS POSIX runtime; it does
not implement Windows socket-only select semantics. No descriptor creation API
is added to `os`; applications can use existing C FFI for their native handles.
`select.error` remains explicitly unsupported: an honest alias needs consistent
import, construction, exception-handler and class-base handling in the compiler.
For accepted list/numeric values, runtime validation checks timeout first, then
read, write and exceptional descriptors. Within each list, descriptor conversion
and range checks precede the count guard at the first excess item; later items
are not examined. Differential tests cover the competing errors against CPython
3.13.16. Unsupported static types are compile-time errors, so their error ordering
is outside this contract.

## Architecture and comparison

One compiler builtin lowers to `pys_select` with three typed lists, a timeout and
an indefinite-wait flag. The runtime calls POSIX `pselect`, returns GC-managed
lists, and records read-list, allocation, I/O and error effects. No CPython
interpreter, extension ABI, object emulation or extra dependency is involved.

Sources reviewed for this scope:

| Source | Relevant design |
|---|---|
| [CPython 3.13 select documentation](https://docs.python.org/3.13/library/select.html), [test_select.py at v3.13.16](https://github.com/python/cpython/blob/v3.13.16/Lib/test/test_select.py) | Real readiness, fresh result lists, invalid/closed descriptor errors, blocking waits and interrupted-call retry. |
| [PyPy interp_select.py, Python 3.11 branch snapshot 3ce8ee9](https://github.com/pypy/pypy/blob/3ce8ee955977343ff96902fdedbc5dad535d0f95/pypy/module/select/interp_select.py) | Interpreter-level wrappers reach the OS, preserve original inputs and recompute interrupted timeouts from a monotonic deadline. Pystachy's initial boundary accepts only integer descriptors. |
| [GraalPy SelectModuleBuiltins.java, snapshot 7e7182b](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/SelectModuleBuiltins.java), [POSIX backend documentation](https://www.graalvm.org/jdk23/reference-manual/python/Embedding-Permissions/) | Select uses a platform-service boundary; native and Java-backed descriptors have different interoperability limits. Pystachy uses native descriptors directly. |

This is an independent implementation, not a copied PyPy or GraalPy module.
The native service boundary is useful precedent; their broader dynamic object,
event-loop and signal infrastructure is outside this small prototype.

## Acceptance and remaining work

`tests/lib_select.py` covers empty/finite polling, timeout errors and descriptor
bounds in all three input positions. `tests/ffi/c_select.py` uses C stdio to
obtain genuine file descriptors and checks read/write readiness, closed-fd
errors, duplicate/order preservation, fresh lists and indefinite waits through
the Python API. `tests/lib_select_sigint.py` exercises an interrupted public wait.
`tests/ffi/py_select.py` checks native and embedded CPython select in the same
program, including a descriptor created by embedded CPython and polled natively.
All are CPython 3.13.16 differential cases, with JIT/AOT and GC-stress coverage.

These cases adapt the *intent* of upstream `test_error_conditions`, `test_errno`
and `test_returned_list_identity`; they are not the unmodified upstream unittest
suite. The C readiness loop mirrors the useful producer/reader pattern of
upstream `test_select` using real pipes without requiring `subprocess` or
`fileno()` object support.

`make selectprobe` checks real pipe readiness, duplicated descriptors, EOF,
repeated EINTR with finite deadline, and blocking retry while a producer sends
bytes. Child processes deterministically test an already-noted SIGINT and a
SIGINT injected after entering I/O, immediately before the kernel wait; a watchdog
makes a lost signal fail instead of hanging. The probe also checks preservation
of the caller's signal mask. It runs normally and with collection on every
allocation, and is required by `make verify`'s `select-io` step in the `contracts`
CI group. Timing is used
only to verify that a wait is not shortened; there is no throughput threshold.

Follow-ups should prioritize a concrete `selectors.SelectSelector` consumer,
then typed `fileno()` objects with original-object return mapping. Do not expose
`poll`/`epoll` names until their registration, lifetime, error and readiness
contracts work. `FD_SETSIZE` bounds and `select`'s scan of the highest descriptor
remain scalability limits; this prototype makes no large-server performance
claim.
