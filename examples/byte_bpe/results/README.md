# Byte-BPE measurements: 6 November 2026

**The full native port matches the original CPython kernels and accelerates all three measured stages.** These are measurements of this educational tokenizer and corpus, not production tiktoken or published pyperformance scores.

## Stage measurements

Source revision `72f5291204afac933597cbe42c897a902cb97e2a` uses unchanged compiler/runtime/library sources from `f7103067545b43cdcd8ce20dc66b1571425b3a8d`. CPython 3.13.16, LLVM 18.1.3, Linux x86-64, AMD EPYC 9V74; pinned to CPU 0 on a shared host. Five interleaved processes per mode. The unchanged Frankenstein input is 31,206 UTF-8 bytes; vocabulary size is 1,024. Each process trains once, encodes 50 times and decodes 200 times.

Times are median milliseconds per operation. Speedup is original CPython median divided by AOT median. Input I/O, full-state output and validation are outside the stage timers.

| Stage | Original CPython | Adapted CPython | Native JIT | AOT | AOT speedup |
|---|---:|---:|---:|---:|---:|
| Training | 4,361.500 | 4,352.251 | 1,059.093 | 1,010.799 | 4.31× |
| Encoding | 37.993 | 40.725 | 14.097 | 12.949 | 2.93× |
| Decoding | 0.662 | 0.622 | 0.222 | 0.216 | 3.07× |

Observed process-sample ranges, milliseconds per operation:

| Stage | Original CPython range | AOT range |
|---|---:|---:|
| Training | 4,203.632–4,621.201 | 974.276–1,113.802 |
| Encoding | 35.619–40.284 | 12.259–14.147 |
| Decoding | 0.515–0.801 | 0.186–0.248 |

The complete stage command took **6.394 s CPython versus 1.669 s AOT**, a 3.83× ratio of medians. This command includes one training pass and repeated encoding/decoding; it is not a single-query latency measurement. Adapted CPython remains a separate baseline so allocation workarounds cannot inflate the headline.

## Compilation and memory

Native JIT spent a median **1.596 s outside the stage timers**. That includes compilation, startup, I/O, validation and printing; it does not isolate LLVM time. AOT building took 6.615 s after a private JIT-runtime warmup. Initial runtime preparation took 13.422 s and is reported separately. Build and preparation times are single observations.

| Execution | Sampled peak RSS, median | Processes |
|---|---:|---:|
| Original CPython, default group | 14.6 MiB | 5 |
| AOT, default GC | 39.6 MiB | 5 |
| AOT, `PYSTACHY_GC_MIN=8` | 14.7 MiB | 3 |

The 8 MiB threshold reduced this workload's sampled peak RSS by **62.9%**. All 12 GC-group executions matched the original CPython output. These groups were run separately, not paired across GC settings: their timing differences are inconclusive as a GC cost estimate. The AOT training medians were 1.011 s default and 1.155 s at 8 MiB. Keep the global default unchanged and select this setting per workload.

RSS uses Linux `VmHWM` observations approximately every 5 ms after the child installs the requested command, with parent/namespace checks. It can miss a brief final peak. The JSON also retains `wait4` RSS, which can include the launcher's pre-exec high-water mark. JIT/compiler memory is not application-only memory. The first timing pass lacked namespace-resolved memory observations; its timing results were not used for this table, and the final pass was repeated with the corrected sampler.

## Optional program-cache consumer

This separate experiment uses [PR #1103](https://github.com/den-run-ai/pystachy/pull/1103) at `706b47facf690f83c234097706e8fef9230c1cad`. It is not a dependency of the port and does not validate the concurrent default-cache changes. The command runs `demo.py`, trains on the full corpus, and encodes/decodes a short Unicode string afresh each time. Only executable code is reused.

| Launch measurement | Result |
|---|---:|
| Uncached, median of five | 3.028 s |
| Cache hit, median of five | 1.249 s |
| Median paired speedup | 2.42× |
| Initial program-cache fill, one observation | 16.097 s |

All five pairs improved (1.77–2.79×), but absolute elapsed times varied broadly on the shared host. All 14 launches returned identical complete CLI stdout, zero status and empty ordinary stderr. **Six verified hits made zero frontend and zero wrapped LLVM calls.** Each measured uncached launch called `opt` and `lli`. The first fill emitted `miss → frontend → stored`; its initial tool/static hashing and build cost is kept separate. RSS was not measured for this optional experiment.

## Validation and reproduction

- Six complete ordered training vocabularies, 19 text/token/byte round trips, all 256 byte values, eight replacement-decoding cases and eight rejection cases pass against pristine CPython. The fixture passes native JIT/AOT both normally and with collection at every allocation.
- All 20 default and 12 GC-group process samples match the pristine original CPython kernel's complete ordered vocabulary, token list, decoded bytes and text.
- Nine CLI cases pass in CPython, JIT and AOT: 27 checks, covering Unicode/whitespace, the empty 256-entry vocabulary, usage, bad numbers, missing files and exhausted merges. Invalid invocations are checked for status/stdout; traceback formatting is not equated across runtimes.
- Thirty hosted controller/port tests pass, including malformed/nonfinite timing, output corruption, stale-success report, source-pin and nested-PID controls. Existing pyperformance smoke passes in all three modes. Eleven repository-hygiene tests and local lint pass.
- The unchanged native compiler was reused from a recorded successful three-stage compiler/runtime fixed point. Its binary hash and all compiler/runtime/library source paths were verified; see the compiler identity record. Full local `make verify` was not run. PR CI provides the broader current-head gate.

```sh
python3 examples/byte_bpe/benchmark.py --processes 5 --cpu 0 --json build/byte-bpe.json
python3 examples/byte_bpe/benchmark.py --processes 3 --cpu 0 --gc-min 8 --json build/byte-bpe-gc8.json
python3 tools/bench_pyperformance.py --benchmarks bpe_tokeniser --smoke
tests/run.sh ./pystachy 'jit aot' tests/programs/apps/byte_bpe.py
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' tests/programs/apps/byte_bpe.py
python3 -m unittest discover -s tools -p test_bench_pyperformance.py
make lint
```

Use a compiler built from this checkout, CPython 3.13.16 and a complete LLVM 18 toolchain. Set `PYSTACHY_LLVM` if needed. The exact commands, source/toolchain fingerprints, environment and raw samples are in the records below. CPU pinning and clean runtime caches are controlled by the runner.

### Evidence

- [Default stage samples and complete oracle](2026-11-06-default.json)
- [GC threshold 8 MiB samples](2026-11-06-gc8.json)
- [CLI outcomes](2026-11-06-cli.json)
- [Compiler identity and recorded fixed point](2026-11-06-compiler.json)
- [Program-cache samples and 57 assertions](2026-11-06-program-cache.json)
- [Exact archived cache experiment driver](2026-11-06-program-cache-driver.py)

The archived cache driver preserves the original run's defaults and hash. For another machine, supply all location arguments: `--project` (this checkout), `--home` (a clean #1103 checkout at the pinned commit), `--compiler`, `--expected-compiler-sha256` (a verified bootstrap binary), `--llvm`, `--python`, `--cpu` and `--output`. The helper and wrapper behavior come from that pinned cache checkout. Its temporary artifacts are private; it never edits the compiler checkout.

### Related work

The port was checked against the ongoing cache, GC and example work before implementation. It uses current main rather than stacking compiler/runtime prototypes. [#1097](https://github.com/den-run-ai/pystachy/pull/1097) consolidates the pyperformance docs and [#1099](https://github.com/den-run-ai/pystachy/pull/1099) adds the example index; preserve their consolidation/index when integrating these narrow BPE links and count updates. [#1101](https://github.com/den-run-ai/pystachy/pull/1101) adds broader example CLI validation. This port already joins the existing pyperformance and differential jobs and adds no CI job.
