# json_repair throughput

These probes time `repair_json()` from the [json_repair port](../../ports/json_repair/PORT.md).
The alpha.4 and earlier tables compare it with pristine json_repair 0.64.1. Each checks complete outputs outside its timer, and
every variant must print identical witnesses. Startup, compilation, input creation and
validation are not timed. The inputs model features of LLM output; they are not a sample
of production failure frequencies.

## Current upstream comparison

The [14 November refresh](results/refresh-2026-11-14.md) compares pristine upstream
0.64.9, adapted CPython, AOT, JIT and the actual CPython companion extension, with 400
process records and reproducible source/artifact hashes. It measures the unreleased
schema-port stack, including bounded static anchors. AOT is 6.3–8.0× faster than upstream
on mixed/malformed records and 3.0–25.2× on the schema workloads. The adapted CPython
baseline is essential: it is 4.1× faster than native on the long Unicode fixture.
The report includes process variability, startup/build costs and remaining compatibility
gaps; these results do not replace the historical same-compiler rebase comparison below.

## Port re-based on upstream 0.64.9

The port is now [upstream 0.64.9's source with a small patch set](../../ports/json_repair/PORT.md#differences-from-upstream)
in place of the 0.64.8 rewrite. This compares the two ports with each other, both built by
one compiler into AOT executables. It was measured on 12 November 2026 on a shared 4-vCPU
Linux x86-64 VM (Intel Xeon @ 2.10 GHz) with LLVM 18.1.3. Ten pairs of processes, in two
runs of five, ran each workload in alternating order, pinned to one CPU, with two warmup and
seven measured batches; times are the best batch of each port. Instructions are steady-state
callgrind counts: a process with the listed rounds less the same process with none. Witnesses
are identical.
[All batches, counts and source hashes](results/rebase-0.64.9-2026-11-12.json) are retained.

| Workload, time per batch | 0.64.8 rewrite | 0.64.9 re-base | Time | Instructions |
|---|---:|---:|---:|---:|
| Ten mixed trace records (`bench.py 200`) | 11.60 ms | 11.66 ms | 1.01× | 1.01× |
| Small valid objects (`facade.py valid 4000`) | 11.01 ms | 11.19 ms | 1.02× | 1.00× |
| Small malformed objects (`facade.py malformed 400`) | 13.35 ms | 13.51 ms | 1.01× | 1.02× |
| Same, serialized result | 15.43 ms | 15.34 ms | 0.99× | 1.02× |
| Valid 8 KB string (`scaling.py valid 4000 200`) | 2.47 ms | 2.44 ms | 0.99× | 1.00× |
| 2,000 escaped newlines (`scaling.py escaped 2000 10`) | 3.04 ms | 3.00 ms | 0.98× | 1.00× |
| Non-ASCII text (`scaling.py unicode 2000 20`) | 3.12 ms | 3.19 ms | 1.02× | 1.00× |
| Comma-dense text (`scaling.py comma 1000 10`) | 7.62 ms | 7.81 ms | 1.02× | 1.02× |
| Logged repair (`scaling.py logs 1000 50`) | 0.36 ms | 0.37 ms | 1.03× | 1.00× |
| 2,000 raw newlines (`scaling.py newline 2000 20`) | 3.63 ms | 3.65 ms | 1.00× | 1.00× |
| Bare key, 10,000-character value (`scaling.py bare-key 10000 50`) | 0.73 ms | 0.67 ms | 0.93× | 1.01× |

- The re-base executes 0 to 2% more instructions than the rewrite. Times on this shared host
  vary by more than that between runs (single runs of five pairs put one workload or another
  at 1.17× or 0.93×); the instruction counts are the comparison to rely on.
- A program that imports the port and repairs one string starts as the rewrite's does: 0.709
  million instructions against 0.696 million, 1.28 ms against 1.28 ms (the least of 3,000 runs
  each, twice), in an executable of 557 KB against 513 KB. It loads 34 modules where the
  rewrite loaded 24, and compiles in 0.59 s against 0.38 s.
- [Schema-guided repair](../../ports/json_repair/PORT.md#what-schema-support-costs-a-program-without-a-schema),
  added after these measurements, left repair itself as it was: 0.993 to 1.010 times the
  instructions on these workloads (callgrind totals, one run each, not retained). A program
  that passes no schema still carries the schema modules, the validator and `re`: it starts
  in 723,491 instructions against 702,242 and is 1,243 KB against 567 KB.
- Upstream's modules, compiled with only the changes the compiler needs, were about 2 to 8
  times slower than the rewrite on these workloads in informal checks while re-basing (three
  pairs, medians, not retained), started 18% slower and compiled in three times the time.
  What closed the gap:
  - The compiler raises an index error of `s[i]`, `xs[i]` and `xs.pop()` inside a `try`
    statement in the function itself, so upstream's `try: return self.json_str[i]` /
    `except IndexError` no longer goes through the unwinder; that took the ten-record mix from
    about 2.0× to 1.2×.
  - `x in strs` for an `x` that may be `None`, as upstream tests the next character, compares
    strs directly, as a search for a str does; that took the comma-dense workload from 1.07×
    to 1.02× in instructions.
  - The rewrite's string module, comment scanning and root-scan avoidance are kept, and the
    path of an array item or object member is formatted only with a schema.
  - The port imports neither `argparse`, `pathlib` nor `re`
    ([imports](../../ports/json_repair/PORT.md#imports)), and `re`, `json` and `textwrap` do
    less as they load: a set of characters is compiled from its intervals, `json`'s escape
    tables are constants, and `textwrap`'s patterns compile where they are first used.

The tables below predate the re-base and compare the rewrite with pristine upstream.

<a id="release-candidate-measurements"></a>

## alpha.4 measurements

Measured on 2 November 2026 on main `ec442a20`, whose code the v0.1.0-alpha.4 tag shares,
against pristine upstream `ace9b23c`, on a shared 4-vCPU Linux x86-64 VM (Intel Xeon @
2.10 GHz) with LLVM 18.1.3 and CPython 3.13.18.
`tools/json_repair_bench.py` ran five rotating process pairs per workload, with two warmup
and five measured batches each, pinned to one CPU. Values are medians of process medians.
[All 330 processes, commands and source manifests](results/release-candidate-2026-11-02.json)
are retained.
Port changes merged on 4 November moved several of these workloads; a
[9 November research re-measurement](https://github.com/den-run-ai/pystachy/blob/eed2912f204688c0b5244c04c72f480f9c98ef1f/research/status-20261109/json-repair/json-repair-remeasure-2026-11-09.json)
on another host recorded them. This remains historical release evidence; the current
unreleased-stack comparison is linked above.

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
- Upstream 0.64.4 made this linear, so the 187× applies to 0.64.1 through 0.64.3 only.
  In an informal check on 9 November (CPython 3.13.18, `scaling.py`'s `escaped` input,
  best of three, outputs checked), 2,000 escapes took 403 ms with 0.64.3 and 7.0 ms with 0.64.4.
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
