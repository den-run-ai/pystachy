# Recursion guard policy, 1 November 2026

[PR #996](https://github.com/den-run-ai/pystachy/pull/996) enforces `sys.setrecursionlimit()`
in native code ([#988](https://github.com/den-run-ai/pystachy/issues/988)). Its first design
counted every source frame, as CPython does, and recovered performance with whole-program
`recursionleaf` and `recursionregion` passes. Those passes cost more compilation than they
saved: on `bench/smoke/text.py` they added 18.6% to the frontend's instructions and 6% to
the LLVM IR, and every guarded function gained `R I` effects, so pure helpers stopped being
pure for the typed optimizations. That design's superseded
[optimization](https://github.com/den-run-ai/pystachy/blob/eac646137480a27467f5c933fd3a0507c39b6643/docs/reports/recursion-guard-optimization.md)
and [region](https://github.com/den-run-ai/pystachy/blob/eac646137480a27467f5c933fd3a0507c39b6643/docs/reports/recursion-guard-regions.md)
measurements remain at #996's merge commit.

The policy now counts only the functions that recursion can repeat
([internals](../internals.md#native-recursion-depth)): a source function on a cycle of
direct calls and generator resumes, or one that can reach code that graph does not show
(`U`: a call of a function value, a runtime callback such as `__eq__`). A generator resume
counts only if a body of its type can recur. Every other function is at most once on the
native stack, so it neither checks nor counts. The two passes, their private clones and the
related lowering paths are removed. Unbounded recursion is still caught; bounded recursion
can fail at a different call than in CPython
([deviation](../language/compatibility.md#errors-and-control-flow)). A cycle that reaches
nothing else that uses the depth keeps it in a register (closed recursion), which takes the
guards' stores out of recursive kernels such as `fib`.

## Inputs and method

| Input | Value |
|---|---|
| Baseline | main [07b26e0](https://github.com/den-run-ai/pystachy/commit/07b26e02425d023288ed95a9d2a5077be5aeb45e) |
| Previous candidate | PR #996 head [43eddb45](https://github.com/den-run-ai/pystachy/commit/43eddb455bc01ad348baec01590b258cacce681b) |
| Candidate | [55a7f4d7](https://github.com/den-run-ai/pystachy/commit/55a7f4d71f0c0adbf9c36eb729eab9f4b06ce3a9) on `claude/cool-gates-ownabn`, counted with a build of the same compiler code (4fdf4a4c with its wrappers `noinline`); the wall-clock runs measured [3d436d8b](https://github.com/den-run-ai/pystachy/commit/3d436d8bbfeccfcb38ed510fe2e2677381203487), whose wrappers clang could still inline |
| Intermediate | [ed51330c](https://github.com/den-run-ai/pystachy/commit/ed51330cd36c6632a39ce464190f59f15d983626), the same policy without closed recursion |
| Compilers | Each revision's native compiler from a fresh `make` bootstrap (three matching IR stages); PR head binary SHA-256 `588eb206…`, matching the PR record |
| Toolchain | LLVM/clang 18.1.3, CPython 3.13.18 (hosted compiler and oracle), Valgrind 3.22.0 |
| Host | Linux x86-64, Intel Xeon @ 2.10 GHz, 4 vCPUs, shared; counts pinned with `taskset` |
| Caches | Private runtime cache per revision, warmed before every measurement |

Instruction counts are Valgrind `callgrind` totals (`Ir`) and are deterministic: they do not
depend on host load. *Frontend* is `pystachy ir`. *AOT* is the whole process of the built
executable. *JIT* is `pystachy run` with every child process traced (frontend, `opt`,
`lli` code generation, execution and teardown). The counting runs themselves discard output;
afterwards every measured AOT executable (14 workloads, four revisions) was run again and its
output, apart from printed timings, matched CPython's. The wall-clock smoke below compares
every JIT and AOT run's output with CPython's. Its samples are reported separately: on this
shared host, sides with byte-identical program IR differed by up to 9% between medians, so
instruction counts carry the decision.

## Where the PR's cost came from

Measured on the PR head against main before this change:

- **The analyses themselves.** With `PYSTACHY_OPT=-recursionleaf,-recursionregion`, the same PR
  compiler spent 3.0% more frontend instructions than main on `text.py`; with the passes on,
  21.6%. The passes ran on every compilation, and their clones (`@rf`, `@rp`, `@rp2`, `@rc`) grew
  `text.py`'s module from 225 to 265 functions and 72,861 to 77,266 lines, which `opt` and `lli`
  then compiled too.
- **Lost purity.** Every source function gained `R I` from its entry check, so effect summaries
  of pure helpers stopped being empty (`tests/ir/effects.fx`: `@f.band:` became `@f.band: R I`).
  Typed optimizations and exception lowering treat such calls as raising and stateful.
- **Generator loops.** Each resume entered and left the depth, and the guarded `pys.gen.drop`
  (personality, invokes, landing pad) kept LLVM's coroutine elision from inlining a loop's
  generator: a plain generator loop ran 68% more AOT instructions than main.

## What changed

- `Gen.recursionscope` (`optimizations.py`, about 220 lines) replaces both passes (about 1,100
  lines, their eight test modules and eight exact-boundary fixtures). It runs once after the first
  effect summaries, from their call graph, and patches the summaries with the guards' known
  `R I` instead of walking every operation again. It is not a `PYSTACHY_OPT` pass.
- Uncounted functions keep their summaries from main; the `.fx` effect probes in `tests/ir` are
  byte-identical to main's again, and so are 32 of main's 40 `tests/ir` expectation files (the
  other eight add only the definition of the entry helper, in programs where an op calls it).
- A resume of a generator type none of whose bodies can recur has no accounting, and its loop's
  drop uses main's `pys.gen.drop`; recursive generators keep the counted forms.
- A Callable's adapter (`@cv.N`) no longer counts as a source frame. Under the PR, a call
  through a function value counted the adapter and its target, so a recursion through function
  values failed at about half of CPython's depth
  (`tests/programs/language/recursion_callable_frames.py`, which the PR head fails).
- The entry helper is no longer `alwaysinline`: LLVM 18's mandatory inliner builds block
  frequencies for every caller it changes, which added 13.8% to `opt` on `text.py` for 24
  inlined entries. clang `-O2` and the JIT's ordinary inliner still inline it where they run.
- **Closed recursion.** Each entry loaded the depth that the previous call had stored, so a
  recursion's calls formed one chain of stores and loads through the depth word. A cycle that
  reaches no `U`, no function outside it that can be entered again and no
  `sys.setrecursionlimit` finds the word as its outermost call found it until that call
  returns. Lowering emits each member's body as `@r.<symbol>`, which takes its caller's depth
  as an argument, checks it against the limit (`pys.recursion.check`) and passes its own depth
  to the cycle's calls, with no store; the member's symbol loads the word and calls the body.
  Frames count at the same calls as before. 195 of the compiler's own functions, 10 of
  `text.py`'s 24 counted ones and 8 of `regex_effbot.py`'s 12 are closed
  (`tests/programs/language/recursion_closed.py`, `tests/ir/closed_recursion.tbaa`).
- **Out-of-line wrappers.** The wrapper is `noinline` and compiles to a load and a jump to the
  body. Inlined, it added a load and an argument to each caller outside the cycle, which kept
  clang from inlining `Pattern._search` into `re.search` (below).

## Results

Instruction counts, main's absolute count and each revision's change from it:

| Frontend (`pystachy ir`) | main | PR #996 head | ed51330c | this branch |
|---|---:|---:|---:|---:|
| text | 2,283.8M | +21.62% | +1.66% | **+1.35%** |
| regex_effbot | 1,434.4M | +28.87% | +1.60% | **+1.40%** |
| ml | 33.3M | +26.14% | +1.95% | **+1.88%** |
| graph_copy | 89.5M | n/a | +2.43% | **+2.38%** |

| JIT (`pystachy run`, all processes) | main | PR #996 head | ed51330c | this branch |
|---|---:|---:|---:|---:|
| fnmatch | 10,004.5M | +6.88% | +0.22% | **+0.22%** |
| json | 9,979.9M | +7.00% | +0.29% | **+0.27%** |
| regex_effbot | 10,488.3M | +8.00% | +1.10% | **+1.04%** |
| autograd | 474.3M | +11.74% | +1.39% | **+1.46%** |
| richards | 1,384.9M | +20.13% | +0.10% | **+0.11%** |
| graph_copy | 910.9M | +6.82% | +3.53% | **+3.54%** |
| generators | 1,453.2M | +15.79% | +15.46% | **+15.52%** |

| AOT executable | main | PR #996 head | ed51330c | this branch |
|---|---:|---:|---:|---:|
| fnmatch | 162.8M | +2.51% | +0.44% | **+0.77%** |
| json | 167.9M | +3.44% | +1.91% | **+1.91%** |
| repair_scan | 758.2M | +0.01% | +0.00% | **+0.00%** |
| regex_effbot | 3,291.5M | +4.64% | +1.21% | **+1.01%** |
| autograd | 214.2M | +3.04% | +1.79% | **+1.43%** |
| numeric | 432.5M | +0.44% | +0.00% | **+0.00%** |
| richards | 133.3M | +31.08% | +0.00% | **+0.00%** |
| object | 268.3M | +0.00% | +0.00% | **+0.00%** |
| ordinary | 100.3M | -0.00% | +0.00% | **+0.00%** |
| json_calls | 803.9M | +1.74% | +1.02% | **+0.63%** |
| genloop | 9.7M | +68.43% | +0.00% | **+0.01%** |
| graph_copy | 387.2M | +1.78% | +1.62% | **+1.62%** |
| generators | 1,091.7M | +11.19% | +10.96% | **+10.93%** |
| fib | 433.3M | +41.35% | +41.35% | **+24.12%** |

`genloop` is [`bench/recursion/generator_loops.py`](../../bench/recursion/generator_loops.py)
with `200000`: two plain generators consumed by `for` loops (about 400,000 resumes). `object`
and `ordinary` are `bench/recursion`'s method and helper kernels, `json_calls` its JSON kernel.
`graph_copy` is the performance smoke's dynamic-`Any` deep copy (`tools/dynany_bench.py
graph-smoke 4000`). Emitted IR for `text.py` is 73,147 lines (main 72,861, ed51330c 73,118), for
`regex_effbot.py` 54,774 (main 54,598, ed51330c 54,746). The self-hosted compiler's IR is
788,153 lines (main 775,228, PR 808,291, ed51330c 786,440).

### What still costs

The remaining overhead is in code that genuinely recurses, where an exact limit has to count
every call. `fib(35)` makes 29,860,703 calls of 14.5 instructions each on main. Its closed form
adds 3.5 per call: the compare against the limit, and in the calls that recurse, the increment
and keeping the depth across the first recursive call. The memory protocol added 6.0, two of
them stores. The pyperformance `generators` benchmark walks a tree with recursive `yield from`,
about 17 counted generator resumes per value, which keep the depth word. JSON's and regex's
parsers and the autograd backward pass are recursive too; their counted calls cost 1–2%.

Closed recursion moves a little work to the cycle's callers: each call from outside goes
through the member's wrapper, which loads the word and passes it on. While clang could inline
the wrappers (3d436d8b), `regex_effbot`'s matcher ran 13M fewer instructions than under
ed51330c, but clang kept `Pattern._search` out of line in `re.search` (each inlined wrapper
added 10 to the inline costs it weighs), which cost 33M: the executable ran 1.92% more
instructions than main's. CI's advisory smoke measured its loop 8.4% and 8.1% slower than
main's on the runners of 2650357e and 4fdf4a4c. With `noinline` wrappers it runs 1.01% more
instructions than main's. The extra jump through a wrapper costs autograd's JIT run 0.27% of
its instructions and fnmatch's executable 0.11%, and the JIT runs of fnmatch and json
0.10% less.

`graph_copy` recurses through a table of copier functions (calls of function values),
so 12 of its 51 functions count, among them `copy_value`, every copier and `checksum`; none
is closed. Its executable runs 1.62% more instructions (PR: 1.79%). Under the JIT most of its
3.5% is fixed cost: with one graph instead of 4,000, `pystachy run` takes 5.2% more
(ed51330c). The JIT's pass pipeline, applied offline, leaves a module 7% larger (2,683 against
2,504 lines), whose `llc -O2` code generation takes 6% more instructions.

A single "remaining frames" counter updated by read-modify-write instructions would also
shorten the memory protocol, but it puts a second store-to-load dependency on every call's
path, so it was not adopted without a timing result that favors it.

### A resume that exceeds the limit

A review of e79e451d found that a counted resume whose entry exceeded the limit raised
`RecursionError` in the consumer but left the generator suspended, so a later `next()`
resumed it, where CPython has cleared its frame: its `finally` blocks do not run, and
`next()`, `send()`, `close()` and `throw()` then find it finished
(`tests/programs/generators/gen_recursion_resume_limit.py`). A counted resume now enters with
`recursion.resume`, given the generator's state word, whose overflow edge marks the generator
finished before it raises. The first version of that fix,
[c8d4ade1](https://github.com/den-run-ai/pystachy/commit/c8d4ade1),
stored the mark before every counted entry instead, and cost the `generators` executable 2.9%
more instructions and its JIT run 1.1%. On the cold path
([338fec59](https://github.com/den-run-ai/pystachy/commit/338fec59)), the executable's count
equals e79e451d's, the JIT run's is 0.06% higher, the plain generator loop's is unchanged and
the frontend's are 0.01% lower. The tables above were measured with 55a7f4d7's compiler, whose
counts these match within 0.1 point. With the fix the self-hosted compiler's IR is 788,316
lines.

## Validation of the candidate

Local, on the host above. The checks ran with 3d436d8b's compiler; after the wrappers became
`noinline` (55a7f4d7), its bootstrap, IR checks, unit tests, JIT dead-code probe and the
recursion, generator and regex cases ran again, and after the review's fixes (338fec59) the
checks of the last rows. CI's results are in the PR.

| Check | Result |
|---|---|
| `make` bootstrap | Three matching compiler IR stages (788,145 lines) and runtime IR stages (18,805 lines); compiler SHA-256 `0724724c…` |
| Corpus, JIT and AOT (`tests/run.sh`) | 6,130 passed, 0 failed |
| `tools/check_ir.sh` | IR check and `llvm-as` accept all 2,133 programs; `.calls`/`.fx`/`.attrs`/`.tbaa` expectations hold |
| Diagnostics and exit statuses against the PR head | All 3,917 corpus programs identical (`irsame` without the IR comparison, one shared library home whose compiled files are byte-identical in both revisions) |
| `PYSTACHY_GC_STRESS_PROGRAM=1`, JIT and AOT: recursion, generator, recursion-exception and Callable cases | 59 cases, 118 passed, 0 failed |
| `PYSTACHY_JIT_INLINE=0`, JIT: recursion and recursion-exception cases | 9 passed, 0 failed |
| `tests/ffi/run.sh` (extension recursion guards included) | 147 passed, 0 failed |
| `tests/cache.sh`, native and hosted | 66 and 68 passed |
| `make check-fast lint` | Pass: 352 tests, `ruff` 0.17.2, `mypy` 2.4.0 on 48 files, repository hygiene, runtime roots, shellcheck, clang `-Wall -Werror` |
| Lint's 22 other unit-suite commands | 511 tests pass, with `libclang-rt-18-dev` installed for the ASan controls as Lint installs it |
| `tests/record.sh --check` | 1,940 recordings and 111 deviations match CPython, except the two `sys_version_info` cases, which print the interpreter's version (3.13.18 here, 3.13.16 pinned) |
| Negative controls | `recursion_closed.py` crashes when a cycle's calls pass their caller's depth, and differs from CPython when the wrapper ignores the depth word; `recursion_set_limit.py` and the unit tests fail without the `setrecursionlimit` exclusion; the closed-recursion unit tests fail without the marking |
| 55a7f4d7: `make` bootstrap | Three matching compiler IR stages (788,153 lines) and runtime IR stages (18,805 lines); compiler SHA-256 `542259a4…` |
| 55a7f4d7: `tools/check_ir.sh`, unit tests, `tools/jitprobe.py` | All 2,133 programs; 71 tests of `test_typed_recursion.py`, `test_frame_fields.py`, `test_identity_scope.py` and `test_inspect_compiler.py`; hosted and native probes pass |
| 55a7f4d7: `make test` of the recursion, generator, regex, recursion-exception, dynamic-`Any` recursion, scoped-file and deviation cases | 48 cases, 96 passed in JIT and AOT |
| 338fec59: `make` bootstrap | Three matching compiler IR stages (788,316 lines) and runtime IR stages (18,805 lines); compiler SHA-256 `1cca29c4…` |
| 338fec59: IR, diagnostics and exit statuses against e79e451d's compiler: 3,929 programs, `irsame`'s corpus with `bench/recursion` and `bench/smoke` | No exit status or diagnostic changed, apart from the library's checkout path (e79e451d's compiler ran from outside the checkout). 3,806 compile to identical IR, among them the compiler and `runtime.py`; 63 differ only in their 1,493 counted resumes, which call `pys.recursion.resume` with the state word, and in that helper and its declaration; 60 whose resumes do not count differ in the declaration alone |
| 338fec59: `tools/check_ir.sh` | All 2,134 programs |
| 338fec59: generator, recursion and deviation cases, JIT and AOT | 63 cases, 126 passed, and 126 with `PYSTACHY_GC_STRESS_PROGRAM=1` |
| 338fec59: `make check-runtime check-fast lint`; Lint's `test_*verif*.py` | Pass: 353 tests; 99 tests (on 871ff2bb, whose harness is the same) |
| 338fec59: negative controls | `gen_recursion_resume_limit.py` differs from CPython in five of its cases with e79e451d's compiler; `test_typed_recursion.py`'s two resume tests fail on e79e451d's tree |

Three checks failed on the way and were fixed: `test_frame_fields.py`, until
[3cf9129e](https://github.com/den-run-ai/pystachy/commit/3cf9129e0f669c6417dbf33f08bc9cc23c7f47c1)
classified the `Gen` fields this change adds; `test_identity_scope.py`'s JSON delimiter
test, which read the parser's methods by their symbols until
[80ce9146](https://github.com/den-run-ai/pystachy/commit/80ce91465da3a70d783e4d1bbeb1f398e2298e01)
read their closed-recursion bodies; and CI's `jit-dead-code` contract, whose
`tools/jitprobe.py` required 35 definitions named `unused_*` until
[4fdf4a4c](https://github.com/den-run-ai/pystachy/commit/4fdf4a4cea33ff1d4b70da9a2cc90a60f2f08648)
counted source functions: closed recursion emits two of them as a symbol and a body. The new `tests/programs/language/recursion_counted_boundary.py`,
`recursion_callable_frames.py` and `recursion_closed.py` were recorded with CPython 3.13.18; the
pinned interpreter is 3.13.16.

## Wall-clock checks

Two timing runs followed the counts on the host above, before the wrappers became `noinline`;
neither carries the decision. Interleaved runs of the AOT executables, 21 rounds pinned to one
core, give each revision's median per-round ratio to main (this branch: 3d436d8b):

| AOT executable, wall clock | PR #996 head | ed51330c | this branch |
|---|---:|---:|---:|
| fnmatch | +2.0% | +1.5% | +3.1% |
| json | -1.3% | +0.3% | -1.5% |
| repair_scan | +2.9% | -5.3% | -6.0% |
| regex_effbot | -0.6% | -2.2% | -4.0% |
| autograd | +4.6% | +2.2% | +0.9% |
| numeric | +3.9% | +0.3% | +2.0% |
| richards | +15.7% | -0.6% | -0.1% |
| object | +1.5% | +1.5% | +0.6% |
| ordinary | -0.2% | -0.9% | -0.3% |
| json_calls | +4.0% | +2.8% | +0.4% |
| genloop | +6.8% | +0.0% | -1.1% |
| graph_copy | +0.6% | +0.7% | -0.3% |
| generators | +5.1% | +3.3% | +1.7% |
| fib | +34.1% | +33.7% | +4.5% |

Under ed51330c and this branch, `repair_scan` and `numeric` run within 0.01% of main's
instruction counts, so their spread, up to 6%, is this host's noise. Beyond it only `fib` (the
first row of [the performance page](../performance.md)) and the PR head's `richards` stand out.

`tools/perf_smoke.py --base` (CI's advisory smoke: three interleaved pairs per workload, and
three more where the first batch is at least 20% and 5 ms slower) compared main with
3d436d8b and with ed51330c and raised no warning either time; every JIT and AOT output matched
CPython's. Its medians moved between -24.6% and +12.2% for 3d436d8b, `copy_float`'s and
`copy_int`'s among the largest, although their program IR differs from main's only in value
names and unused declarations. Its +11.2% for `regex_effbot`'s AOT loop did not hold up on
this host: 41 interleaved rounds of that executable gave +0.8% against main (ed51330c: -1.5%),
with overlapping quartiles. CI's runners repeated it, though (+8.4% and +8.1%, above), and the
`noinline` wrappers remove the inlining change behind it.
