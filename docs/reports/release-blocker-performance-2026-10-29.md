# Compatible scalar dictionary fast path, 28 October 2026 (Pacific time)

PR [#980](https://github.com/den-run-ai/pystachy/pull/980) preserves Python-compatible dictionary hashes and probe order while removing generic hashing and lookup dispatch from native `str`/`int` keys. On the adapted JSON workload, the validated runtime change removes **54.19 million instructions** at 300 iterations, **3.86% versus main**, recovering **51.5% of the instruction excess over alpha.3**. A residual **3.92% instruction excess** remains. The original 70-million-instruction recovery estimate was not achieved.

Timing evidence supports partial recovery with substantial shared-host variation. Against main, median AOT loop time improves 4.51% and warm-JIT loop time 1.90%; paired medians improve 2.85% and 3.75%. Against alpha.3, AOT is near its measured range, while warm JIT still has a residual cost. Combined-source acceptance below confirms substantial typed-loop recovery and preserves the measured JSON residual. The final combined JSON medians remain 3.23% AOT / 6.40% warm JIT above alpha.3, with overlapping ranges; the numeric-heavy reconstructed control remains 7.94% above alpha.3 in instruction count. This report establishes partial recovery, not complete alpha.3 parity. Refs #969 and #976.

## Sources and workload

| Variant | Commit | Tree |
|---|---|---|
| alpha3 | [`f5a09d4223139d7255e31051be97fc509e1ca1fe`](https://github.com/den-run-ai/pystachy/commit/f5a09d4223139d7255e31051be97fc509e1ca1fe) | `8fef058c9a6de7f69b0baaebaaf087a8e39a79ac` |
| main | [`5b49dcfaf639d943a12cbc00ce9117ba3e7b5fcc`](https://github.com/den-run-ai/pystachy/commit/5b49dcfaf639d943a12cbc00ce9117ba3e7b5fcc) | `b98d3faaebab3d57c98a0179b4fc439061522be6` |
| runtime (published) | [`86cedeec314390005e5a5e21dad01373233d2f6b`](https://github.com/den-run-ai/pystachy/commit/86cedeec314390005e5a5e21dad01373233d2f6b) | `491c61ef5894822fbbb5b1cbd52c5a6bfe63565c` |

The measured local runtime commit was `5665d8e916acdcdc4e86180e22510d7a35e6619c`; its tree exactly matches the published runtime commit above.

All three frontends ran under **CPython 3.13.16**, generating native AOT programs and native warm-JIT execution with **LLVM/Clang 18.1.3**. Each checkout supplied its own compiler, library and runtime, with a private warmed runtime cache. No native-compiler throughput or startup comparison is claimed.

The exact input is `bench/pyperformance/json_loads.py`, SHA-256 `51d23d4d8dcc3dea512988ae424988be6bf17d70e9e6d2a09d908799b3319c77`. Its timed loop discards each return value and calls the **typed `json.JSONValue` decoder** inside a program opting into dynamic `Any`. The separate printed witnesses after the loop use the Any JSON adapter. Thus this is not a measurement of an Any-backed decoder loop. The generated IR confirms the timed calls target `f.json$loads`; the witness calls target `f._pystachy_json_any$loads`.

Timing samples use 2,000 outer iterations, three payloads and 20 loads per payload: **120,000 loads**. Callgrind uses the same input with 300 outer iterations: **18,000 loads**. Every build check, warmup, timed sample and profiled execution exits zero and matches pinned CPython stdout exactly. Unprofiled stderr contains only the benchmark timer.

## Method and provenance

The report date uses America/Los_Angeles. The original evidence was collected on 29 October 2026 at 01:42–01:45 UTC, and the forced-inline evidence at 01:50–01:54 UTC: both were on 28 October locally.

Linux 6.18.55, glibc 2.39, AMD EPYC 9V74 80-Core Processor; every measured process is pinned to allowed CPU 0. Valgrind 3.22.0 supplies Callgrind instruction counts. Default optimizations are used, with no GC stress during benchmarks. Inherited `PYSTACHY_*`, `PYTHONPATH` and `PYTHONHOME` are removed; the LLVM path and per-source cache are set explicitly, with `PYTHONHASHSEED=0` and `LC_ALL=C.UTF-8`.

Each timing comparison has seven interleaved pairs after two warmups per variant. Pair order reverses on alternate pairs. The reported timer is inside the generated program loop, excluding frontend work, executable startup, initial cache creation, payload construction and final witness printing. No other session-owned heavy job ran during measurement; external host load and CPU frequency remain uncontrolled. Each comparison is its own series, so candidate medians across comparisons should not be pooled.

The acceptance harness records source commits/trees and actual source-file hashes, rejects dirty sources, and checks that sources remain unchanged. A build manifest binds the metadata hash to each executable and raw IR hash; profiling and timings verify these hashes before and after the stage. Harness SHA-256: `3da53757da16c2c2dd3e7c5634c6a12e1217eb655b25f55467448f8a34fe7df3`.

| Variant | Executable bytes | Executable SHA-256 | Raw program IR SHA-256 |
|---|---:|---|---|
| alpha3 | 224,360 | `899f3983ee6e13fb6979217f554ab60b53ff40a67281d161d135a6e187b3b3d4` | `b78d8e37ba88d0aea14a1f073864e71b05fa7db34e2271ca13c512ff4e64fecc` |
| main | 264,744 | `b90b0ee2e581dcc2b9106c3ea8f25d3d3dd05bc6f29e9625990f6f290b88e8eb` | `79250bbdefc1c9f19b9b8a1e79023e13c4cac0a80e1f8de55789d26fadae6008` |
| runtime | 264,752 | `ea71c91b445a8691f48294ec1d5f239dd1265395c9cea962ca6df46765e28644` | `aac648bcee816ac9ebffd23d958e877a4c937542accf43e895fa3e3737a6320e` |

The candidate executable is eight bytes larger than main and 18.0% larger than alpha.3 on this workload. This is an executable-size observation, not a build-time or memory-use claim. Main and candidate raw program IR differ on exactly one diagnostic-string line: the library checkout path and its three corresponding string-length fields. Applying that exact path/length substitution makes the entire IR identical. No instruction or other content is normalized.

## Instruction counts

Counts below cover the complete AOT process. Function rows are inclusive: the parser includes dictionary and number work, so the rows overlap.

| Counter | alpha.3 | Main | Runtime candidate | Candidate − main |
|---|---:|---:|---:|---:|
| Whole process | 1,300,338,505 | 1,405,529,690 | 1,351,340,704 | -54,188,986 |
| Typed JSON parser (`f.json$_parse`) | 1,153,119,689 | 1,257,772,856 | 1,203,592,912 | -54,179,944 |
| Dictionary insert (`pys_dict_set`) | 215,619,679 | 299,323,173 | 245,137,195 | -54,185,978 |
| Number parser (`m.json$_Parser.number`) | 56,480,923 | 67,944,457 | 67,944,457 | +0 |
| Generic hash dispatch (`hcls`) | 0 | 71,628,000 | 0 | -71,628,000 |
| Generic item hash (`hitem`) | 0 | 70,860,000 | 0 | -70,860,000 |
| Lookup wrapper (`dfind`) | 31,398 | 66,535,090 | 0 | -66,535,090 |
| Compatible probe loop (`dfindc`) | 19,918 | 44,467,990 | 44,467,990 | +0 |
| Runtime integer identity boxing (`pys_dyn_int_box`) | 0 | 90 | 90 | +0 |

Before this fix, dictionary inserts account for about 80% of main’s extra instructions versus alpha.3 and number parsing about 11%. The insertion delta accounts for essentially all of the measured saving. The remaining candidate-to-alpha.3 gap is about 29.52 million instructions in dictionary inserts and 11.46 million in number parsing. The compatible probe loop retains its exact count. Runtime integer identity boxing contributes only 90 instructions in both main and candidate for this complete process.

The change replaces `hcls`/`hitem` dispatch with the existing string/integer hash operations and calls `dfindc` directly after its required nonempty-table check. Hash values, zero/−1 normalization, nullable string behavior, table size, insertion order and probe order remain unchanged. Other key descriptors retain their generic hashing/callback behavior.

| Variant | Callgrind file SHA-256 |
|---|---|
| alpha3 | `60e43f3ce8d7ecabba202a6ed4867df80e3dc0b41a7b5278b40da1faaf96e29a` |
| main | `99ab7cf1e3c5caba5b1a2e419d98f7228806fcc79dd987426899a1e2f98b5132` |
| runtime | `9645c4d723d9f348f9caea17f398fa52fc67dda3446d28785a9ba7ad45be5f87` |

## Paired loop timings

Seconds; median and full observed minimum–maximum.

| Baseline / mode | Baseline seconds | Candidate seconds | Ratio of medians | Median paired ratio | Candidate faster |
|---|---:|---:|---:|---:|---:|
| alpha3 / aot | 0.674036 (0.651690–0.871771) | 0.690669 (0.662810–0.768928) | 1.0247 (+2.47%) | 1.0089 (+0.89%) | 2/7 |
| alpha3 / jit | 0.721277 (0.663322–0.781975) | 0.767995 (0.716709–0.867141) | 1.0648 (+6.48%) | 1.0746 (+7.46%) | 2/7 |
| main / aot | 0.747089 (0.673115–0.823048) | 0.713388 (0.662310–0.925479) | 0.9549 (-4.51%) | 0.9715 (-2.85%) | 4/7 |
| main / jit | 0.788493 (0.729806–0.824230) | 0.773529 (0.713930–0.801873) | 0.9810 (-1.90%) | 0.9625 (-3.75%) | 5/7 |

All observed ranges overlap. The small AOT difference from alpha.3 is inconclusive on this host. Warm JIT remains slower in five of seven alpha.3 pairs, with a median paired overhead of 7.46%; these data do not establish full recovery. The instruction reduction is a separate observation and is not substituted for elapsed-time evidence.

| Pair | AOT / alpha.3 | Warm JIT / alpha.3 | AOT / main | Warm JIT / main |
|---:|---:|---:|---:|---:|
| 1 | 1.07807 | 1.07459 | 0.97151 | 0.90544 |
| 2 | 1.00895 | 1.07266 | 1.05825 | 0.93687 |
| 3 | 1.02704 | 1.16610 | 0.86968 | 0.93449 |
| 4 | 1.00071 | 0.92616 | 0.88652 | 1.07152 |
| 5 | 1.02468 | 0.96511 | 1.00351 | 1.02230 |
| 6 | 0.88203 | 1.08048 | 1.23306 | 0.98883 |
| 7 | 0.96643 | 1.12526 | 0.94868 | 0.96250 |

## Validation and forced-inlining guard

- Full `dictprobe` passes, with worst average **1.93 slots per lookup**, below the 3.0 bound. Its GC-stress checks pass with `PYSTACHY_GC_STRESS=1`.
- New marked-scalar tests compare the optimized path against unchanged generic hashing/probing: exact hashes, table layouts, insertion/hit/miss/deletion probe counts, holes, reinsertion and clear/refill. Inputs include `INT64_MIN`/`INT64_MAX`, zero, −1 normalization, equal hashes, nullable strings, distinct equal strings and cached sentinel values. A cold marked-string case verifies one actual byte hash.
- A deterministic counter requires zero generic hash-dispatch calls for marked str/int keys. A scratch negative control restoring generic dispatch fails that assertion.
- The dictprobe build now rejects an outlined `hobj` definition in optimized LLVM IR. The candidate passes; removing `always_inline` in a scratch negative control produces the definition and fails the guard.
- C syntax with `-Wall -Wextra -Werror` and runtime contracts pass: 579 runtime entries, 70 exception classes and 172 runtime.py functions. `git diff --check` passes.
- Exact-head CI and release gating are tracked in #976. The local checks and performance evidence here do not substitute for the applicable CI matrix on the final published source.

The original candidate `12d99dea2093bd4a4569a7274ab7b645394b8e8d` used only `static inline`; LLVM still emitted `hobj` out of line. Its independent profile was alpha.3 1,300,357,997, main 1,405,555,774 and candidate 1,357,185,562 instructions, recovering 46.0% of the excess. That result prompted the narrowly scoped `always_inline` follow-up and the emitted-IR guard. The original measurements are retained rather than relabeled as results of the final head.

Original candidate timing medians/ranges and ratios:

| Baseline / mode | Baseline seconds | Original candidate seconds | Ratio of medians | Median paired ratio | Faster |
|---|---:|---:|---:|---:|---:|
| alpha3 / aot | 0.668279 (0.609885–0.760986) | 0.705103 (0.656512–0.757925) | 1.0551 | 1.0233 | 2/7 |
| alpha3 / jit | 0.715653 (0.653066–0.861454) | 0.772574 (0.720370–0.924142) | 1.0795 | 1.0794 | 2/7 |
| main / aot | 0.725594 (0.670973–0.968064) | 0.778736 (0.662622–0.932891) | 1.0732 | 0.9238 | 4/7 |
| main / jit | 0.817021 (0.772678–0.862729) | 0.857276 (0.796307–0.969335) | 1.0493 | 1.0473 | 1/7 |

| Pair | Original AOT / alpha.3 | Original warm JIT / alpha.3 | Original AOT / main | Original warm JIT / main |
|---:|---:|---:|---:|---:|
| 1 | 1.11642 | 0.92706 | 0.92378 | 0.95325 |
| 2 | 0.93987 | 1.07941 | 1.06912 | 1.04729 |
| 3 | 1.16553 | 1.22568 | 0.88218 | 1.12357 |
| 4 | 1.05311 | 1.07954 | 0.90494 | 1.10842 |
| 5 | 0.98239 | 1.03280 | 0.91616 | 1.07290 |
| 6 | 1.02329 | 0.87816 | 1.33775 | 1.04218 |
| 7 | 1.01305 | 1.14826 | 1.16061 | 1.03371 |

## Reproduction

Use the exact input bytes and source commits above. Each checkout retains its own library/runtime. Clear inherited result-affecting settings and provide a private cache and LLVM path. Build every variant with the same pinned hosted interpreter:

```sh
python3.13 pystachy.py ir /tmp/json_loads.py -o /tmp/program.ll
python3.13 pystachy.py build /tmp/json_loads.py -o /tmp/json_loads
taskset -c 0 /tmp/json_loads 2000
taskset -c 0 python3.13 pystachy.py run /tmp/json_loads.py 2000
taskset -c 0 valgrind --tool=callgrind --callgrind-out-file=/tmp/callgrind.out /tmp/json_loads 300
```

Check stdout against CPython 3.13.16 for both iteration counts. Warm both execution modes, alternate variant order over seven pairs and extract the internal `seconds` line. Retain full timing ranges, paired ratios, Callgrind outputs and executable/source hashes. The original and forced-inline evidence sets are separate; no sample was discarded from their reported series.

## Combined-source acceptance

The combined identity, module-scoping and runtime source was measured as local commit `aa051bf85554ab7c87884a9b1e1920216f006591`, tree `bba7daabb1d51ed2ac30d32f4169bcad781e2817`. Published #973 head [`d315ace58c7122245670215f12f28bc9cc497833`](https://github.com/den-run-ai/pystachy/commit/d315ace58c7122245670215f12f28bc9cc497833) has that exact tree. These measurements remain associated with their actual source. The final fixture-only follow-up is local `eb11dab661be2fc04147761edb95c3376493bb43`, published as [`9fd73f34a36cfae6196f165628b2ed19fa16538b`](https://github.com/den-run-ai/pystachy/commit/9fd73f34a36cfae6196f165628b2ed19fa16538b), tree `c996c5698c3b201d959cde9e3fc9fff3313cc549`. An exact comparison verifies **all 129 recorded compiler/runtime/library/version source inputs are byte-identical** to the measured tree; both benchmark inputs are unchanged. The only changes are 11 regression-fixture, test-documentation and opt-in-manifest files. `final-source-equivalence.json` preserves every changed path and the source/hash mapping. This supports carrying the performance evidence to that production-equivalent follow-up. Its final PR CI passed all 34 jobs ([run 40807585377](https://github.com/den-run-ai/pystachy/actions/runs/40807585377)); it merged as [`770fe20f`](https://github.com/den-run-ai/pystachy/commit/770fe20ff7c50771b140a918b06843402a456cfa) with the same tree. The [correctness report](release-blocker-correctness-2026-10-29.md#merged-source-ci-and-release-gate) separates this evidence from the exact versioned-main release gate.

The same harness, toolchain, CPU, input hashes, per-source caches, output checks and sampling method apply. JSON uses seven pairs per mode/baseline. Counter uses nine AOT pairs and its exact historical 30-million-iteration source (SHA-256 `74583cdb90fdf990c6862b4129e8c6573088a2373d9de42e3b4138dfb210781e`); its metric includes native process startup because the source has no internal timer. Every execution matches CPython.

JSON loop seconds:

| Baseline / mode | Baseline seconds | Combined seconds | Ratio of medians | Median paired ratio | Combined faster |
|---|---:|---:|---:|---:|---:|
| alpha3 / aot | 0.676921 (0.645093–0.797646) | 0.698787 (0.679241–0.727209) | 1.0323 | 1.0312 | 2/7 |
| alpha3 / jit | 0.708167 (0.671182–0.766846) | 0.753481 (0.709301–0.815989) | 1.0640 | 1.0568 | 1/7 |
| main / aot | 0.698805 (0.661238–0.731141) | 0.692666 (0.654476–0.792384) | 0.9912 | 0.9898 | 4/7 |
| main / jit | 0.828724 (0.764860–1.003900) | 0.820748 (0.682294–1.060858) | 0.9904 | 0.9938 | 4/7 |

| Pair | AOT / alpha.3 | Warm JIT / alpha.3 | AOT / main | Warm JIT / main |
|---:|---:|---:|---:|---:|
| 1 | 1.02811 | 0.99014 | 0.94738 | 1.01632 |
| 2 | 1.04023 | 1.06408 | 1.00441 | 0.83483 |
| 3 | 1.03120 | 1.12416 | 0.98569 | 1.10590 |
| 4 | 0.92946 | 1.07706 | 0.98872 | 0.93302 |
| 5 | 0.91169 | 1.05679 | 1.00221 | 0.99379 |
| 6 | 1.07084 | 1.00476 | 1.17323 | 1.27061 |
| 7 | 1.05233 | 1.05090 | 0.98977 | 0.86333 |

Combined JSON Callgrind totals are **1,351,340,747** instructions versus main **1,405,529,747** and alpha.3 **1,300,338,499**. This is effectively identical to the runtime-only candidate: +3.92% versus alpha.3. The combined raw JSON IR differs from the runtime-only IR on the same one diagnostic checkout-path line and corresponding lengths; no generated instruction changes remain after that exact substitution. Integration adds no measured instruction cost, but also leaves the JSON residual: AOT median +3.23% and warm-JIT median +6.40% versus alpha.3, with overlapping ranges.

Counter/TOML native process milliseconds:

| Baseline | Baseline ms | Combined ms | Ratio of medians | Median paired ratio | Combined faster |
|---|---:|---:|---:|---:|---:|
| alpha3 | 20.874952 (19.102464–23.190422) | 21.911734 (19.408106–32.573852) | 1.0497 | 1.0392 | 2/9 |
| main | 41.770936 (39.146920–46.866723) | 25.354088 (21.519555–32.829839) | 0.6070 | 0.5890 | 9/9 |

| Pair | Counter / alpha.3 | Counter / main |
|---:|---:|---:|
| 1 | 0.96802 | 0.58901 |
| 2 | 1.01600 | 0.55429 |
| 3 | 1.40463 | 0.47468 |
| 4 | 1.35819 | 0.53154 |
| 5 | 1.03918 | 0.52711 |
| 6 | 1.03276 | 0.60193 |
| 7 | 0.95694 | 0.79867 |
| 8 | 1.06285 | 0.76877 |
| 9 | 1.09745 | 0.75473 |

The typed-loop regression is substantially repaired: all nine comparisons against main are faster. The alpha.3 and combined ranges overlap; their small median difference is inconclusive on this short process-level metric. Deterministic IR confirms the intended mechanism: alpha.3 and combined both have `Counter` layout `{i64, i64}` and a 54-line `Counter.step` body; main has `{i64, i64, ptr, ptr}` and a 75-line body. All three bodies have zero direct integer-box calls, reflecting main’s earlier lazy-field work; the removed companion fields/bookkeeping are the relevant remaining difference.

| Workload / variant | Executable bytes | Executable SHA-256 | Raw IR SHA-256 |
|---|---:|---|---|
| JSON / alpha3 | 224,360 | `899f3983ee6e13fb6979217f554ab60b53ff40a67281d161d135a6e187b3b3d4` | `b78d8e37ba88d0aea14a1f073864e71b05fa7db34e2271ca13c512ff4e64fecc` |
| JSON / main | 264,744 | `b90b0ee2e581dcc2b9106c3ea8f25d3d3dd05bc6f29e9625990f6f290b88e8eb` | `79250bbdefc1c9f19b9b8a1e79023e13c4cac0a80e1f8de55789d26fadae6008` |
| JSON / combined | 264,752 | `4ccb54bf40ac1da9a42f87da78e5a6d3494a150275b91df1185abb8e9e9bac48` | `7a46aeaf858b0e3b31075ebf01209e9fce8c779b8750872fe28bf48c840ab2eb` |
| Counter / alpha3 | 551,392 | `7a95b8e78acb1bed2b16959b3ec69f75241b9cba8c0a602ce1cf79d4ca80cfe1` | `4cbfa3f1f34c8bc7af830b32579e53fd4a681e78b79345180a8c5ca8913c69ad` |
| Counter / main | 693,224 | `c5ce7447ede9b65943f7b0a80ca15c266b1513d1a3924e1af4863ebe191e3a2c` | `ade382a93df0b96c9f9dd1f5a8cb016fb0a192fbce43a2759fa92f5974124885` |
| Counter / combined | 697,352 | `2b0ff66c4261a27fd428d0e97320936e50cf674e102fd00efafd9aed95b9e942` | `4e51611a4bd33a54274410f53830e0beb9164176ce0634375cb48ea719fa302b` |

## Reconstructed 32-key integer JSON control

This is a newly reconstructed bounded control, **not a replay of the unavailable historical 124-million-instruction input**. Its source hash is `d02a1bacd6be31de87de758758ee3a3ee18f581894e80f924000cd6357c37510`. It uses one fixed 343-byte JSON object with keys `k0`…`k31` and integer values 1000…1031, and 3,000 discarded typed `json.loads` calls inside a dynamic-Any program. A separate Any-backed witness load/print follows the loop. The entire source and all command/output/hash records are retained with the research evidence.

Only instruction counts are evaluated for this additional control; its profiled timer is not a speed claim. AOT and JIT build/output checks match CPython.

| Variant | Complete-process instructions | Relative to alpha.3 | Callgrind SHA-256 |
|---|---:|---:|---|
| alpha3 | 91,425,414 | 1.0000 | `711753d8bc103c548eb8bbe1b1149ea18adb73443c0b07e0edf8bf9952f8bcd8` |
| main | 105,380,306 | 1.1526 | `0ced517b3c87fcf87e25591bf3ae9d71eecfd1f1d709c20d6baf809fd9fdee45` |
| combined | 98,680,619 | 1.0794 | `715073595fb71655a731668665e19bec34987745f58bdd6cadf85a5348c8c090` |

The combined control improves 6.36% versus main but remains **7.94% above alpha.3**. Its dictionary-insertion cost falls from 29,099,773 to 22,400,012 instructions (alpha.3 19,466,807); number parsing remains 21,325,946 (alpha.3 17,410,977). This independently demonstrates a residual cost on a numeric-heavy decoder input, while preserving the distinction between this reconstructed case and the historical unavailable source.

## Bounded scalar-probe trial rejected

After measuring the residual, a separate local trial `29acda6949ab904e3cf55ff1ee3142e7a01d2906` (tree `d56a52215c7a5a29ad7412924e8111282b5d24c6`) specialized `dfindc` for marked native str/int keys. It reused the same `dlook` recurrence, mask, identity-first check and collision free-slot reprobes, replacing generic equality dispatch with direct scalar comparisons. An independent source review found no correctness issue. Its enhanced probe reference forced the original general loop; exact layout/hash/probe checks, full dictprobe, native GC stress, runtime contracts and both AOT/JIT stdout checks passed. Restoring the generic dispatcher in a scratch negative control failed the new no-generic-equality assertion.

The trial was **rejected**: at 300 JSON iterations, whole-process instructions increased **1,351,366,723 → 1,361,638,491 (+10,271,768; +0.76%)**. The compatible lookup function increased **44,467,990 → 54,765,640** instructions. Both executables were 264,752 bytes. No paired timing series was run for this losing trial, and no trial code was integrated into the release source. Its complete diff, source/input/build hashes and profile summaries are retained on the research evidence path for reproducibility.

The accepted result remains the small hashing/direct-probe change with forced inlining. It fixes the intended dispatch overhead and recovers part of the JSON regression; the remaining measured costs and shared-host timing limits above are retained explicitly.


## Archived evidence

The [immutable research evidence directory](https://github.com/den-run-ai/pystachy/tree/717ae5852f30a4f70cf5ba36cda359fbf99d36cf/research/release-blocker-2026-10-29)
contains the retained inputs, harnesses, source manifests, timings and profile summaries.
`runtime-final.tar.gz` is 352,278 bytes, SHA-256
`1a0832e5eb656e85b5da59037fa78205fc6d603a01d08e41b802f5f864310ba2`.
The archive excludes caches, executables and full Callgrind data; their recorded hashes and
reproduction inputs remain available. Raw research stays on that branch, outside main.
