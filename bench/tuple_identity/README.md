# Numeric tuple identity costs

`score.py` constructs two-item reward batches from fresh arithmetic. `typed`
consumes only their scalar payloads; `observed` passes items through Any; `copy`
slices a fresh tuple before observing either source item. All three modes have
the same checksum and remain executable with CPython.

```sh
python3.13 bench/tuple_identity/score.py typed 20000 3
./pystachy build bench/tuple_identity/score.py -o /tmp/tuple-score
/tmp/tuple-score typed 20000 3
/tmp/tuple-score observed 20000 3
/tmp/tuple-score copy 20000 3
```

Each line contains the checksum and in-process duration in seconds. Compare
checksums before timing; interleave parent/candidate binaries on the same idle
core. Report whole-process JIT startup and AOT compilation separately. To compare
ordinary programs, remove only the first pragma and the `Any` annotation/import:
this requires a distinct source and must be reported as such.

Use `PYSTACHY_CFLAGS=-DPYSTACHY_PROFILE_DATA` and private `PYSTACHY_CACHE`
directories for deterministic AOT allocation requests and requested bytes.
Instrumented timings are not ordinary performance results; counters exclude
foreign allocation and are not RSS or live retention. Expect an eight-byte header
increase for every runtime-length tuple. Identity-tracking numeric tuples also
allocate a companion array; copies may materialize every fresh item box before
sharing, even without an Any observation. `make listprobe` checks ownership,
scan kinds, fresh-copy identity and positive/negative collection controls.

## Allocation sample

On 2026-11-14, x86-64 Linux, LLVM 18 and CPython 3.13.16, AOT builds at the
default optimization tier 2 compared parent `7e96403e` with published candidate
`2b00207e`. The tested candidate `34032b0e` has the same tree as that published
commit. The parent native compiler came from the identical source tree
`88c89982`; the candidate used the hosted compiler. Each build used the profiling flag above and a private
runtime cache. One repetition of 20,000 batches returned `249830.375` in every
mode, matching CPython. These are total requests, including startup and output:

| Source | Mode | Allocations, parent → candidate | Requested bytes, parent → candidate |
|---|---|---:|---:|
| Dynamic Any | typed | 20,010 → 40,010 | 480,372 → 1,120,371 |
| Dynamic Any | observed | 60,010 → 80,010 | 1,080,375 → 1,720,374 |
| Dynamic Any | copy | 40,010 → 120,010 | 800,370 → 2,520,370 |
| Ordinary | typed | 20,007 → 20,007 | 480,328 → 640,326 |
| Ordinary | observed | 20,007 → 20,007 | 480,331 → 640,330 |
| Ordinary | copy | 40,007 → 40,007 | 800,327 → 1,120,326 |

The ordinary variant removes the pragma and `Any` import and changes `number`'s
parameter to `float`. Its extra bytes correspond to the eight-byte tuple header;
it makes no additional allocation requests. The dynamic typed mode adds one
companion allocation per tuple, while the copy mode also materializes both fresh
numeric items before sharing their identities. Thus preserving raw numeric
storage does not make identity preservation allocation-free. Startup paths and
printed output account for small byte differences beyond the tuple costs.

[Raw counters and provenance](results/2026-11-14-allocations.json) include zero-count
controls. This shared-host run supports allocation comparisons only; it makes no
wall-time performance claim.
