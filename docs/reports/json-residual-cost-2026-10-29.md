# Residual JSON costs, 29 October 2026

This follow-up to [the earlier JSON report](json-regression-followup-2026-10-29.md)
removes **84.29% of the remaining broad-workload instruction excess** over the
actual alpha.3 tag. Broad JSON overhead falls from **+0.805% to +0.126%**.
The observed-`Any` control is **6.03% below current main and 1.73% below alpha.3**;
the previous short-control tradeoff is recovered. The three retained 32-key
controls are also below alpha.3.

[#969](https://github.com/den-run-ai/pystachy/issues/969) remains open: the small
broad-workload gap remains and the historical 124M-instruction source is still
unavailable. New controls cannot retrospectively validate that old result.

## Changes and preserved behavior

- Fresh string/bytes dictionary insertions bypass probe-function setup when the
  first slot is empty. Read-only lookups compile without the extra check; occupied
  slots and tombstones use the existing probe. Hashing, capacity, slot visitation,
  equality callbacks and mutation/error behavior are unchanged.
- The growth test compares unsigned products instead of dividing on every
  insertion. `used >= floor(2*size/3)` is equivalent to `3*used + 2 >= 2*size`;
  reachable table bounds keep both products representable. The empty table and
  `popitem()`'s cut entries retain their existing behavior.
- The dynamic JSON adapter compares canonical byte-token identities and reads
  each delimiter once. Its primitive decoder shares number scanning but avoids
  importing typed array/object recursion into an Any-only consumer. The original
  `scalar()` and typed `value()` behavior remain intact. The small dispatch tail
  is deliberately duplicated: routing typed decoding through the extracted helper
  added about 3.95M broad-workload instructions in a rejected trial.
- Deterministic guards require the empty-slot shortcut, preserve lookup past a
  tombstone, check exact growth boundaries, and prevent bytes indexing or typed
  container recursion from returning to the Any path. Removing each optimization
  makes its respective guard fail. Numeric identity boundaries are unchanged.

## Sources and method

| Source | Commit |
|---|---|
| Actual alpha.3 tag | `f5a09d4223139d7255e31051be97fc509e1ca1fe` |
| Current main baseline | `526e7b4eb1dca85e1cab781f03331d7d2eb236f8` |
| Evaluated combined source, published | `53cc4b1160bb728853208d3b4fbf7239523af72a` |

The evaluated code tree is `fbaa27cac3865921edf75f9c90987dc65bc06d2e`.
The evidence manifest records local measurement commit `b22710cd63650756db03e864aeb9649cd07da1ec`;
the published commit has exactly that full tree, verified after upload.
Later report-only edits do not change the consumed compiler, runtime or library
bytes. All sources use their own library/runtime and private caches, the same
CPython 3.13.16 frontend, LLVM/Clang 18.1.3 and Valgrind 3.22.0 on Linux x86-64
(AMD EPYC 9V74), pinned to CPU 0. Inherited `PYSTACHY_*`, `PYTHONPATH` and
`PYTHONHOME` settings are cleared; `PYTHONHASHSEED=0` and `LC_ALL=C.UTF-8` are set.
No other session-owned heavy job runs alongside profiles.

The retained input bytes are unchanged from the prior report. The broad control
uses 300 outer loops; each 32-key case uses 3,000 loads; observed Any uses 2,000.
Counts cover the entire AOT process, including startup and untimed validation.
Every profiled stdout matches pinned CPython byte for byte. Source/input and binary
hashes are retained and consumed source identities are checked again after profiling.

## Executed instructions

| Workload | alpha.3 Ir | Main Ir | Candidate Ir | vs main | vs alpha.3 |
|---|---:|---:|---:|---:|---:|
| Broad pyperformance JSON | 1,300,338,557 | 1,310,804,265 | 1,301,982,770 | −0.673% | +0.126% |
| 32-key numeric | 91,420,750 | 93,173,051 | 90,959,432 | −2.376% | −0.505% |
| 32-key strings | 108,663,905 | 110,412,916 | 108,225,169 | −1.981% | −0.404% |
| 32-key mixed | 127,319,538 | 129,074,649 | 126,940,795 | −1.653% | −0.297% |
| Observed Any | 29,964,369 | 31,334,929 | 29,445,024 | −6.031% | −1.733% |

The broad residual falls from 10,465,708 to 1,644,213 instructions. Dictionary
insertion and its callees now use 214,949,616 instructions versus alpha.3's
215,619,679 (−0.311%); the remaining total gap should no longer be attributed
principally to that subtree. The number scanner remains within 308 instructions
of alpha.3. Fresh whole-process counts differ slightly from the earlier report;
all ratios here use this session's baselines.

Existing dictionary controls check the insertion shortcut against updates, repeated
hits, misses, deletion/reinsertion, copies and adversarial keys:

| Control | Main Ir | Candidate Ir | Change |
|---|---:|---:|---:|
| `bench/dictcount.py` | 1,348,052,838 | 1,347,770,227 | −0.021% |
| `bench/dictlookup.py` | 2,508,747,467 | 2,496,933,329 | −0.471% |
| `bench/dictkeys.py` | 1,427,840,290 | 1,417,759,579 | −0.706% |

These are executed-instruction results, not wall-time speedups. No complete paired
JIT/AOT timing series is claimed for the final source. An exploratory timing run
on the earlier numeric-shortcut candidate was stopped after broad AOT when the
stronger Any candidate became available; those timings do not certify this source.
CI's separate Performance smoke remains an advisory paired comparison.

## Useful probes and replay

The new retained [JSON controls](../../bench/smoke/README.md#retained-json-decoder-controls)
separate typed discarded results from observed Any values. Keep both: a broad
typed-decoder improvement alone missed the small-document helper cost. These
controls are standalone, not noisy CI timing gates.

`make dictprobe` checks exact probe/hash/layout behavior and GC-stressed cached
hashes. Its new guards cover empty first-slot insertions, colliding equal keys
behind tombstones and growth boundaries. The existing dictionary benchmarks above
check workloads that can lose from an insertion optimization.

The [LLVM call inventory](../performance.md#inspecting-emitted-llvm-calls) from
#900 helps inspect scanner/boxing calls. Its counts are static; pair them with
Callgrind. The new Any IR guard checks reachability of typed parser definitions,
not a wall-time threshold.

Use clean checkouts of the three source pins and the unchanged inputs from main.
From each checkout with its own cache, for example:

```sh
python3.13 pystachy.py build /path/main/bench/smoke/json_decode_any.py -o /path/output/any
python3.13 /path/main/bench/smoke/json_decode_any.py 2000 > /path/output/oracle.out
taskset -c 0 valgrind --tool=callgrind --error-exitcode=99 \
  --callgrind-out-file=/path/output/any.callgrind /path/output/any 2000 > /path/output/native.out
cmp /path/output/oracle.out /path/output/native.out
```

Set `PYSTACHY_LLVM` to the complete LLVM 18 toolchain and put Valgrind on PATH.
Select an allowed CPU if CPU 0 is unavailable. Repeat with the workloads and
arguments above; dictionary controls take no arguments. The retained measurement
harness rejects output or source-identity changes. Raw profiles, source manifests,
replay code and local test logs are retained separately in an evidence archive
(SHA-256 `950f00e87bd479f4865e695c6dc446d820ceecfdbe84250c09392411293259ea`),
not in this mergeable source tree.

## Correctness checkpoint

On the evaluated code, lint, runtime signature/effect checks, repository hygiene,
all 1,898 recordings plus 107 deviations and 11 pinned library files pass. The
identity-scope unit suite passes 16 tests and JSON unit suites pass 29. Twenty-one
focused JSON, dictionary callback and identity-boundary programs pass JIT and AOT
through the pinned hosted frontend: 42 regular and 42 program-GC-stress checks.

The dictionary probe passes normally and under GC stress; its worst adversarial
average is 1.93 slots against the existing limit of 3. Independent hosted
old/new semantic comparison passes 37,885 checks, including malformed text,
Unicode/surrogates, nesting boundaries, raw-decode offsets and direct `scalar()`
subclass dispatch. This source-level check is distinct from native execution.
Independent source reviews found no remaining correctness issue. Full native
compiler/bootstrap and verification-matrix status belongs to the PR's exact-head
CI, not these local checks.
