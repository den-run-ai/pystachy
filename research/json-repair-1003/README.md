# JSON-repair correctness and performance evidence for PR #1003

Candidate: [`dceda23e`](https://github.com/den-run-ai/pystachy/commit/dceda23e8b71311c43e5c843698ed4443292004b); baseline: [`07b26e02`](https://github.com/den-run-ai/pystachy/commit/07b26e02425d023288ed95a9d2a5077be5aeb45e).

The implementation and six regression programs are byte-identical to implementation commit `94894897`. Later commits refresh documentation and correct one benchmark witness expression. This research branch preserves evidence; it is not proposed for merging.

## Result

The dynamic native decoder promotes an overflowing integer token directly instead of sending the entire valid document through heuristic repair. This preserves root integers, surrogate pairs, strict empty/duplicate-key behavior, nonfinite values and missing-opening-brace recovery. Integer conversion-limit errors remain visible. Object/array comments retain the following value and container nesting. Active array/object/string repair parses are bounded to 256; alternating top-level comments and prose are processed iteratively.

The controls add essentially no AOT instructions for valid JSON and 1.65–1.78% for malformed repair, with similar whole-process memory to baseline. Longer JIT confirmation gives +4.11% for malformed object-return repair and -0.70% including serialization, with overlapping ranges. Elapsed measurements do not establish a latency improvement or zero overhead. This is fix-branch evidence, not validation of a future final alpha.4 release commit.

## Correctness

- The original 645-case corpus matches in adapted CPython, native JIT, native AOT, JIT with collection at every allocation and AOT with collection at every allocation. The upstream oracle was not changed.
- Six new regression programs pass in both native modes with collection at every allocation: 12 successful executions. They cover integer boundaries, raw-decode offsets, code points, 31 digit-limit assertions, comment semantics and depth/unwinding behavior.
- Existing JSON/repair selection: 24 programs, 48 JIT/AOT passes. Corrected ordinary-mode new fixtures also pass. Initial test-only compilation errors from unsupported `ord(Any)` and a typed JSONValue-to-Any conversion are retained in `focused-new.log`; later recordings use supported narrowing and preserve the same expected values.
- Independent baseline/candidate probes agree between JIT and AOT in each role, and reproduce the original defects before the fix. The source and complete outputs are included.
- Fresh baseline bootstrap: compiler and runtime three-stage fixed points, 775,228 and 18,805 IR lines. Local runs use that source-identical compiler with explicit baseline/candidate resource homes; the compiler and runtime source files themselves are unchanged.
- Local Ruff, shellcheck, C warning/root lint, 29 JSON tool unit tests and 11 repository-hygiene unit tests pass. The full recording check checked 1,934 recordings, 110 deviations and 11 library copies, but retains one failure: unchanged `exc_except_attr` sees sandbox OSError(30) instead of FileNotFoundError(2). The fixture was not rewritten. Exact-head GitHub Lint separately passes.

## AOT instruction controls

LLVM/Clang 18.1.3, CPython 3.13.16, Valgrind 3.22.0, Intel Xeon Platinum 8573C, CPU 0. Each value subtracts a zero-loop process from the corresponding measured-loop process, using one batch and no warmups. Counts include the loop, checksums and its allocation/GC work; they are not wall-clock throughput or JIT instruction counts. Tiny differences can include timing-number formatting. Full Callgrind profiles and output checks are preserved.

| Control | Rounds | Baseline instructions | Candidate instructions | Change |
|---|---:|---:|---:|---:|
| json-small | 300 | 46,356,232 | 46,356,218 | -0.000% |
| json-serialize | 300 | 89,512,160 | 89,791,452 | +0.312% |
| repair-valid | 500 | 11,911,237 | 11,911,738 | +0.004% |
| repair-malformed | 200 | 76,204,296 | 77,558,176 | +1.777% |
| repair-serialize-valid | 500 | 27,502,471 | 27,502,986 | +0.002% |
| repair-serialize-malformed | 200 | 82,443,760 | 83,801,878 | +1.647% |

The direct JSON control has 32 rows per document. Repair controls contain four inputs per round. The direct control deliberately does not import json_repair, which already opts into promoting integers and would mask an import-related effect.

## Elapsed controls: advisory

Processes are interleaved in rotating order and pinned to CPU 0. AOT uses five process rounds, five measured batches and six warmups; JIT uses three rounds, three batches and three warmups. Complete output is checked before and after every batch. The same adapted parser runs under CPython. These are common inputs on which baseline and candidate are both correct; the newly fixed failures are not timed as if their old wrong outputs were valid.

Medians of process medians, milliseconds per batch:

| Control | Baseline AOT | Candidate AOT | CPython (AOT campaign) | Baseline JIT loop | Candidate JIT loop |
|---|---:|---:|---:|---:|---:|
| json-small | 7.946 | 8.653 | 11.145 | 9.454 | 10.421 |
| json-serialize | 26.204 | 19.124 | 15.077 | 12.439 | 12.336 |
| repair-valid | 2.889 | 4.431 | 5.127 | 4.079 | 4.006 |
| repair-malformed | 13.045 | 20.862 | 115.636 | 15.912 | 20.118 |
| repair-serialize-valid | 5.181 | 5.335 | 9.824 | 6.872 | 8.218 |
| repair-serialize-malformed | 19.025 | 13.708 | 87.999 | 16.180 | 18.544 |

Elapsed apparent regressions are retained, not relabelled as wins. For example, AOT malformed repair has process medians of 11.715–19.119 ms on baseline and 10.433–43.465 ms on candidate; valid repair has 2.018–4.360 ms versus 1.852–9.232 ms. This variation and the separate +1.777% instruction result do not establish a causal elapsed magnitude. The short JIT malformed samples initially suggested a larger regression: +26.4% for object returns and +14.6% including serialization. Their raw samples are preserved. They prompted the separate longer confirmation below rather than being dismissed using the AOT instruction result.

## JIT confirmation

The same exact source and probe were rerun sequentially, pinned to CPU 0, with two native variants in alternating order, five process pairs, five measured batches and three warmups. Each batch contains 5,000 rounds (20,000 repairs), compared with 200 rounds in the earlier campaign. No other local native benchmark ran concurrently.

| JIT control | Baseline median ms | Candidate median ms | Change | Baseline process range ms | Candidate process range ms |
|---|---:|---:|---:|---:|---:|
| repair-malformed | 324.236 | 337.573 | +4.11% | 321.232–357.258 | 326.001–348.783 |
| repair-serialize-malformed | 364.575 | 362.023 | -0.70% | 354.752–372.689 | 357.049–365.603 |

The longer controls do not reproduce the earlier 26% difference. They still show a possible modest malformed-repair cost; overlapping ranges do not prove equivalence.

A transparent lli wrapper also captured the actual optimized JIT program and ran lli under Callgrind. The table subtracts each role’s zero-loop process from its 200-round process. This includes approximately cancelling ORC code generation as well as timed loop work; it is not an isolated hardware count or a throughput measurement. The IR is identical between the zero-loop and measured-loop process in each role after excluding only source_filename, which names the driver’s temporary file. Raw IR and normalized hashes are retained.

| JIT control | Baseline incremental instructions | Candidate incremental instructions | Change |
|---|---:|---:|---:|
| repair-malformed | 87,522,094 | 89,404,694 | +2.151% |
| repair-serialize-malformed | 94,287,344 | 96,215,961 | +2.045% |

The captured baseline program has 22,491 LLVM IR lines and the candidate 22,845. Both retain the array/object/string forwarding calls; there is no evidence of a newly crossed inlining threshold. The new depth guards add fixed-width field checks and exception unwind bookkeeping; their successful hot path allocates no integer objects.

A controlled final-release benchmark is still needed. PyPy, GraalPy and pristine-upstream comparisons were not rerun.

## Startup and memory

Zero-loop process observations include imports, fixture construction and validation. Runtime caches were prepared before JIT measurements; cold runtime-cache construction is not measured. Candidate JIT process medians were 367 ms for direct JSON and 1,486 ms for malformed repair, versus 389 and 1,430 ms on baseline (three samples). AOT process observations sit at the runner’s roughly 10 ms polling floor and do not resolve actual AOT startup latency.

The generic Python runner initially reports an inherited launch-memory floor for short children (about 49–52 MiB); those raw results are retained but are not used below. A small fresh C parent uses wait4 to measure the child’s peak RSS without that Python-parent floor. Three runs per cell use three warmups and one measured batch. This is whole-process peak memory, including fixtures and validation, not retained heap or a long-running service test.

| Control | Baseline AOT MiB | Candidate AOT MiB | Adapted CPython MiB |
|---|---:|---:|---:|
| json-small | 27.988 | 27.805 | 13.098 |
| json-serialize | 38.430 | 38.617 | 13.145 |
| repair-valid | 19.645 | 19.434 | 15.547 |
| repair-malformed | 25.551 | 25.551 | 15.547 |
| repair-serialize-valid | 32.273 | 32.254 | 15.484 |
| repair-serialize-malformed | 30.551 | 30.371 | 15.570 |

Native peak RSS stays close to baseline on these controls and exceeds CPython’s. This does not establish general memory efficiency.

## Limits and release status

- The public typed JSONValue/JSONDecoder path still checks signed 64-bit bounds. Dynamic loads/raw_decode promotes tokens and retains the 4,300-digit decimal limit.
- Forced repair can discard primitive roots, including primitives surrounded by comments or prose, following upstream heuristics. Use default decoding for valid scalar documents.
- The 256-active-parse policy intentionally rejects some deeper native repairs that previously completed. CPython may exhaust its interpreter stack earlier. General compiler recursion semantics and PR #996 remain separate.
- The JSON-repair announcement remains held. No release was published or PR merged here.

## Reproduction and retained files

Use the pinned candidate and baseline commits and the maintained `bench/json_repair/codec.py`, `facade.py` and `tools/json_repair_bench.py`. The archive keeps exact command arrays, environment overrides, source/binary hashes, process samples, all Callgrind profiles, native replay output, failure logs and the small RSS launcher. Local absolute paths in the raw scripts/configurations describe this execution and should be replaced for another checkout.

The two roles deliberately use the same freshly bootstrapped native compiler binary because compiler/runtime sources are unchanged; each role has its own PYSTACHY_HOME and runtime cache. Do not accidentally give the baseline the candidate’s library path.

[Download the complete evidence archive](evidence.tar.xz): 1,713,480 bytes, 125 entries. Archive integrity, entry uniqueness and every archived file’s size/hash were checked. Each retained file has a byte size and SHA-256 in manifest.json.

Archive SHA-256: `d2b3683eaafff1f9b446a745e6c4c5180d016af8e0460813fda32ae6d42b52d3`.

Exact-source GitHub CI completed with 40 successful checks and one expected fork-only DCO skip. The CI, Installation, Packages, Lint and Performance smoke workflows all succeeded. See `ci.json` for the complete check/run ledger and URLs. Maintainer review is still required before merge.
