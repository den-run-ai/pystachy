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
