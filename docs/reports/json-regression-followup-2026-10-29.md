# JSON regression follow-up, 29 October 2026

The combined changes for [#983](https://github.com/den-run-ai/pystachy/pull/983) and
[#984](https://github.com/den-run-ai/pystachy/pull/984) remove **79.47% of the remaining
instruction excess** in the retained pyperformance JSON workload relative to alpha.3.
Its residual overhead falls from **3.92% to 0.805%**. This is partial recovery:
[#969](https://github.com/den-run-ai/pystachy/issues/969) remains open, the original
historical 124M-instruction source is still unavailable, and an observed `Any` result
control shows a small additional instruction cost.

This checkpoint follows the [earlier blocker report](release-blocker-performance-2026-10-29.md).
That report's sources and results remain historical; the numbers below are fresh,
same-input measurements of the source identities listed here. Source-pinned validation
and the whole-corpus IR comparison are recorded below.

## Changes and correctness constraints

- Compatible `str`/`bytes` dictionaries use an immediate runtime kind and a specialized
  string probe. Hashes, table size, tombstones and probe order are retained. Immutable
  string probes can compare hashes before reading keys; generic object probes retain
  identity-first behavior. Ordinary list append keeps its small inlinable path, with
  identity-companion allocation moved into a separate helper. Redundant clearing of
  already-zero unused dictionary companion slots is removed.
- A checked `identity-inert` hint lets `json`'s typed scanner omit numeric companions.
  Its dynamic adapter uses scanner methods instead of exposing cursor fields. Unsafe
  arguments/results, field/global observations, boxing, mixed inheritance and numeric-list
  identity observations restore tracking through compiler restart. The hint is an
  optimization request, not permission to change identity semantics.
- Restoring the larger legacy string table was rejected. The retained
  [`dynany_str_dict_probe_order.py`](../../tests/programs/inference/dynany_str_dict_probe_order.py)
  counterexample needs a second equality callback: changing the probe sequence can produce
  `False` instead of `True` and suppress an exception. The optimization preserves that behavior.

## Sources and measurement

| Source | Commit | Tree |
|---|---|---|
| alpha.3 tag | `f5a09d4223139d7255e31051be97fc509e1ca1fe` | `8fef058c9a6de7f69b0baaebaaf087a8e39a79ac` |
| Main before these changes | `1540bb222fa5f82a7c24f6bb19aaf6db363898dd` | `c9867785a56313861fb1819c5369eb4aff3a5d8e` |
| Runtime PR #983 | `9975692d3d81253cd63d878e372315d39dca9826` | `7ba7f35b47b7995fe85924a37af7c467c4737f0e` |
| Identity PR #984 | `11f7ec5f44ca20d8ec53010cb8279b4eb2fa2abc` | `686db1794cfd702678d59bae5507629dbf4eec75` |
| Combined measured source | `40a2c5ddeab50ffdbcc54dc987577c9127d84470` | `92519c59b2777022e6a8b09649584659316ef775` |

The final identity tree differs from the measured tree only in two compiler-state
audit tool/test files; compiler, runtime, library and corpus bytes are identical.
The historical issue's baseline labeled "alpha.3" was actually post-tag commit
`dcdc1a28` (#885). This report uses the alpha.3 tag itself and does not equate those
baselines or claim to reconstruct the missing historical benchmark.

Linux x86-64, AMD EPYC 9V74, affinity CPU 0, glibc 2.39, LLVM/Clang 18.1.3,
CPython 3.13.16 and Valgrind 3.22.0. Every compiler frontend was hosted by the same
CPython. Each checkout supplied its own library/runtime and private cache. Inherited
`PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME` settings were cleared; the intended LLVM
path and `PYTHONHASHSEED=0` were then set. The broader JSON harness also set `LC_ALL=C.UTF-8`.
Sources were checked clean and their consumed bytes hashed before and after measurement.
No other session-owned heavy job ran alongside these profiles or timings.

The [pinned research archive](https://github.com/den-run-ai/pystachy/tree/cea842dde7fd773cfec083c61eb387055ff4dac3/research/json-969-2026-10-29)
retains raw profiles, all timing outputs, source manifests, reviewed IR differences
and reproduction scripts. Its 2,861,051-byte ZIP has SHA-256
`b967a557b06b5822fa2fd971c2607c2475049682e413f8cea5a43d28db4af816`.
Raw research stays on that branch; this report and reusable controls are the curated
repository additions. Compiler binaries, toolchain installations and the full generated
IR corpus are omitted and can be regenerated from the published source pins.

| Retained input | SHA-256 | Profile arguments |
|---|---|---|
| [`bench/pyperformance/json_loads.py`](../../bench/pyperformance/json_loads.py) | `51d23d4d8dcc3dea512988ae424988be6bf17d70e9e6d2a09d908799b3319c77` | `300` |
| [`bench/smoke/json_decode.py`](../../bench/smoke/json_decode.py) | `f863a322eec74cd9b9dfdc99035a1d82d1772be31614198a111a5c82b41564b5` | `numeric 3000`, `strings 3000`, `mixed 3000` |
| [`bench/smoke/json_decode_any.py`](../../bench/smoke/json_decode_any.py) | `7fa30eb1401ee9ca7e3f2c54e99726fe1ef554f7e69da70ad88cdf70e7427dcd` | `2000` |

The pyperformance loop and three 32-key controls discard their typed `JSONValue`
results inside an Any-opt-in program. Each prints a separate untimed decode into
`Any` for full-output comparison. The short `json_decode_any.py` control instead
observes an `Any` result on every iteration and accumulates its numeric field. Its
cursor stays in the small-integer cache, exposing adapter overhead without large
cursor-box allocation savings. It complements, rather than replaces, typed decoding.

## Executed instructions

Callgrind counts cover the complete AOT process, including startup, untimed validation
and output. Every profiled stdout matches CPython exactly.

| Workload | alpha.3 Ir | Main Ir | Combined Ir | Combined / main | Combined / alpha.3 |
|---|---:|---:|---:|---:|---:|
| pyperformance JSON, 300 outer loops | 1,300,357,994 | 1,351,340,732 | 1,310,824,081 | −3.00% | +0.805% |
| 32-key numeric, 3,000 loads | 91,420,809 | 98,680,291 | 93,173,752 | −5.58% | +1.92% |
| 32-key strings, 3,000 loads | 108,663,964 | 112,101,252 | 110,413,617 | −1.51% | +1.61% |
| 32-key mixed, 3,000 loads | 127,319,515 | 134,594,787 | 129,075,378 | −4.10% | +1.38% |
| Observed `Any` result, 2,000 loads | 29,964,363 | 30,855,523 | 31,334,935 | **+1.55%** | **+4.57%** |

The broader workload removes 40,516,651 of main's 50,982,738 excess instructions,
leaving 10,466,087. Dictionary insertion and its callees account for approximately
7.22M of this residual, about 69%. The scanner's `number()` subtree uses 56,476,921
instructions versus alpha.3's 56,476,613, a difference of only 308; the remaining
work is not principally numeric cursor identity bookkeeping. Further dictionary work must preserve callback/probe
semantics rather than recovering the old table layout indiscriminately.

The final runtime-only source measured 1,326,402,110 instructions. That profile is
from `912ea029eb2ee1ce6d2097c381a507d79e223874`; #983's final tree differs only in
two opt-in exception manifests. This isolated runtime trial was not CPU-pinned and
makes no wall-time claim. The archived earlier runtime checkpoint is labeled
separately and must not be mistaken for this result.

The three 32-key controls now retain repeatable sources, but **none is the missing
historical 124M workload**. Their results cannot satisfy that original acceptance
criterion. The `Any` control also prevents the typed-decoder improvement from being
misreported as a universal JSON speedup: scanner helper dispatch remains a cost.

## Paired timing limits

For each control and mode, two warmup rounds preceded seven measured rounds. Source
order alternated. Internal timers exclude compiler startup; the three typed controls
stop before validation/output, while the measured Any control stops after its checksum
assertion and final stdout print, so its time includes the loop, check and output.
All revisions used that same unchanged input and output. The 32-key controls used
30,000 loads and the observed-`Any` control used 20,000. All 216 retained stdout files
(warmups and measurements) match their CPython oracle. The table shows the median
of per-round combined/baseline ratios, not ratios of separately computed medians.

| Control | AOT vs main | AOT vs alpha.3 | Warm JIT vs main | Warm JIT vs alpha.3 |
|---|---:|---:|---:|---:|
| Numeric | 0.946 | 0.979 | 1.053 | 0.898 |
| Strings | 0.979 | 1.010 | 1.008 | 1.032 |
| Mixed | 0.959 | 1.046 | 0.904 | 0.959 |
| Observed `Any` | 1.009 | 1.033 | 0.952 | 1.333 |

Every case/mode has overlapping source timing ranges on this shared host. For example,
observed-`Any` AOT ranges are 37.50–52.11 ms (alpha.3), 36.26–50.83 ms (main) and
36.59–75.32 ms (combined); JIT ranges are 38.12–56.80, 39.54–78.52 and 37.66–80.77 ms.
The timings do not establish a precise small speedup, slowdown or alpha.3 parity.
The instruction increase in observed-`Any` decoding is real even though wall-time
attribution remains inconclusive. These are control measurements, not new paired
wall-time evidence for the broader pyperformance workload.

## Reproduce and inspect

Use clean checkouts at alpha.3 `f5a09d42`, pre-follow-up main `1540bb22`, and the
published final identity head `11f7ec5f`, with the same input bytes for all three.
The final head reproduces the measured `40a2c5dd` compiler/runtime/library inputs;
that local measurement commit is recorded for provenance, not required for replay.
The [control README](../../bench/smoke/README.md#retained-json-decoder-controls)
gives paired builds, separate caches, CPU pinning, Callgrind and output comparisons.
For the broader workload, from each source checkout with its own cache:

```sh
python3.13 pystachy.py build /absolute/shared/json_loads.py -o /absolute/output/json_loads
python3.13 /absolute/shared/json_loads.py 300 > /absolute/output/oracle.out
taskset -c 0 valgrind --tool=callgrind --error-exitcode=99 \
  --callgrind-out-file=/absolute/output/json_loads.callgrind \
  /absolute/output/json_loads 300 > /absolute/output/native.out
cmp /absolute/output/oracle.out /absolute/output/native.out
```

Apply the same commands to the short Any control with `2000`; use `3000` and the
case selector for each 32-key control. Run wall-clock samples outside Valgrind,
warm each source, alternate order and retain all samples. Compare both JIT and AOT.
The [LLVM call inventory](../performance.md#inspecting-emitted-llvm-calls) from #900
helps locate boxing and helper calls in raw and actual linked/optimized IR. Static
call counts do not measure dynamic executions or prove instruction savings.

## Validation checkpoint

Local identity checks passed 15 identity-scope, 11 compiler-restart, 18 frame-state
and 29 JSON unit tests, plus targeted mypy and Ruff. At helper checkpoint `82159ba4`,
seven differential cases passed both JIT and AOT with collection at every allocation
(14 checks), including all three identity-inert fixtures, JSON errors/round trips,
dynamic JSON and raw decoding. The command used the pinned hosted compiler frontend:

```sh
PYSTACHY_GC_STRESS_PROGRAM=1 PYSTACHY_JOBS=2 \
  tests/run.sh "$PY -m pystachy" 'jit aot' \
  tests/programs/inference/dynany_identity_inert.py \
  tests/programs/inference/dynany_identity_inert_fields.py \
  tests/programs/inference/dynany_identity_inert_internal.py \
  tests/programs/library/json_errors.py tests/programs/library/json_roundtrip.py \
  tests/programs/inference/dynany_json.py tests/programs/inference/dynany_json_raw_decode.py
```

The final combined bootstrap at tree `686db1794cfd702678d59bae5507629dbf4eec75`
reached both fixed points: 770,829 compiler IR lines and 18,805 runtime IR lines,
identical across all three stages.
The six newly added differential fixtures' mutual-pragma exclusions were independently
verified on main `1540bb22` and their candidate sources in both run/build modes:
24 exact exit-1 rejections, empty stdout, unchanged diagnostic. Only those new cases
were registered; no runtime mismatch, crash or existing manifest entry was exempted.

The full hosted before/after oracle compared main `1540bb22` with combined `40a2c5dd`,
using each source's own library and the same 3,871 corpus inputs. Both accepted 2,086
and rejected 1,785; no new acceptance, rejection, compiler error or timeout occurred,
and consumed inputs stayed unchanged. After symmetric checkout-path normalization,
3,825 outputs were identical. All 46 remaining differences were reviewed: 29 immediate
dictionary-kind changes, 15 JSON helper/layout changes, one identity-inert fixture and
one diagnostic source-line shift. None was unexpected. Pystachy's own emitted IR was
raw-identical. The original harness overreported 38 differences because it normalized
one checkout root per side; the archived classification corrects that error while
preserving the original summary and raw evidence.

The identity PR's initial CI Lint run found a missing `IDINERT` global-ownership audit
entry. The final head registers it and adds executable seed/reset-removal,
import-reindex, failed-load, plain/runtime and restart controls; ten targeted checks
and final CI Lint pass. Reset behavior already existed.

Both code PRs passed all 40 applicable checks on their exact final heads; fork-only
DCO was conditionally skipped. #983 merged as `b8e5c2d37d35e9e83818674cd3538993112c0259`
and #984 as `56dc29790fead2bde3d6a45a3e59f16bca9e6b05`. Live main after #984 has
tree `686db1794cfd702678d59bae5507629dbf4eec75`, exactly the tested integration.
Both merges used expected-head checks after fresh review-thread and main reads;
independent source and oracle reviews found no correctness issues. Post-merge CI
runs separately; passing PR checks are not labeled a completed main release gate.
No tag or release is published by this work. The remaining instruction costs and
missing historical input keep #969 open.
