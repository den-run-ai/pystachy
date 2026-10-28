# Opt-in JSON loads performance, 28 October 2026

The reviewed JSON hot-path changes in [PR #974](https://github.com/den-run-ai/pystachy/pull/974)
recover a substantial part of the opt-in `json.loads` slowdown. Against the measured main
revision, median AOT loop time fell 20.4% and warm-JIT loop time fell 32.6%. They do **not**
establish complete recovery to alpha.3: AOT was slower in all seven paired comparisons with
alpha.3. Its precise remaining cost is uncertain on this shared host. Warm-JIT differences
from alpha.3 were small relative to the observed variation and changed direction between pairs.
Refs [#969](https://github.com/den-run-ai/pystachy/issues/969).

## Sources and method

| Variant | Source identity |
|---|---|
| alpha.3 | [`f5a09d4223139d7255e31051be97fc509e1ca1fe`](https://github.com/den-run-ai/pystachy/commit/f5a09d4223139d7255e31051be97fc509e1ca1fe), the `v0.1.0-alpha.3` tag |
| main reference | [`5bd492b33cd6bc32fb464d008d543560a8959486`](https://github.com/den-run-ai/pystachy/commit/5bd492b33cd6bc32fb464d008d543560a8959486) |
| PR #974 integrated with main | PR head [`f02150796bc356e2f47572ac147121d0384f919f`](https://github.com/den-run-ai/pystachy/commit/f02150796bc356e2f47572ac147121d0384f919f), integrated with the main reference above; tree `a5fbdba8564478b347cb83f028ab4213947e9d88`, identical to GitHub's PR merge commit [`6ff24a07e09bb78be482402b2fd065ea72f2767b`](https://github.com/den-run-ai/pystachy/commit/6ff24a07e09bb78be482402b2fd065ea72f2767b) |

The local integration commit was `c33bb19a5459c5f4a26c100cc4d093a08c0036ba`; its tree equality
with the GitHub merge tree was checked. Main and the integrated candidate were built to both
compiler and runtime IR fixed points. Alpha.3 used its CPython-hosted compiler. Consequently,
the alpha.3 comparisons cover generated AOT programs and timed JIT program loops, **not**
comparable compiler startup or frontend throughput.

The input is the existing adapted
[`bench/pyperformance/json_loads.py`](https://github.com/den-run-ai/pystachy/blob/f02150796bc356e2f47572ac147121d0384f919f/bench/pyperformance/json_loads.py),
SHA-256 `51d23d4d8dcc3dea512988ae424988be6bf17d70e9e6d2a09d908799b3319c77`.
Every variant compiled and ran this same file. Each sample uses 2,000 outer iterations and
the benchmark's three payloads, 20 loads per payload: 120,000 `json.loads` calls. Seeded input
generation and all printed witnesses are unchanged. Complete stdout matched CPython 3.13.16
exactly, with exit status zero, before timing and in every timed run.

Measurements used Linux x86-64, kernel 6.18.55, glibc 2.39, an AMD EPYC 9V74 processor,
Ubuntu LLVM 18.1.3 and CPython 3.13.16. Processes were pinned to CPU 0. Default optimization
settings were used, without GC stress. Each checkout retained its own runtime cache, warmed
before samples. Home, path, cache, optimization and stress overrides were cleared. No other
owned heavy job ran during these measurements; this remains a shared host with uncontrolled
external load and CPU frequency.

Each comparison has seven interleaved pairs per execution mode, reversing variant order
on alternate pairs. The tables report the benchmark's internal loop timer, excluding compiler
startup, initial runtime-cache creation and AOT compilation. The main and alpha.3 comparisons
are separate series; their candidate medians should not be treated as one pooled sample.

The per-variant commands were equivalent to the following, using the same benchmark bytes
and each variant's own checkout. Warm both paths before alternating seven samples; use
`python3.13 pystachy.py` instead of `./pystachy` for the alpha.3 hosted frontend.

```sh
./pystachy build /tmp/pystachy-json-loads.py -o /tmp/pystachy-json-loads
taskset -c 0 /tmp/pystachy-json-loads 2000
taskset -c 0 ./pystachy run /tmp/pystachy-json-loads.py 2000
python3.13 /tmp/pystachy-json-loads.py 2000
```

## Loop timings

Seconds, median and observed minimum–maximum, seven samples per cell:

| Main comparison | AOT | Warm JIT |
|---|---:|---:|
| Main reference | 0.950322 (0.932500–1.167218) | 1.122727 (1.082619–1.199141) |
| Integrated #974 | 0.756468 (0.687543–0.853413) | 0.756979 (0.724861–0.826986) |
| Ratio of medians, candidate/main | **0.7960** | **0.6742** |

The candidate was faster in every pair in both modes. These measurements support the
improvement against this main reference on this workload.

| Alpha.3 comparison | AOT | Warm JIT |
|---|---:|---:|
| alpha.3 | 0.652527 (0.635645–0.783920) | 0.729953 (0.689248–0.874335) |
| Integrated #974 | 0.753291 (0.680018–0.840269) | 0.743243 (0.736200–0.810328) |
| Ratio of medians, candidate/alpha.3 | **1.1544** | **1.0182** |
| Median of paired ratios | **1.0719** | **1.0272** |

For alpha.3 AOT, the ratio of medians suggests 15.4% overhead while the median paired ratio
suggests 7.2%. Their disagreement and overlapping ranges prevent a precise effect-size claim.
All seven AOT pairs were nevertheless slower, so the evidence supports a residual AOT cost.
The JIT pairs change direction; the small headline difference is inconclusive.

All individual paired ratios are below. A value below 1 means the candidate was faster.

| Pair | AOT / main | JIT / main | AOT / alpha.3 | JIT / alpha.3 |
|---|---:|---:|---:|---:|
| 1 | 0.7373 | 0.7441 | 1.0719 | 1.0651 |
| 2 | 0.8086 | 0.6590 | 1.0698 | 0.9194 |
| 3 | 0.7294 | 0.7281 | 1.1475 | 1.0272 |
| 4 | 0.7773 | 0.6572 | 1.0490 | 0.9696 |
| 5 | 0.6481 | 0.6742 | 1.0280 | 1.1123 |
| 6 | 0.7599 | 0.6567 | 1.2248 | 1.1757 |
| 7 | 0.8406 | 0.6273 | 1.1630 | 0.8420 |

The one Linux AOT benchmark executable was 224,360 bytes for alpha.3, 252,424 bytes for main,
and 252,392 bytes for the candidate. This is effectively unchanged from main and about 12.5%
larger than alpha.3 for this executable. Build durations were single observations affected by
cache state and frontend differences; they do not establish an AOT build-cost improvement.

## Correctness and IR evidence

Review found and fixed a silent wrong-result bug in the draft optimization: after a `try`
statement retired a lazy field-sharing candidate, later write-backs could restart sharing
without participating in barriers. A callback could then leave the field's box describing a
different value from its numeric payload. The original PR head printed
`1000 3000 1000 False` in both JIT and AOT where CPython prints `1000 1000 1000 True`.
The fix prevents retired candidates from restarting sharing. Its standalone CPython-recorded
regression is
[`dynany_identity_field_retired.py`](https://github.com/den-run-ai/pystachy/blob/f02150796bc356e2f47572ac147121d0384f919f/tests/programs/inference/dynany_identity_field_retired.py).

Local validation included:

- Four relevant identity fixtures in hosted and native JIT/AOT, both normally and with
  program GC stress: 32 checks passed on the fixed PR tree.
- On the integrated tree, all three #911 chained-comparison fixtures and the new field
  regression in native JIT/AOT, normally and with program GC stress: 16 checks passed.
- The three changed field/local/lookup IR guards passed the compiler check and `llvm-as`.
- Fifty numeric-identity unit tests and 39 promoting-int harness tests passed. The four new
  dynamic-Any fixtures produced the eight exact documented dual-opt-in rejections in the
  targeted promoting-int gate, with zero unexpected failures.
- On the fixed PR tree before the #911 integration, CPython 3.13.16 recording verification
  checked 1,869 recordings, 105 deviations and 11
  library files with zero failures. Runtime signatures/effects and repository hygiene passed.
- The integrated compiler fixed point contained 765,737 IR lines; the runtime fixed point
  contained 18,805 lines.

The full native IR oracle compared 3,839 cases on the fixed PR tree against the main reference:
377 raw differences, no exit-status changes, and no diagnostic changes after normalizing the
demonstrated checkout library prefixes. After integration with main, 380 cases were checked
again: those 377 differences plus the three new #911 fixtures. Normalizing only exact checkout
paths and their LLVM string lengths left **145 intended IR changes**; 232 differences were
path-only. The three #911 fixtures were IR-identical to main. Each compiler retained its own
library/runtime inputs; they were not replaced with a shared home to suppress differences.

The remaining IR changes are in dynamic-Any programs and consumers such as JSON/tomllib,
including numeric argument/return companions, plain-field operands and field-sharing state.
There were no new rejections or changed diagnostics in the checked corpus. This is a
behavior-change comparison, not a claim that all generated IR is identical or that every
possible program shape has been covered.

For `json_loads.py`, unoptimized IR grew from 12,672 to 13,603 lines while static
`pys_dyn_int_box` call sites fell from 138 to 128. Extra control flow and fewer static call sites
do not by themselves prove an allocation or runtime improvement; the timings above supply
the workload evidence. Full applicable CI, review and the release gate remain separate
requirements on the eventual release commit.
