# Owned libuv source-transfer results

The November 7, 2026 Linux x86-64 run used CPython 3.13.16, PyPy 8.0.1
(Python 3.11.17), libuv 1.51.0, GCC 13.3.0 for the bridge and LLVM 18.1.3 for
native programs. It used the exact compiler/runtime sources of the libuv draft
`5b50ebd`, with the CPython-hosted compiler generating native JIT/AOT programs.
The AMD EPYC 9V74 host was shared; the controller, peer and children were pinned
to logical CPU 0. Sources and compiler inputs were stable throughout the run.

[`2026-11-07-linux-x86_64.json`](2026-11-07-linux-x86_64.json) contains source
hashes, compiler/library identities, tool versions, five samples per cell,
median/min/max, process duration, validation and separate cProfile summaries.
The input was the existing 37,663-byte compiler `lexer.py`, transferred 16 times
per sample. Both clients use identical chunks and the existing independent
eight-thread CPython peer; every completion must return the exact source bytes.
Mode order reverses each repetition.

## Internal transfer times

Times below are medians in milliseconds for the complete 16-round batch.
They include loop creation/close, fresh TCP connections, transfer through EOF
and exact checks. They exclude interpreter startup, loading the source, one
untimed warmup round, and compilation.

| Chunk | In flight | CPython stdlib | CPython libuv twin | PyPy stdlib | PyPy libuv twin | Native AOT |
|---|---:|---:|---:|---:|---:|---:|
| 256 B | 1 | 148.641 | 283.246 | 190.104 | 624.470 | 129.163 |
| 256 B | 8 | 122.534 | 189.092 | 173.374 | 469.779 | 115.965 |
| 4 KiB | 1 | 11.669 | 21.469 | 23.742 | 186.490 | 12.209 |
| 4 KiB | 8 | 9.211 | 13.957 | 17.291 | 121.726 | 9.222 |
| 32 KiB | 1 | 4.244 | 5.796 | 7.373 | 44.154 | 4.606 |
| 32 KiB | 8 | 4.306 | 5.155 | 6.417 | 33.149 | 5.261 |

Native AOT is near the independent stdlib client, with median speed ratios
0.82–1.15x across these cases. Repeated ranges overlap substantially: for
4 KiB/eight requests, CPython spans 8.716–11.526 ms and native 8.055–9.458 ms.
For 32 KiB/eight requests, native spans 4.228–7.742 ms. This run supports
correctness and rough parity, not a general libuv speedup. Loopback scheduling,
the Python peer and fresh connection cost limit interpretation.

PyPy receives only one untimed source round in each fresh process. These numbers
describe that finite-batch policy; they do not establish converged PyPy JIT
throughput. The direct-netio benchmark separately tests longer warmed consumers
and mypyc/Cython. No CPython socket-suite or upstream pyperformance pass is claimed.

## Validation and profiles

Native JIT, JIT GC stress and AOT GC stress passed separate exact-byte/count
checks before the timed AOT runs. The CPython/PyPy stdlib and libuv twin modes
validated every measured sample. The source layer also rejects oversized input,
corrupt/duplicate/unknown completions, failed requests and incomplete reports.
Bridge build cost was 0.142 s; native AOT preparation was 8.225 s, recorded
separately with a private runtime cache. Native process spawning is not added.

Separate cProfile runs show stdlib time in epoll waiting, connection setup and
consumer dispatch. The libuv twin's `ffi.call` includes native waiting as well as
marshalling; its cumulative time is not all Python overhead. `inspect.bind` is
a separately visible wrapper cost. These are Python profiles, not native libuv
CPU profiles. Controller-level SIGTERM during subprocess launch remains unvalidated;
the library's own request cancellation/owned shutdown contract is separate.

```sh
python3.13 examples/uvio/dogfood.py --compiler 'python3.13 pystachy.py' \
  --libuv-prefix /path/to/libuv-1.51.0 \
  --interpreter pypy=/path/to/pypy3 --cpu 0 --samples 5 --rounds 16 \
  --chunks 256 4096 32768 --concurrency 1 8 \
  --profile build/uvio-profiles --json build/uvio-dogfood.json
```

The private libuv build used official tag `v1.51.0`, commit
`5152db2cbfeb5582e9c27c5ea1dba2cd9e10759b`, shared-library Release mode.
It adds no default project dependency; its upstream test suite was not rerun.
