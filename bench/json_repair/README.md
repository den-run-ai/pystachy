# json_repair throughput

These probes time `repair_json()` from the [adapted port](../../ports/json_repair/PORT.md)
against pristine json_repair 0.64.1. Each checks complete outputs outside its timer, and
every variant must print identical witnesses. Startup, compilation, input creation and
validation are not timed. The inputs model features of LLM output; they are not a sample
of production failure frequencies.

## Release-candidate measurements

Measured on 2 November 2026 at main `c3aaa068`, against pristine upstream `ace9b23c`, on a
shared 4-vCPU Linux x86-64 VM (Intel Xeon @ 2.10 GHz) with LLVM 18.1.3 and CPython 3.13.18.
`tools/json_repair_bench.py` ran five rotating process pairs per workload, with two warmup
and five measured batches each, pinned to one CPU. Values are medians of process medians.
[All 330 processes, commands and source manifests](results/release-candidate-2026-11-02.json)
are retained.

| Workload, time per repair | Upstream, CPython | Port, CPython | Port, AOT | Port, JIT | AOT vs upstream |
|---|---:|---:|---:|---:|---:|
| Ten mixed trace records (`bench.py 200`) | 40.8 µs | 35.1 µs | 7.9 µs | 9.5 µs | 5.2× |
| Small valid objects (`facade.py valid 4000`) | 2.0 µs | 1.9 µs | 0.8 µs | 1.0 µs | 2.6× |
| Small malformed objects (`facade.py malformed 400`) | 67.5 µs | 61.6 µs | 12.7 µs | 13.4 µs | 5.3× |
| Same, serialized result | 70.2 µs | 64.9 µs | 12.9 µs | 14.6 µs | 5.4× |
| Valid 8 KB string (`scaling.py valid 4000`) | 13.1 µs | 13.1 µs | 9.6 µs | 9.7 µs | 1.4× |
| 2,000 escaped newlines (`scaling.py escaped 2000`) | 427 ms | 9.4 ms | 2.3 ms | 2.5 ms | 183× |
| Non-ASCII text (`scaling.py unicode 2000`) | 451 µs | 451 µs | 469 µs | 529 µs | 0.96× |
| Comma-dense text (`scaling.py comma 1000`) | 4.9 ms | 6.5 ms | 1.4 ms | 1.5 ms | 3.5× |
| Logged repair (`scaling.py logs 1000`) | 171 µs | 175 µs | 59 µs | 54 µs | 2.9× |

A size sweep with the same method (upstream, port on CPython and AOT) shows linear
scaling at both ends; values are AOT's speedup over upstream:

| Repeated units | 500 | 1,000 | 2,000 | 4,000 | 8,000 |
|---|---:|---:|---:|---:|---:|
| Non-ASCII (`unicode`) | 1.01× | 0.94× | 0.96× | 0.97× | 0.91× |
| Comma-dense (`comma`) | 3.68× | 3.65× | 3.74× | 3.61× | 3.69× |

- Small malformed records gain about 5×. Valid JSON takes the decoder fast path and gains
  less: 2.6× for small objects, 1.4× for one long string.
- Upstream rebuilds brace state over the whole accumulated string after every escape, so
  its cost grows quadratically with escaped newlines. The port's incremental state alone
  is 45× faster on CPython at 2,000 escapes; AOT adds about 4×.
- Non-ASCII text gains nothing. With the same malformed shape, AOT's advantage falls from
  1.7–1.8× for ASCII to 1.1–1.3× for two-byte characters and 0.94–0.96× with four-byte
  characters. In a Callgrind profile of the non-ASCII case, 41% of instructions build the
  `JSONDecodeError` that the facade's first `json.loads()` attempt raises and discards:
  constructing an exception formats `repr()` of all its arguments, here the whole document
  (28%), and the decoder converts the byte offset to a code-point position (13%). That
  `repr()` costs 87 µs to 1.1 ms for 2,000 to 32,000 non-ASCII code points, where CPython's
  construction takes 0.4 µs; alpha.3 behaves the same.
- The adapted port is 1.3–1.4× slower than upstream under CPython on comma-dense text,
  and its accumulator has the PyPy and memory costs in the [accumulator report](ACCUMULATOR.md).
  CPython users should keep upstream.
- Each JIT process first compiles the package, about 1.2 s here. An AOT executable starts
  and repairs the ten records in 2 ms, where importing either version under CPython takes
  43–59 ms. An AOT build of `bench.py` took 7.3 s.
- Whole-process RSS for CPython and AOT stayed at the runner's launch floor (about 47 MiB),
  so these runs establish no memory difference.

To repeat the campaign, build the probes as in [Reproduce](#reproduce) and run
`tools/json_repair_bench.py` with a variants file like the one in the
[accumulator report](ACCUMULATOR.md#paired-timings). The evidence file lists every
command, argument and source hash.

## Earlier prototype measurement

At source `ce6aee5e1dc1a3c3d8e85e833746e642e2839c9a`, on a shared Linux x86-64
AMD EPYC 9V74 host, CPython 3.13.16 and LLVM 18.1.3, this ten-record workload
(three valid records and seven malformed inputs) measured:

| Variant | Median seconds / 20,000 records | Relative to native AOT |
|---|---:|---:|
| Pristine json_repair 0.64.1 / CPython | 0.748 | 2.33× |
| Adapted port / CPython | 0.690 | 2.15× |
| Adapted port / Pystachy AOT | 0.321 | 1.00× |

Seven samples per variant, interleaved in rotating order and pinned to CPU 0.
[All samples and identities](results/prototype.json) are retained. The timed loop
calls `repair_json(return_objects=True)` and a small result-weight function.
Serialization, interpreter startup, JIT startup and AOT compilation are outside
the timer. Output witnesses match exactly across all three variants; the checksum
is 1,232,000 for 2,000 rounds. Results are advisory for this small repeated mix;
no memory, production throughput or general library speed claim is established.

## Reproduce

With the pinned upstream checkout described in the
[parity instructions](../../tests/upstream/json_repair/README.md):

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/bench.py -o /tmp/json_repair_bench
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 bench/json_repair/bench.py 0
PYTHONPATH=ports python3.13 bench/json_repair/bench.py 0
/tmp/json_repair_bench 0
```

Compare the `outputs` and `per_round` lines exactly before timing. Choose an
allowed CPU from `os.sched_getaffinity(0)`. For each of seven rounds, run each
variant once, rotating which runs first:

```sh
PYTHONPATH=/tmp/json_repair_upstream/src taskset -c 0 python3.13 bench/json_repair/bench.py 2000
PYTHONPATH=ports taskset -c 0 python3.13 bench/json_repair/bench.py 2000
taskset -c 0 /tmp/json_repair_bench 2000
```

Use the median `seconds` for each variant. Each run must retain identical output
witnesses, `records 20000`, `per_round 616` and `checksum 1232000`. Ensure GC stress
is disabled and other builds/tests are not running before measuring. CPU pinning
does not isolate a shared host.

The [typing and scaling report](PROFILING.md) adds larger valid, malformed,
Unicode, logging and escaped-code-string workloads. It separates native code-size
changes from inconclusive timing differences and identifies quadratic rescanning.

## Separate decoder, repair and serialization controls

`codec.py` measures dynamic `json.loads()` and predecoded `json.dumps()` without
importing the repair package. `facade.py` separates valid and malformed inputs,
with either object or serialized returns. Both check complete outputs before and
after every batch; they work with `tools/json_repair_bench.py`'s interleaved runner.
Examples (arguments end in measured batches and warmup batches):

```sh
./pystachy build bench/json_repair/codec.py -o /tmp/json_codec
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/facade.py -o /tmp/json_facade
/tmp/json_codec loads 32 300 5 6
/tmp/json_codec dumps 32 300 5 6
/tmp/json_facade valid 500 5 6
/tmp/json_facade malformed 200 5 6
/tmp/json_facade serialized-valid 500 5 6
/tmp/json_facade serialized-malformed 200 5 6
```

Use zero rounds for process-start observations, which still include imports,
fixture creation and validation. The runner's whole-process peak RSS includes
those costs and is not retained heap. Its 10 ms child polling limits the resolution
of short process wall-time measurements. Compare the same source under CPython
explicitly; these controls do not establish performance against pristine upstream,
PyPy or GraalPy.
