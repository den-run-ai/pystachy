# Bulk byte scanning: source, measurements and validation

Evidence for [PR #1004](https://github.com/den-run-ai/pystachy/pull/1004), measured 1 November 2026. Refs #862, #1003.

**Status: draft, with a performance hold.** All 40 applicable CI checks pass on `d056aafe`; the conditional fork-only DCO check is skipped. The final campaign finds a clear **18.17% slowdown in the AOT dense-escape repair workload** (34.861 → 41.193 ms for 300 calls), with all five pairs slower and non-overlapping process-median ranges. This PR is not proposed for merge until that cost is addressed or explicitly accepted.

The reusable native helper scans eight bytes at a time for either of two byte values or a byte below a threshold. JSON's ordinary-string and post-escape spans share it; a 16-byte scalar prefix keeps short spans out of the native helper. This is an explicit internal primitive with a CPython-valid scalar implementation, not automatic optimization of arbitrary Python loops. Thresholds 0..128 use the word path; higher valid thresholds use the scalar fallback. The malformed-input JSON-repair accumulator is unchanged. The scalar helper explicitly computes its returned offset, so direct, keyword and Callable forms agree on uncached numeric identity. The native boundary uses the existing scalar-read mechanism and ordinary coercions without creating unused argument identity companions.

On the full campaign, long valid strings improve about 1.84–2.13× in native JIT/AOT, sparse escapes about 1.8–2.0×, and raw Unicode about 1.2–1.3×. The integrated integer-fix build retains the long-string and sparse-escape gains. These results do not establish a universal engine ranking or zero short-input cost. All slower medians and outliers are retained below; focused follow-up and profiling are recorded separately.

## Source and environment

| Item | Identity |
|---|---|
| Main baseline | `07b26e02425d023288ed95a9d2a5077be5aeb45e` |
| Measured scanner source | `d056aafe2f0c09d72ca23bf14b18123d1e439170` |
| Measured scanner tree | `d8391c0c9af4e189634bb6d495de85c5b23cc167` |
| Candidate compiler bootstrap source | `d056aafe2f0c09d72ca23bf14b18123d1e439170`; compiler and runtime sources match the measured source |
| Integer-fix source | PR #1003 `dceda23e8b71311c43e5c843698ed4443292004b` |
| Combined JSON source SHA-256 | `5b267b3b1ddf373c289c92308459d68ea016b83f0f1dda41918f7b61aea0307b` |
| Machine | Shared Linux x86-64, Intel Xeon Platinum 8573C; timed process pinned to CPU 0 |
| Toolchain | Clang/LLVM 18.1.3; CPython 3.13.16; PyPy 8.0.1 / Python 3.11.17 |

This is a different machine and source from the historical AMD measurements in #862. Executable and source hashes are in `boundary-measurement-metadata.json`. Each native compiler used its own resource home and port directory. The common benchmark source is `bench/extended/json_scan.py` at the measured scanner commit, including when building/running the baseline and integration variants.

## Method and retained data

Eight variants ran in five independent processes each, with rotated variant order: baseline/candidate AOT, baseline/candidate JIT, CPython, PyPy, integer-fix AOT, and integer-fix-plus-scanner AOT. Each case validates a separately constructed full expected value before and after execution, consumes every result in the timed loop, and checks every batch checksum. Three warmup batches precede seven timed batches. One first batch is retained separately, after initial correctness validation. Reported values are medians of process medians; no sample or process outlier is discarded.

All 40 processes exited successfully: 715 validated process/case combinations and 5,005 retained timed batches. Native direct mode uses dynamic JSON; typed JSON shares the implementation and has separate correctness coverage. The repair facade is the same maintained adapted port under each engine, not unchanged upstream on every interpreter. Long cases have value lengths 4,096/8,192/16,384; source JSON adds eight characters. Short is a fixed eight-character value; mixed is a fixed small heterogeneous object. Sparse escapes contain four long ordinary spans, dense escapes repeat `a\nb`, Unicode repeats `é中😀a`, and the malformed case has a raw control at the end of the value.

Compilation/startup is outside batch timing. Whole-process wall times include startup, all cases and validation and are not isolated startup measurements. No startup performance claim is made. Separate profiling and memory observations are excluded from throughput timings. This campaign's build, test and profiling jobs did not overlap the timing window; the host itself is shared.

PyPy's exact direct-control diagnostic is one character earlier than the CPython oracle, so that one case is excluded for PyPy only. The oracle was not weakened; PyPy still runs the corresponding repaired-value case. PyPy's first 4 KiB direct case also has a wide process range, so it should not be used as a steady-state engine-ranking claim.

## Main baseline → scanner: AOT

Batch milliseconds; each estimate is the median of five process medians. Ranges contain every process median. Positive change means slower.

| API / case | Calls | Before ms [range] | After ms [range] | Time change | Speedup |
|---|---:|---:|---:|---:|---:|

| direct / long 4096 | 2,000 | 22.718 [21.307–23.249] | 12.026 [11.068–16.299] | -47.1% | 1.89× |
| direct / long 8192 | 2,000 | 42.589 [40.413–45.333] | 21.410 [20.633–22.541] | -49.7% | 1.99× |
| direct / long 16384 | 2,000 | 82.586 [79.815–83.524] | 40.130 [38.825–41.319] | -51.4% | 2.06× |
| direct / short | 200,000 | 71.450 [69.283–86.337] | 71.854 [70.226–72.829] | +0.6% | 0.99× |
| direct / mixed | 40,000 | 29.884 [29.168–37.022] | 29.787 [29.088–30.832] | -0.3% | 1.00× |
| direct / sparse | 3,000 | 68.661 [67.046–72.442] | 35.128 [34.035–36.821] | -48.8% | 1.95× |
| direct / dense | 300 | 41.167 [36.230–42.711] | 42.122 [41.905–43.593] | +2.3% | 0.98× |
| direct / unicode | 300 | 36.618 [35.686–38.126] | 29.014 [28.250–29.462] | -20.8% | 1.26× |
| direct / control | 300 | 37.595 [35.196–39.444] | 35.342 [34.828–37.588] | -6.0% | 1.06× |
| repair / long 4096 | 2,000 | 21.886 [20.503–22.537] | 10.870 [9.823–11.067] | -50.3% | 2.01× |
| repair / long 8192 | 2,000 | 42.119 [41.443–47.053] | 20.143 [18.880–21.623] | -52.2% | 2.09× |
| repair / long 16384 | 2,000 | 83.846 [80.581–86.055] | 39.297 [38.153–39.704] | -53.1% | 2.13× |
| repair / short | 200,000 | 71.087 [70.245–73.411] | 72.288 [71.190–74.475] | +1.7% | 0.98× |
| repair / mixed | 40,000 | 29.584 [26.888–31.388] | 31.634 [30.043–33.908] | +6.9% | 0.94× |
| repair / sparse | 3,000 | 68.204 [65.745–72.124] | 35.040 [33.363–36.269] | -48.6% | 1.95× |
| repair / dense | 300 | 34.861 [34.756–37.581] | 41.193 [39.597–44.544] | +18.2% | 0.85× |
| repair / unicode | 300 | 36.486 [35.244–37.379] | 29.030 [27.251–32.874] | -20.4% | 1.26× |
| repair / control | 100 | 33.937 [30.406–34.452] | 29.495 [29.014–36.498] | -13.1% | 1.15× |

## Main baseline → scanner: JIT

Batch milliseconds; each estimate is the median of five process medians. Ranges contain every process median. Positive change means slower.

| API / case | Calls | Before ms [range] | After ms [range] | Time change | Speedup |
|---|---:|---:|---:|---:|---:|

| direct / long 4096 | 2,000 | 22.496 [21.250–23.634] | 12.218 [11.379–14.098] | -45.7% | 1.84× |
| direct / long 8192 | 2,000 | 42.065 [39.972–43.893] | 21.066 [19.902–23.440] | -49.9% | 2.00× |
| direct / long 16384 | 2,000 | 82.877 [81.512–84.893] | 39.859 [38.503–46.326] | -51.9% | 2.08× |
| direct / short | 200,000 | 90.644 [87.924–143.265] | 87.063 [85.264–93.570] | -4.0% | 1.04× |
| direct / mixed | 40,000 | 40.883 [39.517–55.979] | 43.191 [41.904–46.861] | +5.6% | 0.95× |
| direct / sparse | 3,000 | 69.405 [67.930–74.354] | 35.841 [34.096–37.918] | -48.4% | 1.94× |
| direct / dense | 300 | 46.757 [45.735–48.218] | 47.212 [44.541–51.176] | +1.0% | 0.99× |
| direct / unicode | 300 | 36.748 [36.250–37.902] | 28.688 [26.615–29.826] | -21.9% | 1.28× |
| direct / control | 300 | 50.406 [49.186–61.080] | 42.917 [42.193–47.120] | -14.9% | 1.17× |
| repair / long 4096 | 2,000 | 22.714 [21.177–23.765] | 10.670 [9.974–12.695] | -53.0% | 2.13× |
| repair / long 8192 | 2,000 | 42.148 [40.808–58.384] | 20.755 [19.607–22.274] | -50.8% | 2.03× |
| repair / long 16384 | 2,000 | 81.835 [80.455–86.645] | 41.016 [40.470–41.188] | -49.9% | 2.00× |
| repair / short | 200,000 | 87.201 [86.017–89.898] | 92.103 [89.150–95.478] | +5.6% | 0.95× |
| repair / mixed | 40,000 | 43.147 [41.831–45.735] | 43.609 [42.098–49.963] | +1.1% | 0.99× |
| repair / sparse | 3,000 | 68.704 [68.010–77.326] | 37.145 [35.745–41.065] | -45.9% | 1.85× |
| repair / dense | 300 | 47.338 [45.686–54.624] | 46.922 [44.511–53.566] | -0.9% | 1.01× |
| repair / unicode | 300 | 35.433 [34.807–43.079] | 29.913 [28.084–36.897] | -15.6% | 1.18× |
| repair / control | 100 | 35.041 [34.051–36.124] | 34.639 [32.722–35.579] | -1.1% | 1.01× |

## Integer fix alone → integer fix plus scanner: AOT

Batch milliseconds; each estimate is the median of five process medians. Ranges contain every process median. Positive change means slower.

| API / case | Calls | Before ms [range] | After ms [range] | Time change | Speedup |
|---|---:|---:|---:|---:|---:|

| direct / long 4096 | 2,000 | 23.144 [22.225–23.969] | 11.806 [10.675–16.305] | -49.0% | 1.96× |
| direct / long 8192 | 2,000 | 41.949 [40.430–63.178] | 20.136 [19.555–21.450] | -52.0% | 2.08× |
| direct / long 16384 | 2,000 | 86.417 [83.631–100.943] | 39.450 [38.608–42.866] | -54.3% | 2.19× |
| direct / short | 200,000 | 68.543 [67.829–74.156] | 73.808 [71.751–79.907] | +7.7% | 0.93× |
| direct / mixed | 40,000 | 29.192 [28.445–29.432] | 30.778 [30.173–36.128] | +5.4% | 0.95× |
| direct / sparse | 3,000 | 71.534 [67.373–90.376] | 35.537 [35.192–42.187] | -50.3% | 2.01× |
| direct / dense | 300 | 36.633 [36.431–38.890] | 38.279 [36.594–39.059] | +4.5% | 0.96× |
| direct / unicode | 300 | 37.276 [36.699–42.607] | 28.161 [26.938–29.167] | -24.5% | 1.32× |
| direct / control | 300 | 41.457 [36.657–43.163] | 37.464 [33.842–39.366] | -9.6% | 1.11× |
| repair / long 4096 | 2,000 | 21.866 [21.392–23.710] | 11.618 [10.344–13.585] | -46.9% | 1.88× |
| repair / long 8192 | 2,000 | 42.924 [40.992–45.221] | 21.619 [19.327–22.426] | -49.6% | 1.99× |
| repair / long 16384 | 2,000 | 82.720 [79.862–84.108] | 38.807 [37.677–42.250] | -53.1% | 2.13× |
| repair / short | 200,000 | 73.949 [70.758–89.108] | 75.607 [74.226–77.386] | +2.2% | 0.98× |
| repair / mixed | 40,000 | 30.533 [29.228–36.795] | 31.538 [29.219–37.412] | +3.3% | 0.97× |
| repair / sparse | 3,000 | 73.267 [67.223–73.987] | 37.123 [36.299–46.519] | -49.3% | 1.97× |
| repair / dense | 300 | 34.687 [33.947–43.580] | 37.570 [35.270–42.263] | +8.3% | 0.92× |
| repair / unicode | 300 | 37.286 [36.677–44.636] | 28.166 [26.564–29.508] | -24.5% | 1.32× |
| repair / control | 100 | 31.872 [30.141–32.539] | 29.199 [28.340–29.473] | -8.4% | 1.09× |

## Same-source engine controls

These are warmed batch milliseconds, including each engine's decoder implementation. Only directly comparable valid cases are shown here; the archive contains all samples.

| API / case | Calls | Native AOT before | Native AOT after | CPython | PyPy |
|---|---:|---:|---:|---:|---:|

| direct / long | 2,000 | 42.589 | 21.410 | 21.302 | 6.384 |
| direct / short | 200,000 | 71.450 | 71.854 | 213.677 | 39.623 |
| direct / mixed | 40,000 | 29.884 | 29.787 | 72.018 | 19.188 |
| direct / sparse | 3,000 | 68.661 | 35.128 | 34.707 | 66.173 |
| direct / dense | 300 | 41.167 | 42.122 | 14.343 | 10.930 |
| direct / unicode | 300 | 36.618 | 29.014 | 5.823 | 7.079 |
| repair / long | 2,000 | 42.119 | 20.143 | 20.713 | 5.883 |
| repair / short | 200,000 | 71.087 | 72.288 | 254.675 | 40.710 |
| repair / mixed | 40,000 | 29.584 | 31.634 | 78.377 | 18.718 |
| repair / sparse | 3,000 | 68.204 | 35.040 | 33.824 | 67.465 |
| repair / dense | 300 | 34.861 | 41.193 | 13.481 | 10.743 |
| repair / unicode | 300 | 36.486 | 29.030 | 5.694 | 7.458 |

At 8 KiB, PyPy remains faster than the candidate on direct decoding and the valid-input repair facade; the table gives the exact comparison. The optimization narrows this workload's gap. Dense escapes and Unicode still have substantial decoder costs beyond scanning. GraalPy was not measured.

## Final instruction and memory diagnostics

Callgrind 3.22.0 collected only two `batch()` calls per invocation (the separately reported first batch plus one measured batch), excluding setup/validation. These runs are separate from throughput measurement. Counts describe the AOT binaries; they do not establish JIT instruction costs.

| AOT case | Baseline instructions | Candidate instructions | Change |
|---|---:|---:|---:|
| direct / long | 434,431,956 | 257,021,931 | -40.84% |
| repair / long | 434,630,167 | 257,220,142 | -40.82% |
| direct / short | 142,353,701 | 146,554,084 | +2.95% |
| repair / mixed | 54,972,352 | 58,212,352 | +5.89% |

For the long-string control, the baseline spends roughly 53% of collected instructions in the string path containing the scalar scan. After bulk scanning, UTF-8 encoding and decoding together account for roughly 64% of remaining instructions. This identifies substantial remaining work outside delimiter scanning; no application-speedup claim is derived from instruction counts alone.

Separate `PYSTACHY_GC=stats` and per-process RSS probes compare all four AOT sources. At each matched case, collection counts and rounded heap peaks agree: 29.1 MiB for direct 4 KiB strings, 7.1 MiB for direct 16 KiB strings, 8.1 MiB for repair 8 KiB strings, and 35.4 MiB for dense strings. These peaks vary with allocation classes and collection timing, so the different sizes are not a linear retained-memory series. RSS samples are retained but are not a precise allocation counter. The native scanner itself performs zero allocations, as checked by the dedicated C probe.

The source-level limit checks and changed AOT inlining remain plausible contributors to short-input costs. The earlier AOT `plain_end()` grew to 617 bytes; the final boundary correction reduces it to 393 bytes and removes its unused numeric-boxing paths, but it remains out of line in the measured AOT binary. This improvement does not erase the measured short/mixed costs or the dense-escape performance hold.

## Correctness, compiler and native safety evidence

- Both baseline and candidate compiler builds reached a three-stage fixed point. Compiler IR counts were 775,228 → 775,537; runtime.py IR was 18,805 lines in both. The final boundary correction was included in this compiler bootstrap; runtime C code is unchanged from the initial scanner implementation.
- The native scalar-oracle probe passes **1,294,979 checks**, covering all byte values, 32 alignments, short tails, thresholds 0 through 256, delimiters, subranges, invalid arguments, metadata preservation and guard pages. Normal and per-allocation-GC variants pass. The same probe passes combined ASan/UBSan in both modes. C boundary/runtime/probe have ASan+UBSan; generated runtime.py IR has ASan coverage, following the repository's sanitizer path.
- Ordinary 4/8/16 KiB spans take exactly 512/1,024/2,048 word probes and zero scalar probes. The helper performs no allocation. A deliberately scalar-only control passes correctness and fails the word-work assertion, proving that the test detects loss of bulk scanning.
- Five new differential programs cover generic scanning, user-module shadowing, typed JSON and dynamic JSON. Final boundary tests pass hosted JIT/AOT normally and with collection at every program allocation (20 checks). The added fixture checks identity parity across direct/keyword/Callable forms, argument order, aliases and later mutations. An earlier 30-program selection passed 60 ordinary JIT/AOT checks; its source identity is separately labeled in the validation manifest.
- Combined #1003 integration passes its six new regression programs plus both scanner JSON programs and the new scanner identity/effects fixture in JIT/AOT with per-allocation GC and IR checking: **18/18**. This validates coexistence with that pinned integer/comment/recursion change; it does not substitute for that PR's independent review.
- Final measured-source IR comparison completes all **3,909 inputs**: 2,122 accepted by both, 1,784 rejected by both, three newly accepted scanner fixtures, **zero new rejections**. Of 271 raw differences, 176 are proven installation-path/string-length changes, 60 diagnostic path changes, 31 intended JSON/repair scanner changes, three new fixtures, and one unchanged rejection with a source-line shift. Compiler self-IR and runtime.py IR are identical. The harness's nonzero mismatch status is fully accounted for; it is not presented as a zero-difference run.
- `make check-fast`, lint/typecheck, runtime signature/effect contracts and focused IR contracts pass. CI is reported independently on the PR at its exact head.

The final compiler and source manifests stayed unchanged during the full comparison. Its one unchanged rejection moves the JSON source location from line 536 to 551.

The full retained evidence distinguishes completed runs from an earlier interrupted 1,468-case IR comparison. The interrupted run is not counted as full validation. An initial hybrid prefix using `min()` was rejected after CI exposed identity-inert numeric-list construction. The final comparison-based prefix passes all 17 identity-scope checks; no expectations were relaxed. Earlier unpaired/pilot timings are not used for speedup claims.

## Reproduction

Build clean baseline and candidate worktrees with the pinned LLVM and Python versions. Compile the **same candidate benchmark source** with each native compiler while selecting that compiler's own home and ports. For example, with `BASE`, `CANDIDATE` and `BENCH` set to those absolute paths:

```sh
PYSTACHY_HOME="$BASE" PYSTACHY_PATH="$BASE/ports" "$BASE/pystachy" build "$BENCH" -o scan-base
PYSTACHY_HOME="$CANDIDATE" PYSTACHY_PATH="$CANDIDATE/ports" "$CANDIDATE/pystachy" build "$BENCH" -o scan-candidate
taskset -c 0 ./scan-base suite all 4096 1 3 7
taskset -c 0 ./scan-candidate suite all 4096 1 3 7
```

Use the retained `measure-scanner-boundary.py` and `boundary-final-plan.json` to rotate all eight variants across five independent processes; adjust workspace paths only. The plan contains explicit JIT homes, ports and cache directories. `profile-scanner-final.py` is a separate instrumented run and must not overlap the throughput campaign. `integration-source.patch` records the combined implementation against the pinned integer-fix source; its benchmark was still the shared measured-source driver.

Raw data and diagnostic scripts are in [evidence.tar.gz](evidence.tar.gz); a compact final summary is in [summary.json](summary.json). They are stored on this research branch only. They are not part of the implementation PR or intended for merging to main.


## Validation history and limits

The archive keeps the superseded `a4cad8bb` campaign and its longer focused repeats separately. Those repeats found approximately 6–8% costs on the then-current JIT short/mixed and integrated dense cases. The final source changes those results: use the final tables above, including the +18.17% AOT repair-dense case, rather than treating the older focused estimates as final. The boundary correction also fixed the newly introduced helper's direct/keyword/Callable numeric-identity mismatch before the final measurements.

The #1003 integration was a deliberately patched worktree; its old checkout HEAD alone does not identify the tested source. Complete before/after consumed-source manifests, the integration implementation patch, integrated JSON snapshot, compiler identity and executable hashes are retained. The final integrated JSON SHA-256 is `5b267b3b1ddf373c289c92308459d68ea016b83f0f1dda41918f7b61aea0307b`.

## Archive contents

The public archive retains every benchmark sample, all comparison accounting, complete compiler mismatch diffs, diagnostic streams and exit statuses. It excludes 417 supplementary full LLVM modules (442.1 MiB uncompressed), which can be regenerated from the retained source identities, corpus and commands. No timing sample, failure, rejection or mismatch diff is excluded. Current final-source data uses the `boundary-` names; superseded measurements are isolated under `superseded-a4/`.

The 207 baseline and 210 candidate retained-IR counts in `irsame/accounting.json` describe the local comparison run; the public archive includes their complete mismatch diffs and diagnostics, with the supplementary modules excluded as stated above.

Archive SHA-256: `b60ed2f961615e3cfe88b44a9349ab6d625f6e099d71b41d54c4e81a2d6eca4a`.
