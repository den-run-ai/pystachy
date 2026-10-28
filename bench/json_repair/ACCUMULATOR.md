# Bounded string-accumulator probes

The parser keeps completed immutable chunks and a tail of at most 64 code
points. Appending or replacing a trailing escape copies only the tail. Cached
length, final character and regex-class whitespace state serve intermediate
reads; finalization joins once. This bounds the accumulator's repeated-prefix
work, rather than asserting that every parser path is linear.

`tools/test_json_repair_accumulator.py` instruments the actual parser under
CPython and counts lengths of concat/slice results and explicit snapshots.
N/2N/4N, Unicode and regex-tail cases have bounded copying; negative controls
restore an unbounded tail or materialize after every append and fail those
bounds while preserving the complete repaired result. These are **logical
copied-code-point counts**, not native allocation traffic or GC statistics.
The separate differential fixture covers 63/64/65-code-point boundaries,
snapshots, surrogates, structural escapes, regex whitespace, strict/streaming
modes and trailing removal/rstrip. The existing 645-case replay remains required;
its known signed-64-bit mismatch is retained without a checker waiver.

## Integrated measurements — 28 October 2026 (UTC)

The repeated-prefix bottleneck is removed in the measured native consumer, but
this remains a **prototype**: the longer-warmed PyPy mixed workload regresses
**65%**, and CPython's traced peak memory at 8,000 escapes increases **40%**.
Keep the draft status until those tradeoffs are reviewed. These measurements do
not establish a general engine ranking or linearity of the entire parser.

The baseline integrates main `daeb6e0d` with the unmerged #847 → #848 → #852
port stack: local `8b2e46f6`, published
[`25bd029a`](https://github.com/den-run-ai/pystachy/commit/25bd029a691062ed874133d3bf0b7c1dd9b6dae4),
tree `51e7d2b8e90dcf63a71228afea3ad6c1a7d0d316`.
The measured final code is local `288e6d5c`, published
[`d81f36b9`](https://github.com/den-run-ai/pystachy/commit/d81f36b950cf048b39ec00aa381e7d55fdc93d2b),
tree `ca9272e4746e26615e8e9a424799426b098005df`.
Compiler/runtime sources are identical; the candidate changes only the port and
its tests/probes. Both variants consume identical benchmark source files. The
final snapshot returns the immutable tail directly when no full chunk exists.
The initial always-join candidate (`ad9b0ce3`) is retained as separate evidence,
not substituted for the final measurements.

[Curated raw evidence](results/bounded-accumulator.json) retains all 568 timing
processes and 6,438 warmup/measured batches, source and executable hashes,
commands, witnesses and separate memory/profile samples. It deduplicates repeated
manifests and output witnesses; no outlier was removed. The host was shared Linux
x86-64, AMD EPYC 9V74, pinned to CPU 0, using LLVM 18.1.3, CPython 3.13.16 and
PyPy 8.0.1 / Python 3.11.17. Default native optimization and GC were used. Runs
rotated variant order with no concurrent local build/profile workload. Startup,
compilation, input creation and full-result checks are outside repair-loop timers.

### Native timing and controls

The final AOT campaign used five independent processes per variant/workload,
each with six discarded warmup batches and five measured batches. Values below
are the median of the five process medians. Sizes count repeated fragments;
`mixed` is 200 rounds of ten records.

| Workload | Repairs per batch | Before, ms | After, ms | Interpretation |
|---|---:|---:|---:|---|
| Escaped, 2,000 | 5 | 26.00 | 9.16 | 2.84× faster |
| Escaped, 4,000 | 5 | 83.31 | 17.71 | 4.70× faster |
| Escaped, 8,000 | 5 | 173.17 | 40.79 | 4.25× faster |
| Escaped Unicode, 2,000 | 5 | 69.56 | 18.75 | 3.71× faster |
| Sparse escape, 4,000 | 5 | 13.00 | 6.09 | 2.14× faster |
| Short, four escapes | 500 | 6.88 | 6.93 | Overlapping samples |
| Valid JSON, 4,000 | 50 | 1.23 | 1.17 | Overlapping samples |
| Unicode, 2,000 | 20 | 9.29 | 8.90 | Overlapping samples |
| Mixed | 2,000 | 18.36 | 20.99 | Overlapping samples; slowdown risk |

For the five larger repair workloads, every paired process is faster and the
before/after process-median ranges are disjoint. Native mixed is slower in only
three of five pairs, with broad overlap (15.58–20.84 ms before,
13.55–22.92 ms after); this campaign establishes neither a mixed throughput gain
nor a conclusive regression. The first campaign also had a higher mixed median,
so the concern remains worth following up. No speedup is claimed for controls.

A separate JIT campaign used three process pairs, again six warmup/five measured
batches: escaped 2,000 improves **26.23 → 9.04 ms**, and escaped 8,000 improves
**162.71 → 42.99 ms**, with every pair faster and disjoint ranges. Mixed is
**16.46 → 16.39 ms** with overlapping samples. JIT startup/compilation remains
outside these timers and inside whole-process memory observations.

### Cross-engine tradeoffs

The final campaign uses exactly the same adapted parser/probes in CPython and
PyPy. CPython controls are noisy and do not establish a broad throughput gain.
PyPy's larger escape probes improve (4,000: **14.61 → 7.37 ms**;
8,000: **43.77 → 16.49 ms**), but its mixed workload showed a slowdown in both
initial and final finite-warmup campaigns.

A separate mixed-only PyPy check therefore increased warmup to **20 discarded
batches**, followed by **10 measured batches**, across five process pairs.
The median is **21.03 → 34.70 ms per 2,000 records**, a **65% regression**.
Every pair is slower, and ranges are disjoint: **17.58–24.05 ms** before versus
**27.52–37.18 ms** after. This is an observed tradeoff after the longer warmup,
not an established cause or a claim that all possible JIT transients disappeared.
Both shorter campaigns remain in the raw evidence. No regression is waived
because the native escape benchmark improves.

### Copy work, instructions and memory

The deterministic hosted probe measures concat/slice result lengths plus the
final snapshot. For 128/256/512 escaped fragments it reports
**16,905 / 33,801 / 67,593 copied code points**, a maximum individual concat/slice
result of **64**, and one final snapshot. These logical counts support bounded
accumulator work; they are not measured native byte traffic.

Separate Callgrind 3.22.0 runs use 8,000 escapes and one timed repair, plus the
probe's initial correctness repair. The complete witness matches in both runs.
Inclusive function counts overlap and must not be added together.

| Whole-process instruction measure | Before | After |
|---|---:|---:|
| Total `Ir` | 1,209,975,434 | 127,859,537 |
| `pys_str_add`, inclusive `Ir` | 817,312,175 | 5,717,384 |
| `pys_str_slice`, inclusive `Ir` | 274,024,649 | 2,071,290 |

This directly re-establishes the integrated baseline's concat/slice bottleneck
and its removal. Instrumented timing is not compared with ordinary wall time.
The raw profiler stderr (including its brk-limit notice), commands, binary/profile
hashes and selected attribution lines are retained.

The paired runner's `wait4` memory figures for native/CPython hit an approximately
47 MiB process-launch floor, so those values resolve no memory change. Separate
GNU `time` measurements avoid that floor: three process pairs per input, six
repairs per process (one witness plus five timed), preserve these peak RSS
medians and all 18 raw observations:

| Escaped fragments | Native before, KiB | Native after, KiB |
|---:|---:|---:|
| 2,000 | 36,760 | 11,592 |
| 4,000 | 38,252 | 22,088 |
| 8,000 | 47,184 | 34,760 |

These are whole-process peaks, including inputs and result checks, not retained
heap or allocation counts. Separate GC-stat runs show 276 → 1 collections at
8,000 fragments and heap peaks 45.7 → 34.5 MiB. The runtime's rounded live value
at its last collection does not measure retained memory after repair. Native
allocation/copy bytes and post-repair retained heap remain uninstrumented.

CPython `tracemalloc` uses one repair per sample, five samples per size, creates
input/expected values before tracing, and retains the verified output through an
explicit collection. The exact probe source and its hash are embedded in the
JSON evidence. Retained traced bytes are identical (**4,228 / 8,228 / 16,228**),
but median peaks rise **11,347 → 14,654**, **19,203 → 26,109**, and
**35,083 → 49,234 bytes** at 2,000/4,000/8,000 fragments. The last increase is
**40%** and reflects a real memory tradeoff in the adapted CPython parser. It is
not evidence about native retained objects.

To reproduce separate native memory and attribution measurements after building
both variants, run the same commands once for each binary. Keep profiling out of
ordinary timing campaigns:

```sh
taskset -c 0 /usr/bin/time -f 'peak_rss_kib=%M elapsed_seconds=%e exit=%x'   /tmp/after-scaling escaped 8000 5
valgrind --tool=callgrind --callgrind-out-file=/tmp/after.callgrind   /tmp/after-scaling escaped 8000 1
callgrind_annotate --inclusive=yes --auto=no /tmp/after.callgrind
```

## Paired timings

Build both probes against each integrated parser variant using the same compiler
and the same probe sources. Keep compilation separate from timing. The optional
final arguments are measured batches and discarded warmup batches; defaults
remain one measured batch and no warmup. Both probes check the complete output
before timing; scaling checks it again after every batch, and mixed checks its
checksum after every batch.

```sh
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/scaling.py -o /tmp/after-scaling
PYSTACHY_PATH=ports ./pystachy build bench/json_repair/bench.py -o /tmp/after-mixed
/tmp/after-scaling escaped 4000 5 5 6
/tmp/after-mixed 200 5 6
```

Create a config like this, replacing paths and adding CPython/PyPy variants with
explicit `PYTHONPATH` to the corresponding parser. Each `source` is the checkout
actually supplying compiler/library/port sources. `identity` records additional
verified toolchain/version details; the runner hashes each executable and script
in the command as well as all Python files under the consumed source roots,
including untracked/ignored ones.

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
    {"name": "unicode", "probe": "scaling", "args": ["escaped-unicode", "1000", "5"]},
    {"name": "short", "probe": "scaling", "args": ["escaped", "4", "500"]},
    {"name": "sparse", "probe": "scaling", "args": ["sparse", "4000", "5"]},
    {"name": "valid", "probe": "scaling", "args": ["valid", "4000", "5"]},
    {"name": "mixed", "probe": "mixed", "args": ["200"]}
  ]
}
```

Choose an allowed CPU from `os.sched_getaffinity(0)`, stop other local builds and
run the campaign. Never edit either source tree or executable during timing.

```sh
python3.13 tools/json_repair_bench.py /tmp/variants.json --cpu 0 \
  --pairs 5 --batches 5 --warmups 6 --output /tmp/accumulator-results.json
```

The runner rotates execution order, checks exact witnesses across all variants,
retains warmup and measured batches, and reports the median of each process's
measured median. NaN/negative timings, missing batches, unsuccessful processes,
changed source/executables and witness mismatches fail. It removes inherited
`PYSTACHY_*`/Python import overrides; provide required JIT LLVM/cache settings in
that variant's `env`. Retained raw samples include command, stdout/stderr,
source/executable hashes, host, core and source status. A shared host remains
noisy despite affinity and interleaving; report overlapping ranges honestly.

RSS comes from `wait4` for the **whole child process**, including startup, JIT,
input creation and validation; it can also include a pre-exec launch floor from
the parent process. It is not retained heap, total allocated bytes or
the repair-loop peak alone. For memory attribution and instruction profiles, run
separate native profiling jobs; do not mix instrumented and ordinary timings.
