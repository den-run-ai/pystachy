# POSIX `select`

Pystachy implements a bounded native `select.select` API for integer file
descriptors in JIT and AOT. It uses POSIX readiness calls directly. This experimental
subset does not establish `selectors`, `subprocess`, unittest, pytest or pyperf
compatibility.

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
constants. The implementation targets the Linux/macOS POSIX runtime; it does
not implement Windows socket-only select semantics. No descriptor creation API
is added to `os`; applications can use existing C FFI for their native handles.
A file's `fileno()`, also of `sys.stdin`, `sys.stdout` and `sys.stderr`, is its
descriptor, so `select([f.fileno()], [], [], 0)` waits on an open file; a closed
file's raises CPython's `ValueError: I/O operation on closed file`. The file
objects themselves are not accepted in the lists.
`select.error` remains explicitly unsupported: an honest alias needs consistent
import, construction, exception-handler and class-base handling in the compiler.
Promoting integers outside signed 64-bit range are rejected with `OverflowError`
when the descriptor lists cross into the runtime, before timeout validation.
For representable descriptors and accepted numeric timeout values, runtime validation
checks timeout first, then read, write and exceptional descriptors. Within each list, descriptor conversion
and range checks precede the count guard at the first excess item; later items
are not examined. Differential tests cover the competing errors against CPython
3.13.16. Unsupported static types are compile-time errors, so their error ordering
is outside this contract.

## Implementation

One compiler builtin lowers to `pys_select` with three typed lists, a timeout and
an indefinite-wait flag. The runtime calls POSIX `pselect`, returns GC-managed
lists, and records read-list, allocation, I/O and error effects. No CPython
interpreter, extension ABI, object emulation or extra dependency is involved.

## Verification

`tests/programs/library/lib_select.py` covers empty/finite polling, timeout errors and descriptor
bounds in all three input positions. `tests/ffi/c_select.py` uses C stdio to
obtain genuine file descriptors and checks read/write readiness, closed-fd
errors, duplicate/order preservation, fresh lists and indefinite waits through
the Python API. `tests/programs/library/lib_select_sigint.py` exercises an interrupted public wait.
`tests/ffi/py_select.py` checks native and embedded CPython select in the same
program, including a descriptor created by embedded CPython and polled natively.
`tests/programs/library/lib_select_files.py` selects on the descriptors of the standard streams
and of open files (`fileno()`), and checks a closed file's error.
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

The API retains `FD_SETSIZE` bounds and scans up to the highest descriptor;
these are scalability limits. There is no large-server throughput claim.
