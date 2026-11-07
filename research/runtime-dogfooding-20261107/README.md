# Runtime subset migration: local validation evidence

**Local validation completed for the integrated source and its scalar follow-up; full verification remains pending.** The original core passed bootstrap, contracts, ABI checks, focused executions, generated-runtime AddressSanitizer checks and native numeric probes. Its 4,245-case compiler IR comparison was completely classified, with the expected differences documented below. The final scalar follow-up at `263bd32d3c64193c58127ef51e432de7d44db7da` passed a fresh bootstrap, 104 focused executions, 12 ASan program executions, 604,985 hosted runtime cases and 137,781 native numeric cases. The unchanged compiler binary and an exact incremental runtime comparison connect the original corpus audit to this final source. **This is not a fresh rerun of all 4,245 cases, and `make verify` has not run.**

This repository-independent bundle is intended for the separate `research/runtime-dogfooding-20261107` evidence branch. Source links identify the published source commit `975e9c0b99c2717f3b26488e25e0638bde214f7f`. Historical logs and JSON retain their original paths and hashes; relative links below identify the copied records. The maintained workload and final reproducible benchmark report belong beside `bench/runtime_subset/` in the source branch. The restarted final benchmark completed successfully: all eight workloads, seven alternating pairs, pinned to CPU 8. Its maintained [final report][bench-final] and [method/interpretation][bench-readme] are linked from the source commit. No universal performance parity or CI result is claimed.

## Revisions and environment

| Item | Recorded identity |
|---|---|
| C baseline | `f7103067545b43cdcd8ce20dc66b1571425b3a8d` |
| Integrated compiler/runtime used by the native numeric probe | `93c1284cafb454ee1531c422012ea9181bcbf0cd` |
| Candidate checkout when IR classification finished | `5c4bb5916a2425752670875add03062e0b54d7a2` |
| Changes between the original integrated revision and original IR classification | Only `bench/runtime_subset/compare.py` and `workload.py`; compiler, runtime, library and corpus sources remained unchanged |
| Final validated compiler/runtime source | `263bd32d3c64193c58127ef51e432de7d44db7da`; subsequent `3b314bb3` changes only the benchmark docstring |
| Published source commit | `975e9c0b99c2717f3b26488e25e0638bde214f7f` |
| Published source tree / equivalent local commit | Tree `53c750a7b12d702e18d89fa498c457ea9f182b0b`; exactly matches local `c5d5fe3168608c2429b5bcc8345130cf62da9f31` |
| Provenance of published files | Core validation at `263bd32d`; benchmark at `3b314bb3`; the equivalent final local commit adds benchmark/numeric result files and documentation only |
| Platform/toolchain | Linux x86-64, LLVM/Clang 18.1.3, pinned CPython 3.13.16 |
| Native compiler SHA-256, baseline | `3b59b4e875a89f15777395f5993ccf2e6d51e934dbc7a4e45228d622c7f1cff7` |
| Native compiler SHA-256, candidate | `793c313f8f580349f9fcd9a9f36a9a3d8847ed3187ddba94204747e37c3b3a23` |

The [IR classification][classification] and [native numeric report][numeric] retain source identities, tool versions, input/output hashes, and their respective limits. These local results do not establish CI status for a subsequently published head.

## Completed original-core checks and what they establish

| Check | Recorded result | Meaning and limit |
|---|---|---|
| Native bootstrap | Baseline and corrected candidate passed compiler **and** runtime three-stage IR fixed points. Candidate: 833,502 compiler IR lines; 19,885 runtime IR lines. | Both native stages reproduce the hosted compiler's output for these sources. This is a bootstrap result, not the complete execution matrix. [Baseline log][baseline-build]; [corrected candidate log][build]. |
| Runtime contracts | 644 entries, 70 exception classes, 181 runtime functions; signatures/effects agree, with no lowering-induced call cycles. | Checks the C/subset/compiler interface, including ASCII's explicit `R A` effect declaration. [Log][contracts]. |
| Runtime ABI | 146 runtime functions, 19,130 uses in C and 2,364 programs; zero mismatches. Also checked 33 FFI C-glue calls. | Checks native signature widths and string layout across runtime parts and generated calls. It does not execute every program. [Log][abi]. |
| Hosted runtime differential checks | **604,985 cases; zero failures.** | Exercises `runtime.py` algorithms against independent CPython/reference behavior, including new raw-byte ASCII cases. CPython execution alone does not prove native code generation or 64-bit overflow behavior. [Log][rtcheck]. |
| Native differential corpus subset | 34 selected programs × JIT/AOT = **68 passes**. | Covers new fixtures plus relevant math, sums, range, power, representation, promoting-int and upstream regressions. [Selectors][selectors]; [log][native]. |
| Program-only GC stress | Six new fixtures × JIT/AOT = **12 passes** with `PYSTACHY_GC_STRESS_PROGRAM=1`. | Exercises these fixtures during frequent collections, not the full GC suite. [Log][gc]. |
| Range optimization disabled | Six fixtures × JIT/AOT = **12 passes** with `PYSTACHY_OPT=-listget`. | Checks agreement when the affected optimization is disabled. Other optimizations remain enabled. [Log][opt-off]. |
| CPython-hosted compiler | Six fixtures × JIT/AOT = **12 passes**. | A second compiler execution route for the same native programs. [Log][hosted]. |
| AddressSanitizer programs | Six JIT and six AOT fixtures = **12 passes** after correcting runtime loading. | Covers the migrated runtime and optimizer fixtures under ASan; see the initial failure below. [JIT log][asan-jit]; [AOT log][asan-aot]. |
| Generated-runtime ASan harness | Three tests passed. | Includes cached subset instrumentation and an external-string overread control whose uninstrumented version misses the overread. [Log][asan-harness]. |
| Focused IR validity | Six programs accepted by the typed IR checker and `llvm-as`. | Structural validity for selected probes, not native correctness of the full corpus. [Log][check-ir]. |
| Maintained fast/lint/recording checks | `make check-fast`, lint, and recording checks passed; 2,148 CPython recordings, 122 deviations and 11 vendored files checked without failures. | Includes Ruff, mypy, hosted compiler unit tests, C warnings, shell checks, and GC-root annotations. Recorded expectations remain CPython-derived. [Fast checks][fast]; [lint][lint]; [recordings][recordings]. |

The focused execution aggregate is **104 passes**: 68 native + 12 GC-stressed + 12 affected-optimization-disabled + 12 hosted-compiler executions. The **12 ASan program executions are additional**. These are program/mode executions, not 116 distinct programs. The three ASan harness tests and the numeric helper cases below are separate evidence.

## Failed attempts retained in the record

**Initial bootstrap failed.** The first candidate build reported `expected Val, got Ins` in `optimizations.py:562`. A loop reused `s` for both sequence values and slot instructions, which CPython permitted but the compiler's supported subset rejected. Commit `b7e58608` renamed the slot variable without changing the proof. The corrected full `make` passed both three-stage fixed points. The initial failure remains in [candidate-build.log][build-failed]; it is not counted as a successful build.

**Initial ASan program harness setup failed.** The JIT runtime-cache preparation reported an undefined `__asan_option_detect_stack_use_after_return` symbol because the ASan runtime was not preloaded. No program pass is credited to that attempt. With the matching LLVM 18 ASan shared library in `LD_PRELOAD`, all six JIT fixtures passed. Six AOT fixtures were then built and run individually with ASan, without `LD_PRELOAD`, comparing their recorded input/output. [Initial failure][asan-failed]; [corrected JIT][asan-jit]; [corrected AOT][asan-aot].

## Complete IR comparison: differences explained, not a raw pass

The original oracle reported **272 differences among 4,245 cases**, with 3,973 identical cases. All retained differences were classified by complete output comparison:

- **Nine cases:** 13 checked list reads replaced by proven direct loads; one also had checkout-path differences.
- **Four cases:** six ASCII calls gained exception edges after declaring its explicit size-error effect; one also had checkout-path differences. Associated value/block renumbering was checked exactly.
- **259 other cases:** 246 had only generated checkout-path IR differences; 13 had only diagnostic source-location differences.

There were **zero unexplained cases, exit-status differences, one-sided IR outputs, missing reports, or new rejections**. Both checkouts used their own libraries; the library Git tree and all 90 common files matched. No shared compiler home or broad text normalization was used. Two `sed` broken-pipe warnings occurred in the reporting pipeline; every case report was present, and classification used the retained complete outputs. The original harness retained equal-status conclusions rather than each individual equal numeric exit code. The archived [comparison harness][irsame-method], [classification script][classification-method] and [case map][case-map] preserve the method. Large retained IR pairs and native executable files are intentionally outside this text/source evidence bundle; the classification includes their hashes and full-output comparison conclusions.

This compares the two compilers on the same current corpus, including the current `runtime.py`; the implementation-value oracle is separate. **The unmodified IR comparison did not pass byte-for-byte.** [Raw log][irsame]; [classification and method][classification].

## Independent native numeric contract

The maintained `bench/runtime_subset/numeric_contract.py` probe passed **137,781 checks** against the original C helpers and CPython: 9,669 integer-power cases, 21,352 range-length cases, and 106,760 membership cases. It includes signed 64-bit endpoints, error text, an independent CPython arithmetic oracle, and 20,000 seeded random ranges (`seed=1123`).

The probe uses the actual native compiler's emitted helper IR, optimized with LLVM `default<O2>`, then links only the selected helpers and an error shim. That isolates native values and errors; it **does not validate Pystachy's full exception unwinder, GC, or timing**. Optimized helper call lists contain arithmetic intrinsics/error calls and no successful-path allocator calls. Individual code sizes changed from 128 to 154 bytes for integer power, 108 to 102 for range membership, and 94 to 91 for range length. These are helper sizes, not whole-executable size claims. [Report][numeric].

## Final scalar follow-up: completed checks and the corpus bridge

The early-return `pys_m_isclose` variant was measured separately at `6ed54439105206bd2e2a78b967eb73f359ad4988`, integrated in `1dd26979`, and validated with its final comments and benchmark defaults at `263bd32d3c64193c58127ef51e432de7d44db7da`. This follow-up is complete; the separately restarted final benchmark also completed successfully.

| Final-source check | Result and scope |
|---|---|
| Fresh three-stage bootstrap | Compiler fixed point: **833,502 IR lines**; runtime fixed point: **19,887 IR lines**. [Final build log][final-build]. |
| Compiler identity | Native compiler SHA-256 remained `793c313f8f580349f9fcd9a9f36a9a3d8847ed3187ddba94204747e37c3b3a23`, bit-identical to the original-core compiler. Stage-three compiler IR also retained SHA-256 `e8779b696e64a2be9cdcb6b853a22513d1b439fcb2cdf419dd905a61f868e7c2`. |
| Runtime change isolation | The before/after candidate runtime IR differs only in `pys_m_isclose`; all other bytes are identical. The pre-follow-up identities and exact comparison are retained. [Pre-follow-up identities][pre-isclose]; [final validation][final-validation]. |
| Runtime-only compiler comparison | Both baseline and final compilers recompiled the final `runtime.py`. Restoring the single expected checked-getter replacement in `pys_sum_float_int` reconstructs the complete baseline output exactly; all other bytes match. This is recorded as `final_runtime_ir_comparison` in [final-validation.json][final-validation]. |
| Focused executions | Fresh **104 passes**: 68 native JIT/AOT, 12 GC stress, 12 with `-listget`, and 12 through the CPython-hosted compiler. |
| ASan program executions | Fresh **12 passes**: six JIT and six AOT, with the corrected loader configuration. Empty successful AOT build logs are retained; per-case run/output checks are recorded in the final JSON. |
| Runtime algorithms and contracts | Fresh **604,985 hosted cases**, zero failures; runtime contracts and Ruff pass. |
| Native numeric contract | Fresh **137,781 cases** pass against the original C helpers and the independent integer oracle. This retains the original probe's isolated-error-shim limitation. [Final numeric log][final-numeric]. |

The original 4,245-case audit therefore supplies **4,244 unchanged-corpus/compiler comparisons plus the final incremental `runtime.py` comparison**. This reuses reviewed evidence on an identical compiler; it does not relabel the original audit as a new full run. The [final validation record][final-validation] includes source hashes, stage results, runtime comparison hashes and ASan AOT checks. The archived [validation runner][final-runner] records the actual commands and output comparisons; it was not executed while assembling this bundle.

## Benchmark history and the incomplete final attempt

Historical reports are retained to show why the scalar implementation changed. The completed [final all-case benchmark][bench-final] supersedes the incomplete attempt for the final workload comparison; these historical records remain distinct. Ratios below are median paired **candidate/baseline execution time**, so values above 1 mean slower execution for that measured case.

| Report | Scope | Scalar AOT / JIT ratio | Interpretation |
|---|---|---|---|
| [Initial all-case report][bench-initial] | Seven alternating pairs, CPU 8; all eight workloads | 1.0747 / 0.9741 | The short scalar and power intervals were sensitive to scheduling noise. Raw checksums, timings and memory observations remain in the report. |
| [Longer initial numeric report][bench-long] | Eleven alternating pairs, CPU 8; scalar at 120 million, range/power at 60 million iterations | 1.0916 / 1.0430 | Revealed the initial scalar AOT regression that prompted the early-return trial. This report covers three cases, not all eight. |
| [C helpers to early-return scalar][scalar-summary] | Eleven alternating pairs, CPU 8; 120 million scalar iterations | 1.0078 / 1.0337 | The measured scalar result is close to the C baseline with substantial pair-to-pair variation. It does not establish universal parity. |
| [Original port to early-return scalar][scalar-summary] | Same compiler, eleven pairs, CPU 8; 120 million scalar iterations | 0.9314 / 0.9992 | Isolates the scalar implementation improvement from compiler changes. |

The scalar trial used checksum `0x1.d12ef830239b7p+32`. Its C-to-early paired ratios ranged approximately 0.9213–1.0999 AOT and 0.9218–1.1587 JIT. Reported scalar managed-heap peaks were 0.4 MiB at the report's rounding precision, with zero collections for both variants. These observations are not exact allocation counts. Trial executables were 114,024 bytes for C and 114,552 bytes for both scalar ports; they are scalar-workload executables, not universal size measurements. The [C-to-early samples](scalar-followup/isclose-probe/c-to-early.json) and [port-to-early samples](scalar-followup/isclose-probe/port-to-early.json) retain the complete timing arrays and source/compiler metadata. Adjacent `*-executables.json` records retain the executable hashes.

**One final all-case attempt stopped after the scalar and range cases without a completion record or traceback; the execution session disappeared and the cause is unknown.** Source remained unchanged. Its [partial JSON][bench-partial] explicitly retains `complete: false`, and its [log][bench-partial-log] is archived. Those completed case fragments are not a complete final benchmark or a failed correctness test. The integration runner restarted the full longer-default, seven-pair benchmark; it completed successfully for all eight workloads on CPU 8. The [complete final report][bench-final] lives beside the maintained workload. The partial attempt remains `complete: false` and is not combined with the completed run.

The [saved AOT disassembly](scalar-followup/scalar-codegen.json) shows unchanged nine-byte `degrees`/`radians` helpers. `isclose` changes from 148 bytes in C to 166 in the initial port and 155 with separate exits. The final form preserves the C hot-path short circuit; its additional error-path setup supplies two arguments to `pys_raise`.

## Command provenance and reproduction

The logs retain exact underlying commands for bootstrap, contracts, lint and recordings. The execution forms below were confirmed by the integration runner; aliases and Bash arrays make the recorded selectors explicit. **This is a reproducible command summary, not an exact shell transcript, and it was not rerun while preparing this bundle. The archived runner scripts preserve their historical absolute paths and are method/command records, not turnkey portable launchers.**

```bash
cd /workspace/scratch/9c9ef915af51/pystachy
TASK=/workspace/scratch/9c9ef915af51
DEV=/workspace/scratch/e98dc1e3e6cd/dev/bin
LLVM=/workspace/scratch/e98dc1e3e6cd/toolchains/ubuntu-18.1.3-1ubuntu1-amd64/usr/lib/llvm-18/bin
PY="$DEV/python3.13"
export PATH="$DEV:$PATH" PYSTACHY_LLVM="$LLVM"

make PY="$PY"
make PY="$PY" check-runtime
"$PY" tools/rtabi.py ./pystachy
make PY="$PY" check-fast lint check-recordings

mapfile -t CASES < "$TASK/focused-cases.txt"
NEW_CASES=("${CASES[@]:0:6}")
tests/run.sh ./pystachy "jit aot" "${CASES[@]}"
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy "jit aot" "${NEW_CASES[@]}"
PYSTACHY_OPT=-listget tests/run.sh ./pystachy "jit aot" "${NEW_CASES[@]}"
tests/run.sh 'python3.13 -m pystachy' "jit aot" "${NEW_CASES[@]}"

"$PY" bench/runtime_subset/numeric_contract.py \
  --before "$TASK/baseline" --after . --compiler ./pystachy \
  --seed 1123 --random-ranges 20000 --json "$TASK/numeric-contract-final.json"
```

The first six selectors are `rt_scalar_math_input`, `rt_sum_float_edges`, `rt_ascii_edges`, `runtime_range_boundaries`, `runtime_power_boundaries`, and `opt_listget_range`.

The corrected ASan JIT invocation used these additional settings:

```bash
env PYSTACHY_JOBS=1 PYSTACHY_CFLAGS=-fsanitize=address \
  PYSTACHY_CACHE="$TASK/asan-program-cache" \
  ASAN_OPTIONS=detect_leaks=0:detect_stack_use_after_return=0 \
  LD_PRELOAD=/workspace/scratch/e98dc1e3e6cd/toolchains/ubuntu-18.1.3-1ubuntu1-amd64/usr/lib/llvm-18/lib/clang/18/lib/linux/libclang_rt.asan-x86_64.so \
  tests/run.sh ./pystachy jit "${NEW_CASES[@]}"
```

AOT used the same sanitizer/compiler settings except `LD_PRELOAD`: each fixture was built with `./pystachy build CASE -o OUTPUT`, run with its `.in` where present, and compared against `.out`. The standalone ASan harness, runtime differential, and focused IR logs retain outcomes but not their complete outer invocation arguments; no missing arguments are inferred here.

## Migration and validation gaps still open

| Remaining area | Actual current constraint and condition for a later port |
|---|---|
| Fixed-size native scratch | `pys_m_dist` and `pys_m_hypot_list` still use `double b[16]`, allocating an atomic buffer only above 16 coordinates. A temporary Python list would add heap allocation to small inputs. Preserve this storage choice through a nonescaping native stack-buffer facility or an equivalent measured interface. |
| Integer summation | `pys_sum_int` calls `list_narrow(l)` before reading slots and uses checked addition. `list_narrow` rejects promoting-integer storage that cannot be consumed as plain 64-bit integers. A later migration must retain that boundary. `pys_sum_int_float` also remains C and intentionally adds converted integers without compensation. |
| Modular power | `pys_powmod` uses signed/unsigned `__int128` for products, absolute endpoints and the modular inverse for negative exponents. Existing 64-bit wrapping multiplication is not an equivalent replacement. A port needs exact wide or overflow-safe modular arithmetic and separate correctness/performance evidence. |
| Broader bounds elimination | The new proof requires constant nonnegative start, constant positive step, invariant list identity/length, no whole-function list writes or unknown calls, and no suspension. Mutable loops, unknown starts and coroutine cases retain checks. This does not solve every reduction-loop shape. |

These constraints are visible in [runtime.c][runtime-c], the [subset runtime guide][runtime-guide], and the [compiler proof][bounds-source]. Raw allocation, GC, container layouts and native interfaces remain C responsibilities.

**Outstanding gates:** full `make verify`, the complete GC/optimizer-disabled/Python-free/UBSan and cache matrices, required CI on the final published head, and any cross-platform performance claims. ASan covers generated subset code but managed arena objects do not all receive independent red zones, so its passes do not establish every GC lifetime property. The completed performance evidence reports checksum-validated paired JIT/AOT results, noise, memory/GC observations and code-size scope; it does not extrapolate parity to all runtime algorithms.

[baseline-build]: original-core/baseline-build.log
[build]: original-core/candidate-build-fixed.log
[build-failed]: original-core/candidate-build.log
[contracts]: original-core/contracts-all-ports.log
[abi]: original-core/rtabi.log
[rtcheck]: original-core/rtcheck-all-ports.log
[selectors]: original-core/focused-cases.txt
[native]: original-core/native-tests.log
[gc]: original-core/gc-stress-tests.log
[opt-off]: original-core/bounds-disabled-tests.log
[hosted]: original-core/hosted-tests.log
[asan-jit]: original-core/asan-jit.log
[asan-aot]: original-core/asan-aot-direct.log
[asan-harness]: original-core/asan-instrumentation.log
[asan-failed]: original-core/asan-programs.log
[check-ir]: original-core/check-ir-focused.log
[fast]: original-core/check-fast.log
[lint]: original-core/lint-final.log
[recordings]: original-core/recordings.log
[irsame]: original-core/irsame-full.log
[classification]: original-core/irsame-classification.json
[numeric]: original-core/numeric-contract-final.json
[runtime-c]: https://github.com/den-run-ai/pystachy/blob/975e9c0b99c2717f3b26488e25e0638bde214f7f/runtime.c
[runtime-guide]: https://github.com/den-run-ai/pystachy/blob/975e9c0b99c2717f3b26488e25e0638bde214f7f/docs/runtime-in-subset.md
[bounds-source]: https://github.com/den-run-ai/pystachy/blob/975e9c0b99c2717f3b26488e25e0638bde214f7f/src/pystachy_compiler/optimizations.py

[final-build]: final-validation/candidate-build-final.log
[final-validation]: final-validation/final-validation.json
[final-numeric]: final-validation/final-numeric-contract.log
[final-runner]: final-validation/final_validate.py
[pre-isclose]: scalar-followup/pre-isclose-source.json
[bench-initial]: benchmark-history/runtime-subset-benchmark.json
[bench-long]: benchmark-history/runtime-subset-benchmark-long.json
[bench-partial]: benchmark-history/runtime-subset-benchmark-final-partial.json
[bench-partial-log]: benchmark-history/benchmark-final-partial.log
[scalar-summary]: scalar-followup/isclose-probe/summary.json
[irsame-method]: original-core/irsame-evidence.sh
[classification-method]: original-core/classify_irsame.py
[case-map]: original-core/irsame-case-map.json

[bench-final]: https://github.com/den-run-ai/pystachy/blob/975e9c0b99c2717f3b26488e25e0638bde214f7f/bench/runtime_subset/benchmark.json
[bench-readme]: https://github.com/den-run-ai/pystachy/blob/975e9c0b99c2717f3b26488e25e0638bde214f7f/bench/runtime_subset/README.md
