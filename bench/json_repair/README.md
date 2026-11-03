# json_repair throughput

These probes time `repair_json()` from the [adapted port](../../ports/json_repair/PORT.md)
against pristine json_repair 0.64.1. Each checks complete outputs outside its timer, and
every variant must print identical witnesses. Startup, compilation, input creation and
validation are not timed. The inputs model features of LLM output; they are not a sample
of production failure frequencies.

<a id="release-candidate-measurements"></a>

## alpha.4 measurements

Measured on 2 November 2026 on main `ec442a20`, whose code the v0.1.0-alpha.4 tag shares,
against pristine upstream `ace9b23c`, on a shared 4-vCPU Linux x86-64 VM (Intel Xeon @
2.10 GHz) with LLVM 18.1.3 and CPython 3.13.18.
`tools/json_repair_bench.py` ran five rotating process pairs per workload, with two warmup
and five measured batches each, pinned to one CPU. Values are medians of process medians.
[All 330 processes, commands and source manifests](results/release-candidate-2026-11-02.json)
are retained.

| Workload, time per repair | Upstream, CPython | Port, CPython | Port, AOT | Port, JIT | AOT vs upstream |
|---|---:|---:|---:|---:|---:|
| Ten mixed trace records (`bench.py 200`) | 40.4 µs | 34.0 µs | 7.6 µs | 9.1 µs | 5.3× |
| Small valid objects (`facade.py valid 4000`) | 1.9 µs | 1.9 µs | 0.7 µs | 1.0 µs | 2.7× |
| Small malformed objects (`facade.py malformed 400`) | 63.4 µs | 59.4 µs | 10.9 µs | 12.5 µs | 5.8× |
| Same, serialized result | 76.0 µs | 62.7 µs | 12.4 µs | 13.6 µs | 6.1× |
| Valid 8 KB string (`scaling.py valid 4000`) | 13.3 µs | 14.2 µs | 9.5 µs | 9.8 µs | 1.4× |
| 2,000 escaped newlines (`scaling.py escaped 2000`) | 416 ms | 9.4 ms | 2.2 ms | 2.4 ms | 187× |
| Non-ASCII text (`scaling.py unicode 2000`) | 454 µs | 464 µs | 273 µs | 292 µs | 1.7× |
| Comma-dense text (`scaling.py comma 1000`) | 4.9 ms | 6.5 ms | 1.3 ms | 1.4 ms | 3.8× |
| Logged repair (`scaling.py logs 1000`) | 170 µs | 169 µs | 50 µs | 48 µs | 3.4× |

A size sweep with the same method (upstream, port on CPython and AOT) shows linear
scaling at both ends; values are AOT's speedup over upstream:

| Repeated units | 500 | 1,000 | 2,000 | 4,000 | 8,000 |
|---|---:|---:|---:|---:|---:|
| Non-ASCII (`unicode`) | 1.39× | 1.71× | 1.54× | 1.72× | 1.63× |
| Comma-dense (`comma`) | 3.58× | 3.72× | 3.91× | 3.40× | 4.08× |

- Small malformed records gain about 6×. Valid JSON takes the decoder fast path and gains
  less: 2.7× for small objects, 1.4× for one long string.
- Upstream rebuilds brace state over the whole accumulated string after every escape, so
  its cost grows quadratically with escaped newlines. The port's incremental state alone
  is 44× faster on CPython at 2,000 escapes; AOT adds about 4×.
- Non-ASCII malformed text gains 1.4–1.7×. On an earlier alpha.4 candidate, `c3aaa068`, it
  gained nothing (0.91–1.01×): 41% of its instructions built the `JSONDecodeError` that the
  facade's first `json.loads()` attempt raises and discards, mostly `repr()` of the whole
  document. [#1031](https://github.com/den-run-ai/pystachy/pull/1031) stops formatting
  arguments that an exception's `__init__` replaces, and steps UTF-8 faster when converting
  the byte offset to a character position; alpha.4 executes 42% fewer instructions on this
  workload than that candidate. `JSONDecodeError.__init__`'s line and column arithmetic on
  non-ASCII text remains.
- The adapted port is 1.3–1.4× slower than upstream under CPython on comma-dense text,
  and its accumulator has the PyPy and memory costs in the [accumulator report](ACCUMULATOR.md).
  CPython users should keep upstream.
- Each JIT process first compiles the package, about 1.2 s here. An AOT executable starts
  and repairs the ten records in 4–5 ms, where importing either version under CPython takes
  46–57 ms. An AOT build of `facade.py` or `scaling.py` took about 7 s.
- Whole-process RSS for CPython and AOT stayed at the runner's launch floor (about 47 MiB),
  so these runs establish no memory difference.
- The 645-case parity replay matches pristine upstream at this build on CPython and in AOT
  and JIT, normally and with collection at every allocation.

To repeat the campaign, build the probes as in [Reproduce](#reproduce) and run
`tools/json_repair_bench.py` with a variants file like the one in the
[accumulator report](ACCUMULATOR.md#paired-timings). The evidence file lists every
command, argument and source hash. Its `callgrind_counts` also compare whole-process AOT
instruction counts of the nine workloads with those of `c3aaa068`, less a stack-bounds
fallback that only Valgrind triggers.

<a id="earlier-prototype-measurement"></a>

## Earlier measurement

The first prototype measurement, of the ten-record mix at `ce6aee5e`, is on
[this page as of alpha.4](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/bench/json_repair/README.md#earlier-prototype-measurement);
[its samples and identities](results/prototype.json) are retained. It used CPython 3.13.16
on another host, so it is not comparable with the table above.

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
