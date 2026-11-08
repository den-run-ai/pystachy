# CPython FFI wrapper costs

The CPython compatibility twin binds complete positional calls directly and
precomputes parameter metadata when an `@extern` declaration is created.
Keywords, omitted defaults and non-positional signatures keep `inspect` binding.
Integer-list marshalling applies its known signed-64-bit range check directly,
with the same bounds and error as generic conversion. Aliased lists still share
one temporary C array, and writes are copied back once per distinct list.

## Socket workload comparison

The November 7, 2026 comparison uses the unchanged binary-validating consumer
and native bridge from networking draft
[`b9ab8d9d`](https://github.com/den-run-ai/pystachy/tree/b9ab8d9d3065b94c85952c79bada1de43a021c49/examples/netio).
Both variants run under CPython 3.13.16; only `tools/rt_cpython/ffi.py` changes.
The baseline twin is identical to main `6e5544cf`.

Median microseconds per transfer iteration, lower is faster:

| Work per iteration | Baseline twin | Revised twin | Speedup |
|---|---:|---:|---:|
| One 64-byte transfer | 25.860 | 15.651 | 1.65x |
| Sixteen 4 KiB transfers | 311.399 | 193.395 | 1.61x |
| One ready stream among 64, 64 bytes | 112.955 | 64.980 | 1.74x |
| Four 64 KiB transfers | 111.303 | 81.190 | 1.37x |

The [raw report](results/2026-11-07-linux-x86_64.json) preserves every sample,
source and executable hashes, loaded-library identity, hardware, affinity and
profile summaries. Four alternating process rounds each contain a first call,
three untimed warmups and five timed samples: **20 warmed samples per cell**.
Every received fragment is checked before accepting a timing. Socket creation,
registration and process startup are outside transfer timings; complete process
durations are recorded separately. These are advisory measurements on a shared
Linux x86-64 host (AMD EPYC 9V74), pinned to logical CPU 0. Median absolute
deviations were 1.4–3.1% for baseline and 1.4–4.5% for revised samples.

Separate cProfile runs of the sparse workload record 736,216 versus 538,457
total calls. `Signature.bind` and `BoundArguments.apply_defaults` fall from
12,788 calls to zero. The list values still receive range checks; the revised
conversion avoids repeatedly dispatching on the same declared integer type.
Profiling runs are excluded from timing samples.

The measured scope is the **CPython ctypes compatibility wrapper**. This is
not a comparison against CPython's stdlib sockets or a native Pystachy speedup;
the native receive-buffer copy requires separate work.

## Reproduce

Use a baseline checkout at `6e5544cf` and a networking checkout at `b9ab8d9d`,
plus CPython 3.13.16 and a C compiler. From the revised checkout:

```sh
python3.13 bench/ffi_twin/compare.py \
  --baseline ../pystachy-baseline \
  --netio-root ../pystachy-netio-dogfood \
  --cpu 0 --rounds 4 --warmups 3 --samples 5 \
  --json build/ffi-twin-comparison.json
```

Choose a CPU in the available affinity mask. The controller reuses the existing
netio workload, bridge builder and sample validator, checks the actually imported
twin, and rejects changes to consumed source bytes during a run. It requires no
optional comparison runtime, Pystachy build or native runtime-cache preparation.

Twelve real-C unit controls cover positional/keyword/default binding, arity
errors before conversion, positional-only and keyword-only parameters, integer
boundaries, binary and NULL handling, writes, aliasing and offset checks. A
deterministic operation-count control rejects unnecessary signature binding and
fails with the baseline twin. All 24 existing `tests/ffi/c_*.py` programs also
match their committed CPython recordings. These checks validate the changed
twin; full native compiler/embedding verification remains a separate CI gate.
