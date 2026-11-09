# Byte-level BPE and mypy/mypyc readiness, 2026-11-09

Main is `f60df76d` (v0.4.0-alpha.2 merged). A Claude Code subagent did this review read-only. Its
spot checks used a compiler built from main's tree `0e84b32e`, with LLVM 18.1.3 and CPython 3.13.18;
the scripts and outputs are in [scripts/](scripts/) and [results/](results/). The coordinating
session re-checked the claims marked *checked*.

Link prefixes used below:

- `M` = `https://github.com/den-run-ai/pystachy/blob/f60df76d2bcef35dd11142c5f1219ca3bc6f53f6/`
- `RC` = `https://github.com/den-run-ai/pystachy/blob/ae2c0afe568c6f5f02dd427e7981c1c6181462ea/examples/byte_bpe/results/runtime-comparison-2026-11-07/`

## Verdicts

- **Byte BPE:** ready with caveats for users and the README; not yet for upstream.
  - Correctness is strong and covered by CI.
  - Any speed claim must name the compiler revision `f7103067` (6 Nov). That is six releases ago,
    so re-measure before tying a claim to a release.
  - pyperformance has nothing to take from this work.
- **mypy/mypyc:** not a use case yet.
  - There is nothing users can run.
  - The experiments produced six general compiler optimizations.
  - Only a narrow compatibility note can be shared.
  - "mypy/mypyc" covers four separate activities:
    1. mypy and mypyc code as optimization inputs;
    2. mypyc as a comparison baseline;
    3. mypyc compiling Pystachy's own compiler;
    4. mypy type-checking the compiler in Lint.

## Byte BPE

### Source and correctness

- **Source:** pyperformance 1.14.0 (`2ab96f98`), MIT, by Shantanu Jain, derived from tiktoken (MIT).
  - The tokenizer and corpus match the hashes in `provenance.json` (*checked*).
  - Pystachy compiles a port with five marked edits. The "original CPython" baseline runs the
    unmodified code.
- **Edits still needed:** compile-only probes on main show that 4 of the 5 are still required
  ([results/out-bpe.log](results/out-bpe.log)):
  - field inference for `_decoder`;
  - `bytes.decode(errors=...)`;
  - `enumerate(zip(...))`;
  - an untyped `Counter()`.

  The `ranks` annotation is no longer needed.
- **Spot check on main** (*checked*):
  - 12 of 12 demo runs gave byte-identical stdout and exit status across pristine CPython, adapted
    CPython, JIT and AOT. The runs were: custom Unicode text at vocabulary 1,024; default text at
    1,024; vocabulary 256; and 255, which raises upstream's `ValueError`.
  - The `apps/byte_bpe.py` fixture matched its `.out` in JIT and AOT.
- **CI on `f60df76d`:** every job that runs BPE passed on x86_64 and aarch64:
  - `native-2`;
  - `gc-jit-1`;
  - `gc-aot-0`;
  - the pyperformance correctness step.
- **Not covered by CI:** the full corpus at vocabulary 1,024, `demo.py`, and any timing.

### Performance as recorded

- **6 Nov** (*checked* against `M`examples/byte_bpe/results/README.md):
  - Setup: compiler `f7103067`, a shared AMD EPYC host pinned to one CPU, CPython 3.13.16, five
    interleaved processes, no warmup. The build and 13.4 s of runtime preparation are excluded.

  | Stage | AOT vs CPython |
  |---|---|
  | Training | 4.31× faster |
  | Encoding | 2.93× faster |
  | Decoding | 3.07× faster |

  - RSS: 39.6 MiB for AOT, against 14.6 MiB for CPython; 14.7 MiB with `PYSTACHY_GC_MIN=8`.
- **7 Nov warmed comparison** (research draft #1126, `RC`): AOT against each baseline.

  | Baseline | Training | Encoding | Decoding |
  |---|---|---|---|
  | CPython | 4.84× | 2.89× | 3.30× |
  | Cython 3.3.1 | 2.95× | 1.96× | 2.54× |
  | mypyc 2.4.1 | 3.37× | 1.93× | 2.95× |
  | PyPy 8.0.1 | 1.95× | 0.93× | 1.94× |

  PyPy is about 8% faster at encoding, and those ranges overlap. The evidence verifier passes on a
  `git archive` copy.
- **Stability:** nothing has been measured since 7 Nov. The compiler has since changed by
  +5,177/−324 lines in 62 commits.

### Bug bash and review

- **Stable code:** no BPE issue has ever been filed, no wrong output has been reported, and the
  code has not changed since 6 Nov.
- **Review gaps:**
  - #1107 reached main through #1139 without a review; #1139's automatic review finished 32 s
    after the merge.
  - #1126 is unreviewed. Its Verification failed because `native-0` was cancelled at the
    15-minute limit.
- **Stale documentation** (*checked*):
  - `M`bench/pyperformance/README.md#L219 still lists `bpe_tokeniser` under "Sources without a port".
  - `M`bench/optional_scalar_slots/README.md#L99 still says "draft review … before merge", although
    #1131 is merged.

### Shareability

- **Upstream:** nothing for pyperformance. No upstream bug was found, and the edits are specific to
  Pystachy. Reviewers from pyperformance or faster-cpython would ask for:
  - pyperf, rather than a shared host with five samples;
  - pyperformance's own metric;
  - unmodified source;
  - a CPython 3.14 baseline;
  - several input sizes;
  - build and preparation costs included;
  - tuned Cython and mypyc builds;
  - a CPU profile.
- **Downstream:** the example needs a source checkout. The README's scope statements are careful.
  The demo text greets "Sebastian", and the README credits Sebastian Raschka's teaching examples
  (*checked*). Use neutral text for any announcement.

### Draft public claim

> On Linux x86-64, Pystachy (compiler revision `f7103067`, 6 Nov 2026, LLVM 18.1.3) compiled
> pyperformance 1.14.0's educational byte-pair tokenizer with five small, marked source edits.
> Compared with the unmodified code on CPython 3.13.16, the ahead-of-time build trained a
> 1,024-token vocabulary on the benchmark's 31 KB text 4.3× faster. It encoded the text 2.9× faster
> and decoded it 3.1× faster. These are medians of five interleaved processes on a shared host;
> build time and I/O are excluded. Every run reproduced CPython's vocabulary, tokens and text byte
> for byte. Peak memory was 39.6 MiB against 14.6 MiB for CPython, or 14.7 MiB with
> `PYSTACHY_GC_MIN=8`. This is one educational tokenizer, not production tiktoken and not an
> official pyperformance result.

### Next steps

1. Re-run `examples/byte_bpe/benchmark.py` on the release tag on an idle host.
2. Get #1126 reviewed, or label its README link as research.
3. Add a pyperf-protocol run, with CPython 3.14 alongside 3.13.
4. Fix the two stale README lines.
5. File issues for the four remaining port blockers.

## mypy and mypyc

### What exists

- **Six merged optimizations** (#1065–#1069, #1078). Each came from a mypy or mypyc component used
  as a test input, and each has general regression tests. No mypy source is committed, and the
  replay harnesses were never committed.
- **NameGenerator** at `python/mypy@1231cf15`.
  - Spot check on main (*checked*): the unchanged `namegen.py` gives the same output as CPython in
    JIT and AOT.
  - All five of mypyc's own `test_namegen.py` tests pass on CPython, JIT and AOT
    ([results/out-namegen.log](results/out-namegen.log)).
- **The stubgen parser:** prose only (`M`docs/porting.md#L109-L117). The fork commit could not be
  read from this session.
- **Pystachy's compiler built with mypyc:** `M`examples/comm/mypyc_compiler.md, run by hand once
  on 7 Nov.
  - The build used mypyc 2.4.0 with its C compiled at `-O0`.
  - All 55 modules ran as extensions, and the compiler's self-compiled IR (33 MB) was byte-identical
    to the CPython-hosted output.
  - Not in CI.
- **mypy type-checking:** `make typecheck` (mypy 2.4.1) runs in Lint and passed on `f60df76d`.

### Fairness and performance

- **No end-to-end mypy or mypyc speedup has ever been shown.** Measurements inside real mypy
  workloads were neutral or worse: #1069's extension call per emitter result raised the time from
  5.01 to 6.73 ms.
- **BPE against mypyc:** fair as labeled, but mypyc built the pristine code plus one annotation,
  while Pystachy built the five-edit port. The C compilers also differed.
- **The comm example's mypyc row:** this measures the ctypes bridge, not compiled code. The document
  says so.

### Shareability

- **mypy maintainers:** there is no bug to report.
- **mypyc maintainers:** one positive data point: a 55-module code base builds unchanged and
  reproduces its output byte for byte. Re-run it on main, with mypyc 2.4.1 and an optimized build,
  before sharing.
- **Users:** there is nothing to run.

### Draft public claim

> Pystachy's own compiler (55 Python modules) also compiles unchanged with mypyc. On 7 Nov 2026, a
> mypyc 2.4.0 build (C compiled at `-O0`) produced byte-identical LLVM IR when compiling the
> compiler itself. Separately, selected mypy and mypyc components served as test inputs that led
> to six general compiler optimizations merged on 4 Nov 2026. Pystachy does not ship, support or
> test any mypy or mypyc component in its CI, and claims no end-to-end mypy or mypyc speedup.

### Next steps

1. Keep the replay harnesses for #1065–#1078 on a research branch, or mark their PR numbers as
   historical.
2. Re-run the mypyc build of the compiler on main, at `-O2` with mypyc 2.4.1. Compare it with
   Pystachy's native compiler on the same self-compile job.
3. Optionally vendor `namegen.py` (hash-pinned, MIT) and its five tests under `tests/upstream/`.

## Not checked

- Timings.
- macOS.
- Builds with mypyc, Cython or PyPy.
- The upstream mypy, pyperformance and `den-run-ai/mypy` repositories.
- The pinned CPython 3.13.16; the checks used 3.13.18.
