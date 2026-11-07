# Owned buffers and completions

An optional **local CPU reference backend**, with the same Python wrapper under
CPython and Pystachy JIT/AOT. It exercises copy, broadcast, all-gather and float64
sum all-reduce across buffers representing ranks **in one process**. It does not
communicate between workers. No compiler/runtime changes or external dependencies
are required beyond the existing C/LLVM toolchain.

The verified consumer in [exercise.py](exercise.py) reduces four independent rank
vectors, gathers rank-ordered vectors and broadcasts binary packets. This is an
ownership/completion experiment, not a throughput benchmark or MPI binding.

## Use

From the repository root, on Linux:

```sh
mkdir -p build/comm
cc -std=c11 -O2 -fPIC -shared examples/comm/bridge.c -o build/comm/libpystachy_comm.so
export LD_LIBRARY_PATH="$PWD/build/comm${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$PWD/examples/comm:$PWD/tools/rt_cpython"
export PYSTACHY_PATH="$PWD/examples/comm"
python3.13 examples/comm/exercise.py
./pystachy run examples/comm/exercise.py
./pystachy build examples/comm/exercise.py -o build/comm/exercise
build/comm/exercise
```

The `ffi` CPython twin supplies the call bridge; CPython needs no embedded
Pystachy runtime. Inputs are copied into native-owned allocations. This is a
custom Python API, **not** an implementation of Python's buffer protocol,
`memoryview`, mpi4py or asyncio.

```python
from comm import Context

with Context(capacity=4, byte_limit=4096) as ctx:
    a = ctx.from_f64([1.0, 2.0])
    b = ctx.from_f64([3.0, 4.0])
    x = ctx.buffer("f64", 2)
    y = ctx.buffer("f64", 2)
    request = ctx.allreduce_sum([a, b], [x, y], tag=42)
    a.close()                     # Native request retains its input.
    b.close()
    ctx.progress(1)               # Explicitly execute one queued operation.
    event = ctx.peek()             # Observation does not consume capacity.
    assert event is not None and event.request_id == request
    ctx.ack(request)               # Release leases and completion capacity.
    print(x.to_f64(), y.to_f64())  # [4.0, 6.0] [4.0, 6.0]
```

## Contract

| Interface | Behavior |
|---|---|
| `buffer("u8"/"f64", count)`, `from_bytes`, `from_f64` | Fixed, zero-initialized owned host storage; constructors copy inputs synchronously. |
| `metadata()` | `[dtype, count, nbytes, byte_offset, memory_kind]`; dtype 1=u8, 2=IEEE binary64; memory kind 1=host; native byte order. No public raw-pointer import. |
| `view(offset, count)` | Contiguous item slice retaining the original allocation; checked bounds, including nested and empty views. |
| `write_bytes`/`to_bytes`, `write_f64`/`to_f64` | Exact-length copies. Reads reject a write lease; writes reject any lease on the backing allocation. |
| `copy`, `broadcast`, `allgather`, `allreduce_sum` | Submit and return a positive request ID. Sources have matching dtype/count; gather destinations have `rank_count * count` items. Sum is f64 only, evaluated in source order. |
| `progress(budget=1)` | Execute up to 0–64 queued operations in submission order. No waiting or callbacks into Python. Budget counts operations, not time or bytes. |
| `test(id)` | Observe pending/terminal state without progressing or consuming. |
| `peek()`, `ack(id)` | Observe the oldest terminal event, then explicitly consume a terminal ID. Useful when application handling can fail and must retry. |
| `poll()` | Convenience returning `[]` or one `Completion` in a list. Constructs the result before acknowledging; call repeatedly to drain. |
| `cancel(id)` | Local queued request becomes terminal with status 1, with no output writes. False if already terminal. It still occupies capacity/leases until ack. |
| `close()` | Buffer: revoke user handle, defer freeing retained storage. Context: discard queued work/results, release all native storage and invalidate children. Idempotent Python close. |

`Completion` carries `request_id`, application `tag`, `status` (0=success,
1=cancelled) and `kind` (1=copy, 2=broadcast, 3=allgather, 4=sum allreduce).
Events arrive in completion order: a canceled later request can precede earlier
pending work. Unknown/consumed IDs fail; IDs never wrap or repeat within a context.

An accepted request holds read leases on inputs and exclusive write leases on
outputs **through acknowledgment**, even after `test()` says terminal. Views share
the backing's lease, so even disjoint slices conflict conservatively. Input/output
and output/output backing aliases are rejected before writes; input/input sharing
is allowed. Closing all user handles while pending is safe. No borrowed Python
list, bytes, pointer-cell or GC-managed address is retained by C.

All methods belong to the creating thread and reject reentry. Use `with`/`finally`:
there are no automatic finalizers. Context limits are 1–64 live requests (including
unconsumed results), 128 live user buffer handles, 32 ranks and 0–64 MiB of unique
backing payload. Views do not charge the payload twice; retained closed buffers
still count. Metadata/queue overhead and one-byte empty allocations are additional
bounded overhead. Invalid arguments fail before writes or new leases.

## Backend boundary and limits

The checked descriptors and lifetime rules are reusable; [bridge.h](bridge.h) is
an experimental C interface, not a stable ABI or a registered backend system.

| Future adapter | What it must add beyond this local example |
|---|---|
| Socket/libuv, UCX/UCP, libfabric | Peer addressing, transport errors, progress integration and a quiescent terminal event after all buffer access ends. |
| MPI/UCC | Communicator/team membership, matching collective order and native requests. Cancellation may be unsupported. |
| NCCL/RCCL | Device allocations, device/stream metadata and synchronization events; host descriptors must be rejected or explicitly staged. |
| Worker/task systems | Scheduling, bounded task queues, process ownership and failure handling independently of these data buffers. |

Completion grants **local** buffer reuse after ack. It does not establish peer
delivery, a global barrier or completion of another rank. This follows the useful
distinction in the [MPI nonblocking collective contract](https://www.mpi-forum.org/docs/mpi-5.0/mpi50-report/node147.htm).
The local backend's immediate cancellation must not be assumed for future
collective/transport adapters. A future wait timeout must leave requests and leases
intact; this prototype provides no wait/deadline API or background progress.

Python's [buffer protocol](https://docs.python.org/3/c-api/buffer.html) can support a
future retained exporter adapter. The existing synchronous `pyobj.Buffer` and
DLPack examples are not accepted here: async export retention, mutation discipline,
device synchronization, general strides and zero-copy Python imports are unimplemented.
There is no network, GPU, MPI, persistent-collective, thread-safe or distributed
failure handling claim. Linux x86-64 is the locally validated platform.

## Validation

```sh
python3.13 examples/comm/check.py --compiler ./pystachy --cc clang --sanitizers
python3.13 -m unittest discover -s tools -p test_comm_example.py
```

The harness compares independent Python arithmetic/bytes with CPython's FFI twin,
native JIT/AOT and both modes under GC stress. It checks views, cancellation,
leases, completed-but-unconsumed capacity, bad shapes/types, stale IDs, pending
shutdown, owner-thread rejection and completion conversion failure. The standalone
C ownership probe runs under ASan/UBSan; `--leak-check` adds LeakSanitizer where
supported. Each run hashes consumed inputs and fails if they change mid-run.
`--report PATH` records the compiler hash, source hashes and executed modes.

The existing Lint job runs the harness with the CPython-hosted compiler plus its
unit tests. No CI jobs or dependencies are added. Full repository verification
remains a separate merge gate.
