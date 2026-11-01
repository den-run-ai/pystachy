# Ordinary-text spans in JSON repair: implementation and measurements

The native controls show substantial improvements when malformed strings contain
ordinary runs: about **6.5× AOT and 7.3–7.8× JIT** for long/sparse-escape inputs,
and **4.2–4.8×** for raw Unicode text. Dense escapes gain little, and larger-string
peak memory can increase. The default API's maintained mixed workload is measured
separately below, including its noisy initial campaign and longer confirmation.

## Change and comparison identity

[946bb203](https://github.com/den-run-ai/pystachy/commit/946bb203c1835af708b5779c388b85482cf7514b) is the standalone
span implementation on main `07b26e02` in [PR #1007](https://github.com/den-run-ai/pystachy/pull/1007).
It changes the maintained adaptation of json_repair 0.64.1. The
[parser](https://github.com/den-run-ai/pystachy/blob/946bb203c1835af708b5779c388b85482cf7514b/ports/json_repair/parse_string.py) advances across
ordinary code points with a small local scan, then appends the source range once.
It stops at escapes, quotes, structural punctuation and context-sensitive
whitespace, retaining the existing post-append quote/colon heuristics and logs.

The shared accumulator fills its tail and adds complete **64-code-point chunks**
without materializing the entire substring or copying a growing prefix. Arbitrary
appends still update brace/regex metadata; proven ordinary spans omit that work.
A one-code-point path avoids extra slicing on short runs and decoded escapes.
This storage improvement also serves existing inline-container and escape callers.
It is reusable within the parser, with no new compiler transformation, ownership
assumption, byte-index conversion or restriction on accepted programs.

To measure after the correctness fix and account for the existing scanner work,
both benchmark variants use a local merge of
[#1003 `dceda23e`](https://github.com/den-run-ai/pystachy/commit/dceda23e8b71311c43e5c843698ed4443292004b) and
[#1004 `d056aafe`](https://github.com/den-run-ai/pystachy/commit/d056aafe2f0c09d72ca23bf14b18123d1e439170). Its exact tree is
`276e01519733a14303e9d7d29bed2b44df92e37a`. The candidate adds **only the span parser diff** to that tree;
the compiler and the other ports/libraries are identical. This is not a claim that
these separate PRs are merged. Full identities and all measurements are retained in
[measurements.json](measurements.json) and the [raw archive](evidence.tar.xz). The [archive manifest](archive-manifest.json) lists
all retained files and hashes; [SHA256SUMS](SHA256SUMS) covers this publication package.

## Method

LLVM/Clang **18.1.3**, Linux x86-64, Intel Xeon Platinum 8573C, CPU 0 on a shared
host. Processes run sequentially, with baseline/candidate order alternating and
case order rotated. Complete values, Unicode code points and serialized text are
validated outside timers; each timed result contributes to a checked checksum.
All **208** primary-campaign processes completed with matching witnesses.

Tables show batch-time medians across process medians. “Change” is the percentage
change between those medians; “paired” is the median change within process pairs.
Negative percentages mean faster. These are descriptive comparisons, not confidence
intervals; raw process samples are retained.

## Forced-repair controls

The [standalone probe](https://github.com/den-run-ai/pystachy/blob/946bb203c1835af708b5779c388b85482cf7514b/bench/extended/json_repair_spans.py)
uses the same adapted port in both variants and forces `skip_json_loads=True`.
Large strings include escapes or raw newlines so the simple-quoted-string shortcut
cannot conceal repair work. These controls isolate repair from valid-JSON decoding.
Each configuration has **five pairs**, three warmups and seven measured batches.
Size is 4,096 target code points except fixed small short/mixed inputs. Rounds per
batch: short 20,000; mixed 5,000 with five repairs each; long/sparse 200; others 100.

| Case | AOT base → candidate ms | AOT change / paired | JIT base → candidate ms | JIT change / paired |
| --- | ---: | ---: | ---: | ---: |
| short | 60.995 → 60.631 | -0.60% / -0.62% | 73.333 → 73.538 | +0.28% / +0.17% |
| mixed | 106.734 → 83.275 | -21.98% / -22.66% | 119.343 → 100.778 | -15.56% / -18.97% |
| long | 232.994 → 35.939 | -84.58% / -84.54% | 267.944 → 34.205 | -87.23% / -86.65% |
| sparse | 221.816 → 34.130 | -84.61% / -84.61% | 255.361 → 35.144 | -86.24% / -86.20% |
| dense | 169.170 → 171.517 | +1.39% / -0.79% | 193.086 → 198.598 | +2.85% / -0.47% |
| unicode | 125.943 → 29.769 | -76.36% / -76.69% | 142.481 → 29.653 | -79.19% / -79.39% |
| punctuation | 114.676 → 75.634 | -34.05% / -34.05% | 131.724 → 85.163 | -35.35% / -36.75% |
| regex | 106.216 → 85.312 | -19.68% / -19.02% | 119.134 → 98.627 | -17.21% / -20.53% |

Short results are close to unchanged. Dense object-return aggregates are slightly
slower while paired medians are slightly faster; this establishes no dependable
dense-escape gain. The historical repeated `x\n` workload has almost no ordinary
span to batch. This change does **not** establish that its reported PyPy gap closes.

## Serialization and scaling

These AOT controls use three pairs, three warmups and seven measured batches.
Serialization includes repair plus `repair_json()`'s output encoding. Scaling
uses 100 repairs per batch, whereas the 4,096-size long/sparse rows above use 200;
normalize by calls before comparing sizes.

| AOT control | Size | Rounds | Base → candidate ms | Change / paired |
| --- | ---: | ---: | ---: | ---: |
| serialize long | 4096 | 200 | 223.879 → 36.980 | -83.48% / -83.43% |
| serialize sparse | 4096 | 200 | 226.926 → 41.773 | -81.59% / -81.59% |
| serialize dense | 4096 | 100 | 170.852 → 175.959 | +2.99% / +2.99% |
| serialize unicode | 4096 | 100 | 143.774 → 48.499 | -66.27% / -66.12% |
| objects long | 8192 | 100 | 222.376 → 35.631 | -83.98% / -83.84% |
| objects long | 16384 | 100 | 450.818 → 65.697 | -85.43% / -85.48% |
| objects sparse | 8192 | 100 | 225.998 → 32.785 | -85.49% / -85.68% |
| objects sparse | 16384 | 100 | 447.901 → 66.895 | -85.06% / -85.06% |

Long/sparse wins persist at 8,192 and 16,384 code points. Dense serialization costs
about **3.0%** in this campaign and is retained as a tradeoff. No threshold was
relaxed and no slower control was removed.

Peak RSS is also not uniformly better. The 8,192-code-point long control's median
AOT peak rises **37136 → 43832 KiB
(+6.54 MiB)**. All per-process RSS values are in the compact ledger.
These are process peaks, not allocation counts or evidence of a leak. AOT excludes
compilation; JIT RSS covers the compiler/JIT invocation and waited-for children,
with `ru_maxrss` reporting a maximum rather than total concurrent residency.

## Default API: maintained mixed consumer

The unchanged [ten-record benchmark](https://github.com/den-run-ai/pystachy/blob/946bb203c1835af708b5779c388b85482cf7514b/bench/json_repair/bench.py)
uses normal decoder dispatch and returns objects; serialization is outside timing.
Both adapted-CPython zero-round oracles and every native run have identical full
outputs, `per_round=616`, and checked records/checksums. Each process has three
warmups and five measured batches. Both campaigns are retained:

| Campaign | Engine | Repairs/batch | Pairs | Base → candidate ms | Change / paired |
| --- | --- | ---: | ---: | ---: | ---: |
| Initial | AOT | 20000 | 3 | 205.704 → 177.204 | -13.85% / -13.85% |
| Initial | JIT | 20000 | 3 | 240.712 → 294.143 | +22.20% / +0.89% |
| Confirmation | AOT | 100000 | 5 | 983.228 → 881.594 | -10.34% / -10.34% |
| Confirmation | JIT | 100000 | 5 | 1177.384 → 1061.642 | -9.83% / -9.41% |

The initial JIT summary was **+22.20%** slower by aggregate medians but **+0.89%**
by paired medians; its first AOT pair was **+49.7%** slower.
That disagreement prompted one longer confirmation using unchanged sources and
executables, five pairs and 100,000 repairs per batch. The additional evidence does
not erase the initial variation. This is one repeated synthetic consumer, not a
production workload distribution or a promise of improvement for every document.

## Correctness and verification

The existing **645-case** replay passes in adapted CPython, native JIT/AOT, and
both native modes with collection at every program allocation. This corpus is
not the complete upstream test suite. Independent hosted differential review
compares **16,132** public/parser/scan/accumulator observations against the pre-change
adapted port, including values, errors, logs, positions and metadata, with zero mismatches.

Two new regression programs pass eight normal/stressed native executions; the
combined correctness/scanning/span selection passes 16 native executions.
Nine accumulator unit tests include independent metadata and deterministic work
checks plus negative controls; 11 repository-hygiene tests and local lint pass.
These checks cover code-point/chunk boundaries, Unicode/surrogates, escapes,
quoted keys, regex whitespace, smart quotes, inline containers and streaming EOF.
Compiler/runtime sources are unchanged by the span PR. A complete trial merge of
all ten changed files with #1003 and #1004 is conflict-free, matches the measured
parser/runtime inputs, and passes the nine accumulator tests.

The [CI ledger](ci-ledger.json) records **40 successful checks** on published head
`946bb203c1835af708b5779c388b85482cf7514b`, with the expected fork-only DCO skip.
All five applicable workflows succeeded: the [34-job CI matrix](https://github.com/den-run-ai/pystachy/actions/runs/41282000146),
installation, packages, lint and performance smoke. This hosted CI evidence is
separate from the local checks above; no independent GitHub review has been submitted.

## Reproduction and limits

The [portable recipe](reproduction/README.md) reconstructs the pinned baseline,
applies only the parser delta, verifies source hashes, and builds fresh compilers.
Timing requires explicit opt-in after other builds/tests stop. The raw archive
preserves all campaigns, rejected/intermediate pilots, build logs, commands,
environments and source identities; [measurements.json](measurements.json) keeps
the complete compact comparison, including slower cases and memory peaks.

Startup/compilation and process wall time are separate from warmed batch timings.
Runtime caches may already be warm; **no cold-start claim** is made. CPython's
default-API runs are output checks, not a performance comparison; no fresh PyPy,
GraalPy or pristine-upstream ranking was measured. These results support the
ordinary-span optimization within its measured scope, not universal JSON-repair
superiority, full compatibility or release readiness.
