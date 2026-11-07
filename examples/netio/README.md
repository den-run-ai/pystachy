# Optional native sockets and readiness

`netio` is a small networking/I/O prototype that runs under CPython and native
Pystachy. A separate C bridge supplies IPv4 TCP, local socket pairs, binary pipe
reads and persistent **epoll on Linux / kqueue on macOS**. It does not change the
compiler, runtime or the normal program's dependencies. The same test program
also runs against CPython's unmodified `socket`, `selectors` and `os` APIs.

The verified platform is **Linux x86-64**, with CPython 3.13.16. The macOS
implementation is present but unexecuted; Windows is unsupported. This optional
module does not make `import socket`, `import selectors` or `asyncio` compile.

## Run the comparison

From the repository root, after the normal [compiler setup](../../docs/install.md):

```sh
make netio-check
# Or select an existing native or hosted compiler:
python3.13 examples/netio/check.py --compiler ./pystachy --repeat 8 \
  --json build/netio-check.json
python3.13 examples/netio/check.py --compiler 'python3.13 pystachy.py' --repeat 2
```

The checker builds `libpystachy_netio.so` in a temporary directory, sets explicit
module/library paths and private caches, and compares twelve scenarios in six
modes: the independent CPython stdlib oracle, the CPython bridge, native JIT and
AOT, and both native modes with collection at every allocation. `--cpython-only`
selects the first two modes. Every subprocess has a timeout; failed or incomplete
runs fail the gate and retain their diagnostics. The JSON report includes source
and library hashes and rejects source changes during validation.

The scenarios cover binary NUL/non-UTF-8 payloads, partial sends and backpressure,
EOF and half-close, would-block, refused connection completion, selector keys
and metadata, modification/unregistration, descriptor reuse, finite deadlines,
explicit cleanup and a readable pipe at descriptor **2048**. Output agreement is
correctness evidence; no throughput, latency or memory-speedup claim is made.

## Supported surface

| Interface | Bounded behavior |
|---|---|
| `socket()` | IPv4 TCP with `AF_INET`, `SOCK_STREAM`, protocol zero; initially blocking, as in CPython. |
| `socketpair()` | Local `AF_UNIX` stream pair; initially blocking. |
| Socket lifecycle | `fileno()`, `close()` and context management; close is idempotent. |
| Connection operations | `bind((host, port))`, `listen(backlog=128)`, `accept()`, `connect()` and `connect_ex()`; canonical numeric IPv4 or an empty host for the wildcard address. |
| Data operations | `send(bytes)` returns the actual byte count; `recv(size)` copies binary data. Empty bytes mean EOF, except that `recv(0)` returns immediately. |
| Modes and addresses | `setblocking()`, `getblocking()`, `settimeout(None/0)`, `gettimeout()`; IPv4 `getsockname()`/`getpeername()`; `shutdown()`. |
| Integer socket options | `SOL_SOCKET` with `SO_REUSEADDR`, `SO_ERROR`, `SO_SNDBUF` and `SO_RCVBUF`. |
| `DefaultSelector()` | `register`, `modify`, `unregister`, `get_key`, `select`, `close` and context management. Read/write masks are 1, 2 or 3; registrations accept sockets or integer descriptors, with integer-or-None metadata. |
| Readiness results | `(SelectorKey, events)` pairs. Keys expose `fileobj`, `fd`, `events`, `data`; they are frozen records rather than stdlib named tuples. |
| Pipe operations | `read(fd, size)`, `set_blocking(fd, flag)`, `close_fd(fd)` correspond to the supported integer-descriptor operations in `os`. |

Receive calls are limited to **16 MiB** and selectors to **4096 registrations**.
Selectors wait for a finite number of seconds, poll with zero/negative timeouts,
or wait indefinitely with `None`. Positive socket timeouts are deliberately
unsupported: use nonblocking sockets and a selector with a monotonic deadline.
NaN/infinite selector timeouts and unsupported event masks are outside the
contract and explicitly rejected. Error classes and errno follow the operating
system; diagnostic wording is not a complete stdlib compatibility promise.

DNS, IPv6, UDP, TLS, file-like socket wrappers, flags/buffer variants, arbitrary
metadata and general asynchronous Python execution are outside this prototype.
Socketpair address-query operations are also outside the supported surface.
The `SelectorKey` attribute API is tested; tuple indexing/unpacking of the key
itself is not provided. Use this module from one owner thread.

## Ownership and deadlines

The bridge never retains a managed bytes or list pointer after returning. Sends
borrow bytes only for the syscall. Receives allocate a bounded native buffer;
the wrapper copies its exact length and frees it in `finally`, including when
the copy raises. The selector keeps managed keys in Python and stores only
monotonic registration tokens in the kernel, so stale events cannot identify a
new registration by a reused descriptor alone.

Use a context manager or `try/finally` for every socket and selector. Automatic
garbage-collection closing is not implemented. Unregister descriptors before
closing them; the selector does not own registered descriptors. Created sockets
and selector handles are non-inheritable. Socket sends suppress SIGPIPE locally,
without changing the process's signal disposition.

Short operations retry EINTR where no bytes were transferred. Selector retries
reuse one monotonic deadline and bound each native wait to one second. Arbitrary
Python signal-handler behavior and cross-thread cancellation are unverified.
Write readiness after a nonblocking connect must be followed by
`getsockopt(SOL_SOCKET, SO_ERROR)`; it is not proof of connection success.

[`drain.py`](drain.py) demonstrates readiness-driven collection of multiple
inherited worker-output pipes. It enforces an overall deadline and a per-pipe
output bound, emits completed streams as EOF is observed, and closes all its
descriptors on exit. The launcher still owns spawning, exit-status collection and
termination of workers. Native process lifecycle integration is separate from
this pipe consumer.

`make netio-check` also runs `check_drain.py` in all six modes. The checker
withholds the first pipe's bytes until it observes the second pipe's completed
output, so the consumer must make progress independently of input order.

## Standalone native ownership check

The C probe covers 300 lifecycle cycles, binary buffer ownership across later
calls, invalid bounds, SIGPIPE suppression and a pipe descriptor above 1024:

```sh
mkdir -p build/netio
cc -std=c11 -O1 -g -Wall -Wextra -Werror -Wpedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  examples/netio/netio.c examples/netio/ownership.c -o build/netio/ownership
ASAN_OPTIONS=detect_leaks=1 build/netio/ownership
```

ASan and UBSan passed locally with `detect_leaks=0`; the executor's ptrace setup
prevented LeakSanitizer from running. Descriptor-count checks passed, but a native
heap leak scan and macOS execution remain outstanding.

All code here is original project code. API references:
[CPython socket](https://docs.python.org/3.13/library/socket.html),
[selectors](https://docs.python.org/3.13/library/selectors.html), and the project's
[FFI lifetime contract](../../docs/ffi.md#pointer-lifetimes-and-foreign-control-flow).
