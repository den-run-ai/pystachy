# Owned libuv TCP prototype

This optional example explores an asynchronous C I/O boundary that the same
Python source can use under CPython and native Pystachy. It sends bounded TCP
requests concurrently, half-closes each write side, collects replies through
EOF, and returns completions in the order observed by the event loop.

The API is deliberately small and experimental. It uses actual `uv_tcp_t` and
`uv_timer_t` handles. It does not implement `socket`, `selectors`, `asyncio`,
coroutines, DNS, TLS, server sockets, pipes, processes or filesystem operations.
The build and descriptor probe currently target Linux. Libuv's support for
other platforms does not establish support for this binding on those platforms.
Nothing is added to Pystachy's default build or runtime dependencies.

## Build and check

Use the repository's pinned Python and LLVM setup, and build the native compiler
with `make`. The checker needs a C compiler and libuv development files. It uses
`pkg-config libuv` by default, or an explicit installation prefix. The tested
upstream version is [libuv 1.53.0, commit
840404ce8ba7cc0204be52389a6cfff9f2c90fb6](https://github.com/libuv/libuv/tree/840404ce8ba7cc0204be52389a6cfff9f2c90fb6).
For an isolated installation:

```sh
uv_src=/tmp/pystachy-libuv-src
uv_prefix=/tmp/pystachy-libuv

git clone --branch v1.53.0 --depth 1 https://github.com/libuv/libuv.git "$uv_src"
test "$(git -C "$uv_src" rev-parse HEAD)" = 840404ce8ba7cc0204be52389a6cfff9f2c90fb6
cmake -S "$uv_src" -B "$uv_src/build" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX="$uv_prefix" \
  -DBUILD_TESTING=OFF -DLIBUV_BUILD_TESTS=OFF -DLIBUV_BUILD_BENCH=OFF
cmake --build "$uv_src/build" --parallel 2
cmake --install "$uv_src/build"

python3.13 examples/uvio/check.py --libuv-prefix "$uv_prefix" \
  --compiler ./pystachy --sanitizers --json build/uvio-check.json
```

`--cpython-only` skips Pystachy compilation/execution. `--repeat` controls the
small lifecycle workload, from 1 to 64. `--cc` selects the C compiler. The
`uvio-check` Make target forwards `UVIO_CHECK_ARGS`, for example:

```sh
make uvio-check UVIO_CHECK_ARGS="--libuv-prefix /tmp/pystachy-libuv --sanitizers"
```

The checker builds the shared bridge in a temporary directory and sets the
loader/import paths for its subprocesses. For a standalone consumer, build it
once and point the two runtimes at the same bridge:

```sh
mkdir -p build/uvio
cc -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror -O2 -fPIC -shared \
  $(pkg-config --cflags libuv) examples/uvio/bridge.c \
  $(pkg-config --libs libuv) -o build/uvio/libpystachy_uvio.so
export LD_LIBRARY_PATH="$PWD/build/uvio${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$PWD/tools/rt_cpython:$PWD/examples/uvio"
export PYSTACHY_PATH="$PWD/examples/uvio"
```

CPython uses the existing [`ffi` twin](../../tools/rt_cpython/ffi.py). Native
Pystachy lowers the same [`uvio.py`](uvio.py) declarations through its normal
[FFI](../../docs/ffi.md). No Python callback is called by C.

## Python interface

```python
from uvio import Loop

with Loop(capacity=16, byte_limit=65536) as loop:
    request = loop.submit("127.0.0.1", 9000, b"hello\0world", timeout_ms=1000)
    finished = False
    while not finished:
        for result in loop.run_once():
            print(result.request_id, result.error_name(), result.data)
            finished = result.request_id == request
```

The peer must understand an exchange terminated by write-side EOF and close
its own write side when its reply is complete. The checker supplies such a
peer. This is a request/reply transport primitive, not a general persistent
connection protocol.

| Operation | Contract |
|---|---|
| `Loop(capacity=16, byte_limit=65536)` | Capacity is 1–64; input and output budgets are each 1–1,048,576 bytes per request. |
| `submit(address, port, data, timeout_ms=1000)` | Numeric IPv4 only, port 1–65535, bytes payload, deadline 1–60000 ms from submission. Returns a monotonic request ID. |
| `run_once(block=True)` | Runs one native loop turn and copies all available terminal completions. A turn can return an empty list. `False` polls without waiting. |
| `cancel(request_id)` | Starts cancellation and returns `True`, or returns `False` if that live request is already terminal. A consumed or unknown ID fails. |
| `close()` | Cancels active requests, runs their pending callbacks and closes all handles before freeing native storage. Repeated calls are harmless. |

A completion contains `request_id`, libuv integer `status`, and copied `data`.
`error_name()` returns `OK`, `ETIMEDOUT`, `ECANCELED`, `ENOBUFS` or another libuv
name. Failed requests may contain a partial reply; an oversized reply keeps
exactly the configured byte limit and terminates with `ENOBUFS`. Immediate
admission/transport-setup errors raise `OSError` with a libuv name; these are
not CPython socket errno objects. Invalid Python API bounds raise `ValueError`.

The loop must be used on its creating thread. The bridge rejects operations
from other threads before entering C, and rejects reentrant public operations
(such as closing during a signal handler); this does not introduce
managed-object multithreading. Use `with` or `try/finally`: there is no implicit
GC-driven resource teardown. A blocking foreign call returns when libuv makes
progress or a request deadline expires; Python signal responsiveness during
that wait is outside this prototype's contract.

## Ownership and bounds

`submit` copies its borrowed Python input before returning. Native requests,
handles, timers, write buffers and read buffers keep stable native addresses.
Callbacks only update that native state. Completion becomes visible after
both handles close and all in-flight connect/write/shutdown callbacks finish.
Managed execution then copies the result with `ffi.bytes_at`; a `finally`
block releases its native slot even if that copy fails.

Every accepted request reserves one slot through result consumption. Both
active and completed-but-unconsumed requests count toward admission. Each
slot produces exactly one terminal completion, so the event ring is bounded
by the same capacity. Canceling or failing a request does not immediately
reuse its slot. At the hard limits, payload storage is at most 128 MiB per
loop (64 input and 64 output buffers of 1 MiB), plus fixed handles, metadata
and 4 KiB scratch storage per slot. Libuv/kernel buffering is additional.

Deadlines use libuv's monotonic timer clock, refreshed on each submission.
Close stops readers and timers, closes handles, drains callbacks and checks
`uv_loop_close` before disposing storage. It does not wait for a remote peer
to finish its protocol. IDs never silently wrap or identify a newly reused
slot within the same loop.

## Validation and limits

`check.py` uses a separate CPython `socket` peer and socket-only oracle, then
compares exact exercise output under CPython, native JIT, native AOT, and both
native modes with GC stress interval 1. It checks binary/empty/fragmented
replies, a later request completing before a held earlier request, deadlines,
cancellation, connection refusal, input/output limits, admission pressure,
consumed IDs and active/idempotent close.

`ownership.c` independently overwrites and frees each borrowed input before
driving the loop: a retained-pointer implementation would corrupt the reply
or fail under ASan. It performs 32 such exchanges and 64 active cancellation
and close lifecycles, checks cross-thread rejection, and verifies Linux file
descriptor counts return to their warmed-up baseline. `--sanitizers` runs
this standalone bridge probe under ASan and UBSan. It does not instrument
Pystachy's runtime or an externally installed libuv itself. Add
`--leak-check` for LSan where the execution environment permits its process
inspection; this must be reported separately from descriptor cleanup.
The CPython-only `hosted.py` probe checks Python thread guards, an exception
immediately after native close frees the loop, reentrant close rejection,
and slot reuse after a failed managed result copy. Cancellation checks cover
submission, read waits and active close; deterministic cancellation of an
incomplete queued write and allocation-failure injection remain future work.

The stdlib-only checker harness tests run through `make check-fast`; the
libuv/native check is opt-in. The JSON report starts as `running` and ends as
`pass` or `fail`; it includes
source and binary hashes, tool versions and the modes executed. The checker
rejects consumed source changes during a run and kills its subprocess group
on timeout. Passing these tests does not establish a performance advantage, complete allocation-failure coverage,
full compiler verification, or a portable runtime I/O backend. A broader
libuv backend would still need process/pipe ownership, task cancellation and
an independently measured workload before replacing the direct readiness
prototype.
