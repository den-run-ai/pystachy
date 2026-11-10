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

### Dynamic file-object boundary

The explicit `Any` annotations in `netio.py` retain selector file objects and
pass them through descriptor lookup. The supported inputs have the closed shape
`Socket | int`; the dynamic annotation does not extend this contract to arbitrary
objects or metadata. `SelectorKey.fileobj` must retain the original object so
identity lookup still works after a socket is closed.

This is compiler debt. On compiler commit `070c8137`, replacing those annotations
with `Socket | int` and removing the dynamic-Any opt-in rejects compilation of
the existing `probe.py` consumer at `DefaultSelector.register()`:

```text
parameter 'fileobj': reference unions cannot mix native references with scalar or container members
```

Retain the current API while that mixed reference/scalar union is unsupported.
Removing the dynamic boundary requires the closed-union consumer to compile and
preserve descriptor lookup, object identity, and GC-stress behavior. See the
[typed/dynamic contract](../../docs/dynamic-any.md#the-typeddynamic-contract).

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
this pipe consumer. Deadlines are checked before waiting, before each ready event,
and after preparing an EOF message, so a late readiness result cannot be accepted
as a successful completion. The launcher still bounds a child that stalls while
writing its completion output.

The consumer retains fragments in batches of 256, joining each completed batch
once and joining the blocks at EOF. For that single final result, each byte is
copied at most twice by accumulation. No append recopies an earlier block.
Batching also bounds retained fragment metadata for one-byte reads: at most one
completed block per 256 bytes, plus an unfinished batch. Native receive copies
and hexadecimal output are separate costs.

`make netio-check` also runs `check_drain.py` in all six modes. The checker
withholds the first pipe's bytes until it observes the second pipe's completed
output, so the consumer must make progress independently of input order. A small
probe exercises empty, partial and multiple fragment batches, including keeping
an earlier result alive while more bytes arrive. The same probes run under both
GC-stress modes. Controlled tests also cover exact limits, one-byte overflow,
would-block, read failures and late EOF cleanup.

## Compiler dogfood and performance

`compiler_dogfood.py` reuses that same drain to collect **real compiler IR
and diagnostics** from three existing corpus programs: a small successful
program, a container program, and a deliberate syntax error. The same worker
compiler runs in every collector mode. Every stdout/stderr byte and exit status
must match an independent serial capture from the CPython-hosted compiler.
The host owns subprocesses; the consumer owns only its inherited descriptors.
The launcher duplicates those descriptors to 64 and above and records the
mapping for comparison with the recorded measurements. That policy originated
as a workaround for [#1154](https://github.com/den-run-ai/pystachy/issues/1154),
which was fixed by [#1162](https://github.com/den-run-ai/pystachy/pull/1162) and
[#1176](https://github.com/den-run-ai/pystachy/pull/1176). The current driver
preserves inherited descriptors; [`jitfdprobe.py`](../../tools/jitfdprobe.py)
checks low descriptors independently of this example's retained FD64+ mapping.

```sh
make netio-dogfood-check
python3.13 examples/netio/compiler_dogfood.py --compiler ./pystachy \
  --samples 3 --json build/netio-compiler-dogfood.json
```

The socket benchmark reuses the same bridge and stdlib oracle. Four original
workloads exercise a small binary message, 16 ready streams, one ready stream
among 64 registrations, and four 64 KiB transfers. Sockets and registrations
persist across timed samples. Nonblocking partial writes and fragmented reads
are handled, and every received fragment must match its stream's binary data.
These are focused stdlib comparisons, not an import or port of CPython's full
`test_socket`/`test_selectors` suites.

```sh
make bench-netio BENCH_ARGS='--cpu 0 --profile --json build/netio-benchmark.json'
# Optional comparison tools in an isolated CPython 3.13 environment:
python -m pip install mypy==2.4.1 Cython==3.3.1 pyperf==2.10.0 setuptools
python examples/netio/benchmark.py --compiler ./pystachy --cpu 0 \
  --pypy /path/to/pypy3 --extension-python /path/to/comparison-venv/bin/python \
  --profile --json build/netio-benchmark.json --pyperf-json build/netio-pyperf.json
python -m pyperf show build/netio-pyperf.json
```

Select a CPU in the current affinity mask, or omit `--cpu` where affinity is
unavailable. Missing explicitly requested runtimes or failed extension builds
fail the run; they are never silently reported as successful comparisons.
The optional pyperf file exports the verified samples; it does not imply use
of pyperf's calibration or worker controller.

Pystachy compiles the consumer **and** native wrapper. CPython/PyPy baselines use
unmodified `socket`/`selectors`. mypyc and Cython compile the unchanged consumer
while retaining the CPython stdlib; the harness verifies that the extension,
rather than its source fallback, was loaded. A separate CPython-bridge mode
measures the existing ctypes twin. No Python runtime is embedded in native modes.

Reports preserve source/compiler/library hashes, runtime versions, build cost,
first and warmed transfer times, complete process times, affinity, host load,
and rotated execution order. JIT process time includes compilation with the
private runtime cache already populated by the preceding AOT build. cProfile
examines Python wrapper costs; optional `strace -c` counts native syscalls after
checking tracer availability. Profiling runs are excluded from timings.

All timings are advisory. These local socket pairs do not establish TCP/WAN
throughput. Compiler dogfood includes actual compilation, buffering and hex
encoding; hex output doubles the payload size. Its bounded small-corpus results are not a compiler speedup
claim or a production scheduler integration. No timing threshold is added to CI.
The [recorded Linux results](results/README.md) include all runtime comparisons,
profiles, native GC smoke and the real compiler collection witnesses.

## Drain accumulation comparison

`benchmark_drain.py` compares a saved consumer revision with the current consumer
using the existing owned-process, bounded-capture and exact-output helpers. It
replays the same freshly captured compiler output for `runtime.py`, an 8 MiB
binary stream and a 64-byte control. CPython uses unmodified stdlib pipe I/O;
Pystachy compiles each whole consumer with the same native wrapper. Compiler
work and AOT builds precede timing. Each sample includes writer/consumer startup,
pipe collection, hex encoding and parent capture/parsing. Before/after variants
are interleaved, and every byte must match before a sample is accepted.

```sh
mkdir -p build
git show b9ab8d9d3065b94c85952c79bada1de43a021c49:examples/netio/drain.py > build/drain-before.py
python3.13 examples/netio/benchmark_drain.py --before build/drain-before.py \
  --compiler ./pystachy --cpu 0 --samples 7 --json build/netio-drain-benchmark.json
```

The report separately models native accumulation-copy volume for deterministic
fragment sizes. It executes each consumer with sized byte proxies whose addition
and join operations count the full result length, matching the current native
bytes operations. This is an algorithmic byte-volume model, not a measured
allocation count, instruction profile or time estimate. CI checks the linear-copy
budget without a timing threshold; the original consumer fails that control.
The [drain results](results/2026-11-08-drain.md) preserve the measurements,
negative controls and limits.

The extra native receive-buffer-to-managed-bytes copy remains. The current
[FFI contract](../../docs/ffi.md#c-types-and-conversions) forbids modifying borrowed
`bytes`, and Pystachy has no mutable byte-buffer type. This consumer change adds
no buffer-ownership API and makes no claim to fix the bulk socket timing gap.

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
