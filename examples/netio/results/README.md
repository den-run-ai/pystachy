# Native readiness dogfood results

The November 7, 2026 run on Linux x86-64 used CPython 3.13.16, PyPy 8.0.1
(Python 3.11.17), mypyc 2.4.1, Cython 3.3.1 and LLVM 18.1.3. The machine reports
AMD EPYC 9V74; measured children were pinned to logical CPU 0 on a shared host.
The native compiler was rebuilt through compiler/runtime IR fixed points
(877,338 / 19,907 lines). Its compiler/runtime/library inputs match main
`6e5544cf`; the networking draft is based on `9c2d9e5`.

## Socket consumer

[`2026-11-07-linux-x86_64.json`](2026-11-07-linux-x86_64.json) records the exact
source hashes, commands' identities, build cost, each measured process and
sample, runtime versions, affinity and host load. There were three rotated
process rounds per case/runtime, each with one first invocation, five untimed
warmups and five timed samples: **15 warmed samples per cell**. Every fragment
was checked against the expected binary payload before accepting a sample.
Socket creation and registrations persist outside these transfer timings.

Speed relative to the CPython stdlib baseline (higher is faster):

| Work per iteration | Pystachy AOT | Pystachy JIT | PyPy stdlib | mypyc consumer | Cython consumer |
|---|---:|---:|---:|---:|---:|
| One 64-byte transfer | 1.43x | 1.34x | 2.18x | 1.04x | 1.06x |
| Sixteen 4 KiB transfers | 1.21x | 1.18x | 0.77x | 0.94x | 1.01x |
| One ready stream among 64, 64 bytes | 0.97x | 0.86x | 2.17x | 1.03x | 1.01x |
| Four 64 KiB transfers | 0.84x | 0.82x | 0.26x | 0.80x | 0.96x |

CPython medians were respectively 2.181, 31.440, 2.270 and 29.602 microseconds
per iteration; Pystachy AOT medians were 1.528, 25.919, 2.346 and 35.403.
The median absolute deviations of the warmed samples were about 0.3–5.3% of
their medians. Small differences near parity are inconclusive on this host.
The larger native transfer takes about 20% longer than CPython in this run;
the measurements do not justify a universal networking speedup claim.

Pystachy compiles both consumer and wrapper. mypyc/Cython compile only the
unchanged consumer and retain CPython's native `socket`/`selectors` modules;
extension loading was checked. Cython uses its default annotation handling.
The mypyc build selects its serial parser because optional psutil cannot inspect
this executor's PID namespace. This changes build setup, not the consumer source.
PyPy uses the Python 3.11 stdlib, so the comparison includes that version difference.

The separate CPython ctypes bridge achieved only 0.085x, 0.104x, 0.021x and
0.268x of the stdlib speed. It is a correctness twin, not the performance
baseline. A separate sparse-readiness cProfile run recorded 736,662 calls for
the bridge versus 30,631 for stdlib; list conversion/range checking in `ffi.call`
and `_check`, plus `inspect.bind`, dominate that wrapper profile. These Python
profiles do not identify native allocation cost. Native `strace` was explicitly
unavailable because ptrace was denied; the availability failure is retained.

The separate [native Callgrind profile](2026-11-07-native-profile.json) uses
Valgrind 3.22.0 with collection restricted to `f.bench_workload$transfer` and its
callees. Its [small-message](2026-11-07-pair_64.callgrind) and
[bulk](2026-11-07-bulk_64k.callgrind) records preserve the original instruction
counts. Exact outputs and unchanged source hashes passed in both runs.

For 360 received 64 KiB payloads, the profile records 360 native receive-buffer
allocations, 360 `pys_bytes_at` managed copies and 360 native frees. The managed
copy path accounts for 84.98% of **inclusive guest instructions**, equality
checking 11.04%, and the GC slow path 2.81%; inclusive categories overlap.
This makes the extra receive copy a concrete optimization candidate. Valgrind's
REP-move expansion and virtual CPU dispatch mean these percentages are **not
native wall-time percentages** and do not prove the cause of the 20% timing gap.
No hardware cycle/cache or allocation-byte counters were collected. The JSON
preserves commands, tool/package identities, binary hashes and function counts.
Full-payload slices were already efficient in these profiles: 720 bulk
`pys_str_slice` calls made no child allocation or copy calls. For small messages,
per-transfer list allocation and identity bookkeeping are visible additional
targets. A receive-into or ownership-preserving buffer path is the next measured
design candidate; this prototype does not implement that interface.

Bridge build took 0.122 s. AOT consumer/runtime preparation took 7.097 s;
mypyc/Cython consumer extension builds took 3.660/3.599 s, with their different
compiled scopes as described above. JIT process durations include compilation
with a private runtime cache already populated by AOT preparation. The steady
transfer columns exclude those startup/build costs.

Reproduction, with optional runtimes already installed:

```sh
python3.13 examples/netio/benchmark.py --compiler ./pystachy --cpu 0 \
  --rounds 3 --warmups 5 --samples 5 --pypy /path/to/pypy3 \
  --extension-python /path/to/cpython-comparison-venv/bin/python --profile \
  --json build/netio-benchmark.json --pyperf-json build/netio-pyperf.json
```

[`2026-11-07-pyperf.json`](2026-11-07-pyperf.json) is a pyperf 2.10-compatible
export of these validated samples, normalized per iteration. It was not collected
through pyperf's adaptive calibration/worker controller. These are local socket
pairs, not TCP/WAN bandwidth measurements or an upstream pyperformance result.

## Real compiler collection

[`2026-11-07-compiler-dogfood.json`](2026-11-07-compiler-dogfood.json) preserves
exact IR/stdout, diagnostic/stderr and exit-status witnesses for three existing
corpus inputs. All six collectors passed: CPython oracle/bridge, native JIT/AOT
and both GC-stress modes. The independent reference is the CPython-hosted
compiler; the workers use the same native compiler in every collector mode.

This exercise exposed [#1154](https://github.com/den-run-ai/pystachy/issues/1154):
the JIT launcher overwrites inherited descriptors 8 and 9, silently reading ELF
or bitcode bytes instead of an application pipe. The launcher now explicitly
duplicates its streams to FD64+ and records those mappings. The underlying
driver bug remains open; this is a prototype integration workaround.

The compiler collection run is correctness evidence, not a performance ranking.
Its first JIT call also populated the private runtime cache; the later GC JIT
call reused it. The collector buffers and hex-encodes whole bounded streams,
and its small fixtures do not model a production scheduler or full self-compile.
[`2026-11-07-native-smoke.json`](2026-11-07-native-smoke.json) separately records
the four new socket cases in JIT/AOT and both GC modes; its tiny-input times are
correctness-only and must not be used as benchmark results.
