# Native process workers (prototype)

`process.Popen` gives a compiled Pystachy program owned Linux subprocesses. Each
child has a separate address space and may parse strings, allocate containers,
raise exceptions, or run LLVM without entering the owner's managed heap. The
owner remains single threaded. This is an experimental Pystachy API; importing
Python's full `subprocess` module is still unsupported natively.

```python
from process import Popen, run

with Popen(["/bin/cat"]) as child:
    stdout, stderr = child.communicate(b"binary\x00input", timeout=5.0)
    assert child.wait() == 0
    assert stdout == b"binary\x00input"

status, stdout, stderr = run(["/usr/bin/printf", "%s", "literal; argument"])
```

The public wrapper uses ordinary Python syntax. For its CPython twin, add
`tools/rt_cpython` to `PYTHONPATH`. Native Pystachy finds `lib/process.py` normally;
the compiler resolves its private `_pystachy_process` primitives directly to the
C runtime. There is no embedded interpreter and no `os.system()` shell wrapper.
Native spawning is supported in executables and JIT programs. Compiled extension
imports and exported calls reject it with `NotImplementedError`: the CPython
host's signal handling and incomplete-import teardown need their own lifecycle
integration. CPython can use the Python twin or its standard `subprocess` API.

## Supported operations

| Operation | Contract |
|---|---|
| `Popen(args: list[str])` | Start one executable with explicit arguments; `args[0]` must be an absolute path. The current directory and environment are inherited. Standard input, output and error are binary pipes. |
| `pid` | The original child process ID. Ownership is tracked separately with an opaque, nonreused handle. |
| `poll()` / `returncode` | `None` while running; otherwise an exit code, or negative signal number. |
| `wait(timeout=-1.0)` | Wait for exit and return status. A finite timeout raises `TimeoutError` and leaves the child owned and running. |
| `communicate(input=b"", timeout=-1.0, max_output_bytes=16777216)` | Write bytes while draining both output pipes; close stdin, read through EOF, reap the leader, return `(stdout, stderr)`. One call per process. |
| `terminate()` / `kill()` | Send SIGTERM / SIGKILL to the owned group. Idempotent after the leader's exit has been observed. |
| `close()` | Kill a running group, reap the direct child and close all pipes. Calling it twice is allowed; other operations after close raise `ValueError`. |
| `with Popen(...) as child:` | Close on normal return or exception. |
| `run(...)` | Context-managed convenience returning `(status, stdout, stderr)` with the same binary I/O limits. |

The timeout sentinel is exactly `-1.0`; other negative values, NaN and infinities
are refused. A zero timeout is an immediate status check. `communicate` needs
pipe EOF as well as a reaped leader to finish, so a zero communication timeout
may expire even for an already finished child whose output remains unread.

Use `communicate` for children that can fill their pipes. `wait` intentionally
does not drain output: waiting for a child that is blocked writing a full pipe
requires a timeout or a later `communicate` call. Output order is preserved within
each stream; the API makes no ordering claim between stdout and stderr.

`argv` is passed directly to `execv`, without shell expansion or PATH search.
Starting `/bin/sh` explicitly is allowed and means the caller chose a shell.
Arguments containing a NUL byte fail before any child is started. An exec failure
is reported synchronously as its corresponding `OSError` subtype, such as
`FileNotFoundError`; it is not mistaken for an ordinary exit status 127.

## Ownership and bounds

The runtime owns a process group for every started child. A worker's descendants
must not outlive its leader: observing leader exit kills the remaining group
before reaping the leader. Keeping the leader unreaped through that step prevents
a recycled PID from becoming the target of cleanup. Children that intentionally
escape with `setsid` or `setpgid` are outside this cooperative ownership contract;
this is not a sandbox for hostile commands. Other code must not reap these child
PIDs or change SIGCHLD handling. Native spawn checks the current disposition
before allocating or forking and rejects nondefault SIGCHLD handlers, SIG_IGN,
and SA_NOCLDWAIT. Automatic OS reaping would invalidate the retained-PID rule.
The CPython twin also requires default SIGCHLD behavior without external reapers.

The owner keeps handles until explicit `close`, context exit, or runtime exit.
Dropping a Python reference does not make collection an unpredictable process
cancellation mechanism. Normal native exit and unhandled exceptions kill owned
groups and reap direct children. SIGINT also kills groups; the existing runtime
SIGINT behavior remains fatal, so an immediate signal exit can leave reaping to
the operating system. SIGKILL, a native crash, or an externally imposed SIGTERM
cannot promise owner cleanup. Remote execution still needs worker leases.

| Resource | Prototype bound |
|---|---|
| Open process handles | 64, including completed handles until closed |
| Arguments | 1–4096 strings; combined encoded bytes including terminators ≤1 MiB |
| Input | At most 64 MiB per `communicate` |
| Combined stdout/stderr | 16 MiB by default, explicitly adjustable from 0 to 64 MiB |
| Spawn handshake | Five seconds, then kill/cleanup on failure |
| Cleanup | One second of reap polling per close; one shared second across runtime shutdown |

A communication timeout, output limit, or pipe I/O failure kills the group and
closes all pipes before raising. Partial output is discarded on failure. The
original handle remains owned until close; if the OS cannot reap even after
SIGKILL, close raises and retains ownership for later cleanup. The bound covers
user-space polling; the OS cannot guarantee scheduling or immediate removal of a
process stuck in an uninterruptible kernel operation.

The output limit bounds captured data, not the child's memory. Native output
buffers can temporarily reserve up to twice the requested limit across the two
streams; materializing immutable result bytes adds another copy at completion.
Inputs remain rooted on the owning call's stack throughout I/O and joining.
Compiler/application schedulers must reserve CPU and estimated memory separately
and account for tools that launch their own LLVM or BLAS threads. No automatic
pool, task serialization or job retry is provided by this slice.

Linux uses `fork` followed immediately by async-signal-safe descriptor, signal,
process-group and exec operations. It closes inherited descriptors above stderr,
using `close_range`. If the kernel or sandbox does not permit that operation,
spawn fails before exec and cleans up; Linux 5.9 or newer is normally required.
There is no fallback based on `RLIMIT_NOFILE`, because inherited descriptors can
remain above a subsequently lowered limit. All pipe descriptors are close-on-exec.
The child never runs the Pystachy allocator,
collector, exception machinery or Python before exec. Other native platforms
raise `NotImplementedError` at spawn in this prototype.

## Validation and next consumer

`tools/test_native_process_workers.py` compiles one real owner program, compares JIT and
AOT to the live CPython twin, and repeats AOT with collection on every allocation.
Its children exercise allocating JSON work, literal arguments, binary NULs,
simultaneous live children, pipe pressure in both directions, exit statuses,
invalid arguments/timeouts, cancellation, handle exhaustion/reuse, output limits,
normal/exception exit, SIGINT, descendants retaining output pipes, inherited high
descriptors after lowering a limit, unavailable descriptor closure, and compiled
extension rejection (including a failing import), and unsupported inherited
SIGCHLD auto-reaping settings. It runs in
the existing Linux Lint job without adding a CI job or timing threshold.

[`examples/process/compile_batch.py`](../examples/process/compile_batch.py) is a
small native compiler consumer. It starts requests in pairs, with at most two
fresh compiler processes for independent `ir` requests. It writes into a new
private directory and collects bounded diagnostics in input order, closing all
children when it observes a failure. A later request's failure is detected when
its turn is collected; this example is not a completion-driven scheduler. It prints that directory
only after all requests succeed. It intentionally does not share semantic state
or publish results into a shared artifact cache. For example:

```sh
./pystachy build examples/process/compile_batch.py -o /tmp/compile_batch
/tmp/compile_batch "$PWD/pystachy" input1.py input2.py
```

The reusable job runner remains responsible for queue admission, CPU and memory
reservations, artifact validation, and remote execution. This API establishes
that process boundary; it does not make `Gen` reusable, share compiler semantic
state, or accelerate one serial LLVM invocation. An event loop can later expose
readiness on these same pipes, with owned cancellation and cleanup retained.


## Local validation (2026-11-07)

The prototype was checked on Linux x86-64 with LLVM 18.1.3 and CPython 3.13.16,
against base `f7103067545b43cdcd8ce20dc66b1571425b3a8d`. The
[validation record](process-workers-validation.json) retains raw outcomes,
source/artifact identities and both successful and corrected environment runs.
These checks establish correctness and ownership behavior; they are not a timing
comparison or a compiler speedup claim.

| Check | Observed result |
|---|---|
| Native process integration | 11 tests pass: CPython/JIT/AOT, GC on each allocation, native compiler supervision, cancellation and the documented refusal boundaries |
| Complete native bootstrap | Three byte-identical compiler IR witnesses (832,374 lines), and three byte-identical runtime IR witnesses (18,805 lines) |
| Runtime ABI/effects | 651 entries, 70 exception classes, 172 runtime Python functions pass |
| Fast checks | Ruff, mypy for 49 source files, and 412 unit checks pass |
| Recorded expectations | 2,142 recordings, 122 deviations, 11 library copies and 6 pinned agent files pass |
| Native compiler consumer | Final AOT supervisor launches two fresh native compiler children; both emitted artifacts match the same CPython frontend's IR byte for byte |

The required `make irsame REF=f7103067545b43cdcd8ce20dc66b1571425b3a8d`
comparison reported 269 differences with separate library homes. Many diagnostics
embed literal checkout paths, which the oracle intentionally preserves. After
verifying all 89 existing library files and `runtime.py` byte for byte and using
the same base library home, 4,230 of 4,238 cases match exactly. The remaining eight
only add `_pystachy_process` to the list of builtin modules in existing rejection
messages. An expanded report preserves each difference in the validation record;
there are no acceptance, exit-status or emitted-IR changes among these cases.
All eight also pass the repository's unchanged rejection expectations, which
match message excerpts rather than full module lists. No recordings were edited.

The final SIGCHLD guard changes only the C runtime and its probes, after that
corpus run. The final runtime passes a new complete bootstrap and all 11 native
integration checks; the compiler and library sources remain unchanged. The first
recording check used a bare interpreter missing the required `typing_extensions`;
the corrected run used the existing development environment and passed.

Full `make verify`, the complete GC groups and FFI suite, native non-Linux
execution and remote execution remain unrun. This API is a draft runtime slice;
the pairwise example demonstrates native orchestration without making a claim
about completion-driven scheduling or distributed-worker throughput.
