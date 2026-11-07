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
  and the accumulator has historical PyPy and memory costs recorded in
  [Historical evidence](#historical-evidence).
  CPython users should keep upstream.
- Each JIT process first compiles the package, about 1.2 s here. An AOT executable starts
  and repairs the ten records in 4–5 ms, where importing either version under CPython takes
  46–57 ms. An AOT build of `facade.py` or `scaling.py` took about 7 s.
- Whole-process RSS for CPython and AOT stayed at the runner's launch floor (about 47 MiB),
  so these runs establish no memory difference.
- The 645-case parity replay matches pristine upstream at this build on CPython and in AOT
  and JIT, normally and with collection at every allocation.

To repeat the campaign, build the probes as in [Reproduce](#reproduce) and run
`tools/json_repair_bench.py` with a variants file like the one in
[Paired timings](#paired-timings). The evidence file lists every
command, argument and source hash. Its `callgrind_counts` also compare whole-process AOT
instruction counts of the nine workloads with those of `c3aaa068`, less a stack-bounds
fallback that only Valgrind triggers.

<a id="earlier-prototype-measurement"></a>
<a id="earlier-measurement"></a>

## Historical evidence

The first prototype measurement, of the ten-record mix at `ce6aee5e`, is on
[this page as of alpha.4](https://github.com/den-run-ai/pystachy/blob/9c8bc74648aa7c7e6a1b9d8f9dbbfeb1f2908ad3/bench/json_repair/README.md#earlier-prototype-measurement);
[its samples and identities](results/prototype.json) are retained. It used CPython 3.13.16
on another host, so it is not comparable with the table above.

The [typing/scaling report](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/bench/json_repair/PROFILING.md)
and [28 October accumulator report](https://github.com/den-run-ai/pystachy/blob/a2cb8a3638d715577a7ab1cd1e4a0d6b01b6cdf2/bench/json_repair/ACCUMULATOR.md)
are preserved in Git history. The latter measured a **65% PyPy mixed-workload slowdown**
after 20 warmup batches, and a **40% increase in CPython `tracemalloc` peak bytes** at
8,000 escaped fragments (35,083 → 49,234 bytes). Retained traced bytes were unchanged;
this is not a native retained-heap measurement. These historical tradeoffs were not
remeasured by the alpha.4 campaign. Raw evidence remains in
[typing/scaling](results/typing-and-scaling.json),
[incremental escape state](results/incremental-escape-state.json),
[native escape state](results/native-incremental-escape-state.json) and
[bounded accumulator](results/bounded-accumulator.json).

## Reproduce

With the pinned upstream checkout described in the
[parity instructions](../../tests/upstream/json_repair/README.md):

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/bench.py -o /tmp/json_repair_bench
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 bench/json_repair/bench.py 0
PYTHONPATH=ports python3.13 bench/json_repair/bench.py 0
/tmp/json_repair_bench 0
```

Compare the `outputs` and `per_round` lines exactly before timing. A mixed run
with 2,000 rounds must report `records 20000`, `per_round 616` and `checksum 1232000`.
`scaling.py` covers larger valid, malformed, Unicode, logging and escaped strings:

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/scaling.py -o /tmp/json_repair_scaling
/tmp/json_repair_scaling escaped 4000 5 5 6
/tmp/json_repair_scaling bare-key 10000 100 3 1
python3.13 -m unittest discover -s tools -p 'test_json_repair_accumulator.py'
```

The `bare-key` case has one unquoted object key and a long valid string value.
It isolates the cost of scanning the initial container after validation has
already rejected the key.

The [deterministic accumulator checks](../../tools/test_json_repair_accumulator.py)
exercise N/2N/4N, Unicode and chunk boundaries, with negative controls for unbounded
copying and scalar scanning. They count logical copied code points and parser calls,
not native allocations or GC traffic; they do not prove every parser path is linear.
The [port guide](../../ports/json_repair/PORT.md#adaptations) describes incremental
escape state, bounded chunks and ordinary-text spans.

### Paired timings

Build the mixed and scaling probes separately in each checkout, using identical
probe sources and, for port-only comparisons, the same compiler. Give the binaries
distinct paths as below. Each probe accepts measured batches and discarded warmup
batches as its final arguments; the runner appends those itself.
Save a config like this to `/tmp/variants.json`, replacing the example paths:

```json
{
  "variants": [
    {"name": "before-aot", "source": "/path/to/baseline", "commands": {
      "scaling": ["/tmp/before-scaling"], "mixed": ["/tmp/before-mixed"]}},
    {"name": "after-aot", "source": "/path/to/candidate", "commands": {
      "scaling": ["/tmp/after-scaling"], "mixed": ["/tmp/after-mixed"]}}
  ],
  "cases": [
    {"name": "escaped-N", "probe": "scaling", "args": ["escaped", "1000", "5"]},
    {"name": "escaped-2N", "probe": "scaling", "args": ["escaped", "2000", "5"]},
    {"name": "escaped-4N", "probe": "scaling", "args": ["escaped", "4000", "5"]},
    {"name": "mixed", "probe": "mixed", "args": ["200"]}
  ]
}
```

Choose an allowed CPU from `os.sched_getaffinity(0)` for `--cpu` (replace `0` below).
Disable GC stress, stop other local builds/tests and leave sources/binaries unchanged:

```sh
python3.13 tools/json_repair_bench.py /tmp/variants.json --cpu 0 \
  --pairs 5 --batches 5 --warmups 6 --output /tmp/json-repair-results.json
```

The runner rotates process order, requires identical complete-output witnesses and
retains raw batches, commands and source/executable hashes. It reports medians of
process medians and rejects changed sources, failed processes or invalid timings.
Each `source` must be the checkout supplying the consumed sources. For CPython/PyPy,
use absolute script paths and set `PYTHONPATH` to the parser path in the variant's `env`.
Inherited `PYSTACHY_*` and Python import overrides are cleared, so required JIT LLVM/cache
settings also belong there.
Pinning does not isolate a shared host. Keep memory/instruction profiling separate
from ordinary timings; see the historical reports for attribution commands.

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

## Installed CPython API campaign

`tools/json_repair_api_bench.py` measures the public `pystachy_json_repair` wheel
in the Python process using it, alongside pristine upstream 0.64.1 and the adapted
port under the same CPython interpreter. This complements the core/JIT/AOT probes
above: it includes native string transport, CPython decoding of object/log payloads,
and the valid-JSON CPython fast path.

The [2026-11-06 installed-wheel evaluation](results/installed-api-2026-11-06.md)
records calibrated timings, process-to-process ranges, startup, sustained-request
RSS, and the validated CPython 3.12/3.13 wheel. It retains both the corrected raw
campaign and the initial short-sample run that exposed measurement limitations.

Install the wheel into a dedicated environment using the
[companion build instructions](../../docs/packages.md#install-native-json-repair-into-cpython),
then invoke that environment's Python. Replace the paths and CPU below:

```sh
/path/to/venv/bin/python tools/json_repair_api_bench.py \
  --upstream /path/to/json_repair_upstream --adapted /path/to/pystachy \
  --cpu 0 --check-only --output /tmp/json-repair-api-check.json
/path/to/venv/bin/python tools/json_repair_api_bench.py \
  --upstream /path/to/json_repair_upstream --adapted /path/to/pystachy \
  --cpu 0 --pairs 3 --batches 3 --warmups 2 --rounds 100 \
  --min-sample-seconds 0.2 --group-sizes 1 32 --memory-rounds 500 \
  --output /tmp/json-repair-api.json
python3.13 -m unittest discover -s tools -p test_json_repair_api_bench.py
```

Every backend uses a fresh isolated (`-I`) worker. The runner verifies all pinned
upstream source hashes, requires the companion to load an actual extension from
an installed distribution, and records its wrapper/native hashes, distribution
version, wheel metadata, and installer provenance when present. It refuses to
proceed if any complete tagged output differs. The tags distinguish bool/int,
int/float, signed zero, tuple/list, dictionary order and exact string code points;
strict-error messages and Unicode/wide-integer boundaries are checked too. These
checks include both default and forced repair. The maintained upstream corpus
remains the larger compatibility gate; these benchmark witnesses do not replace it.

The campaign rotates backend order and pins all children to the selected CPU. It
uses eight constructed record shapes with tool calls, verifier results, simulation
state, search candidates, code, nested data and a longer answer. The controls are
all valid, all malformed, and an explicit **80% valid / 20% malformed** mixture
containing every shape. This is a reproducible scenario, not measured production
failure frequency. Three paths are measured: `repair_json(ensure_ascii=False)`
text, `loads()` objects, and `loads(logging=True)` objects/logs. The public
`repair_json(return_objects=True)` and `repair_json(logging=True)` facades also
receive untimed parity checks.

Each steady worker starts with `--rounds` and calibrates toward
`--min-sample-seconds` (default 0.2 seconds) before warmups and measured batches.
Calibration is limited to eight checked probes and at most the larger of the
initial count and one million rounds. It never reduces the initial count.
The report retains every probe, the stop reason, the actual rounds, and the
`requests_per_sample` denominator used for that worker's timings. This avoids
using millisecond samples for fast inputs while giving slower inputs independent
counts. Calibration time is excluded from measured samples. The target is an aim,
not a performance gate; warmup and host load can still change sample duration.
Use `--min-sample-seconds 0` for fixed-round reproduction. Startup and sustained
memory request counts are not calibrated.

| Evidence | Included | Interpretation |
|---|---|---|
| Steady API calls | Public Python/native conversion, result lists, loop and length-checksum overhead | Median of process medians per request using each worker's calibrated denominator; excludes calibration, startup, input construction and complete-result validation. |
| Group sizes 1 and 32 | Groups of ordinary Python API calls, capped by the workload length | There is no native bulk API; this measures request-loop grouping, not one native call for a batch. |
| Fresh-process startup | Python worker launch through exit, common harness setup and report output | Backend import and first malformed request are also timed separately; the process wall time is not a bare application import measurement. |
| Sustained memory | Separate fresh workers; Linux `/proc/self/status` `VmRSS` and `VmHWM` after warmup and each block | Counters describe the current address space since exec. Bounded retention: expected and latest workload results plus the current group. CPython GC runs before samples; native GC is not forced. |

Every timed worker verifies its complete final outputs against its initial outputs
and the pristine preflight witness; a length checksum covers all calls. Memory is
measured separately after ordinary timings. Its RSS series includes interpreter,
native heap and allocator retention; it is not a native live-heap counter or proof
that no leaks exist. Every snapshot names the source and peak scope. Linux uses
`VmRSS`/`VmHWM` in KiB converted to bytes, and fails on missing or invalid counters.
It does not use `getrusage().ru_maxrss`, which can preserve the launching parent's
high-water mark across exec. The non-Linux `getrusage` fallback is explicitly
labeled, reports no current RSS, and may include inherited pre-exec usage.
Compilation and wheel installation are outside all timers.
No performance threshold is enforced. Stop other local builds/timing jobs, retain
the raw JSON, and report shared-host noise; CPU affinity alone does not isolate a VM.
The runner rejects changes to consumed sources, Python, the harness or installed
wrapper/native binaries during the campaign.
